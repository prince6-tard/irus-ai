"""Hunter.io lead enrichment module.

Reads leads_raw.csv and uses Hunter.io to find/verify emails. Writes to leads_enriched.csv.
"""

import os
import time

import requests
from dotenv import load_dotenv

from config import ENRICH_WITH_HUNTER
from db import get_raw_leads, update_lead

load_dotenv()

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
HUNTER_DOMAIN_URL = "https://api.hunter.io/v2/domain-search"
HUNTER_FINDER_URL = "https://api.hunter.io/v2/email-finder"


def _hunter_get(url: str, params: dict) -> dict | None:
    """GET a Hunter endpoint with rate-limit handling."""
    if not HUNTER_API_KEY:
        return None
    time.sleep(1)
    for attempt in range(2):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                print(f"Hunter rate limit (429). Waiting 30s... (attempt {attempt + 1}/2)")
                time.sleep(30)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            print(f"Hunter request error (attempt {attempt + 1}/2): {exc}")
            if attempt < 1:
                time.sleep(5)
    return None


def _domain_search(domain: str) -> tuple[str, str]:
    """Try Hunter Domain Search. Return (email, source) or ("", "none")."""
    params = {
        "domain": domain,
        "api_key": HUNTER_API_KEY,
        "limit": 1,
        "department": "management",
    }
    data = _hunter_get(HUNTER_DOMAIN_URL, params)
    if data and data.get("data", {}).get("emails"):
        email = data["data"]["emails"][0].get("value", "")
        if email:
            return email.strip().lower(), "hunter"
    return "", "none"


def _email_finder(domain: str, first_name: str, last_name: str) -> tuple[str, str]:
    """Try Hunter Email Finder. Return (email, source) or ("", "none")."""
    params = {
        "domain": domain,
        "first_name": first_name,
        "last_name": last_name,
        "api_key": HUNTER_API_KEY,
    }
    data = _hunter_get(HUNTER_FINDER_URL, params)
    if data and data.get("data", {}).get("email"):
        email = data["data"]["email"].strip().lower()
        if email:
            return email, "hunter_finder"
    return "", "none"


def _enrich_single(lead: dict) -> dict:
    """Enrich one lead with Hunter.io if needed."""
    result = dict(lead)
    result["email_source"] = "apollo" if lead.get("email") else "none"
    result["has_phone"] = bool(lead.get("phone"))
    result["notes"] = ""

    # If Apollo already gave us an email, keep it and skip Hunter
    if lead.get("email"):
        result["notes"] = "Email provided by Apollo."
        return result

    if not ENRICH_WITH_HUNTER or not HUNTER_API_KEY:
        result["notes"] = "No Apollo email; Hunter enrichment disabled or missing key."
        return result

    domain = lead.get("organization_domain", "").strip().lower()
    if not domain:
        result["notes"] = "No Apollo email and no organization domain for Hunter."
        return result

    # 1. Domain Search
    email, source = _domain_search(domain)
    if email:
        result["email"] = email
        result["email_source"] = source
        result["notes"] = f"Email found via Hunter Domain Search ({domain})."
        return result

    # 2. Email Finder (need first/last name)
    name_parts = lead.get("name", "").strip().split()
    first_name = name_parts[0] if len(name_parts) > 0 else ""
    last_name = name_parts[-1] if len(name_parts) > 1 else ""

    if first_name and last_name:
        email, source = _email_finder(domain, first_name, last_name)
        if email:
            result["email"] = email
            result["email_source"] = source
            result["notes"] = f"Email found via Hunter Email Finder ({domain})."
            return result

    # Nothing worked
    result["notes"] = "No email found via Apollo or Hunter."
    return result


def enrich_leads() -> list[dict]:
    """Read leads from DB, enrich with Hunter.io, and UPDATE back to DB.

    Returns:
        List of enriched lead dicts.
    """
    leads = get_raw_leads()

    if not leads:
        print("No raw leads to enrich.")
        return []

    enriched: list[dict] = []
    for idx, lead in enumerate(leads, start=1):
        print(f"Enriching lead {idx}/{len(leads)}: {lead.get('name', 'Unknown')}")
        try:
            enriched_lead = _enrich_single(lead)
            enriched.append(enriched_lead)
        except Exception as exc:
            print(f"Error enriching lead {lead.get('name', 'Unknown')}: {exc}")
            lead["email_source"] = lead.get("email_source", "none")
            lead["has_phone"] = bool(lead.get("phone"))
            lead["notes"] = f"Enrichment error: {exc}"
            enriched.append(lead)

    # Write enriched data back to DB
    for lead in enriched:
        update_lead(
            lead.get("email", ""),
            email_source=lead.get("email_source"),
            has_phone=lead.get("has_phone"),
            notes=lead.get("notes"),
            email=lead.get("email"),
        )

    print(f"Enriched {len(enriched)} leads")
    return enriched
