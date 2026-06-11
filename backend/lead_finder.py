"""Serper + Hunter lead discovery module.

Uses Serper Places API to find organizations near a target location, then
scrapes their websites and queries Hunter.io to find management contacts.
No Apollo needed.
"""

import os
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from config import MAX_SENDS_PER_RUN
from db import insert_leads

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
SERPER_PLACES_URL = "https://google.serper.dev/places"


def _serper_search(query: str, gl: str = "in", hl: str = "en") -> list[dict]:
    """Call Serper Places API to find organizations."""
    if not SERPER_API_KEY:
        print("Warning: SERPER_API_KEY not set. Skipping lead discovery.")
        return []

    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "gl": gl, "hl": hl}

    for attempt in range(2):
        try:
            resp = requests.post(SERPER_PLACES_URL, headers=headers, json=payload, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            places = data.get("places", [])
            results = []
            for p in places:
                results.append({
                    "name": p.get("title", "").strip(),
                    "address": p.get("address", "").strip(),
                    "phone": p.get("phoneNumber", p.get("phone", "")).strip(),
                    "website": p.get("website", "").strip(),
                    "city": _extract_city(p.get("address", "")),
                })
            print(f"  ✅ Serper found {len(results)} places for '{query}'")
            return results
        except requests.exceptions.RequestException as exc:
            print(f"  ❌ Serper error (attempt {attempt + 1}/2): {exc}")
            if attempt < 1:
                time.sleep(2)
    return []


def _extract_city(address: str) -> str:
    """Extract city from an address string."""
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else ""


def _scrape_website(website: str) -> dict:
    """Scrape contact page for phones/emails."""
    if not website:
        return {}
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = [
        website.rstrip("/") + "/contact-us",
        website.rstrip("/") + "/contact",
        website,
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code != 200:
                continue
            text = BeautifulSoup(resp.text, "html.parser").get_text()
            phones = re.findall(r'(?:\+91[-\s]?)?[6-9]\d{9}|1800[-\s]\d{3}[-\s]\d{4}', text)
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            emails = [re.split(r'[^a-zA-Z0-9._%+-@]', e)[0] for e in emails]  # strip trailing junk
            emails = [e for e in emails if '@' in e and '.' in e.split('@')[-1] and not any(x in e.lower() for x in ["example", "noreply", "test", "support", "info@", "contact@", "care@"])]
            if phones or emails:
                return {"phone": phones[0] if phones else "", "email": emails[0] if emails else ""}
        except Exception:
            continue
    return {}


def _get_domain(website: str) -> str:
    """Extract clean domain from website URL."""
    if not website:
        return ""
    domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    return domain.lower()


def _hunter_domain_search(domain: str) -> dict | None:
    """Hunter Domain Search for management emails."""
    if not HUNTER_API_KEY or not domain:
        return None
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": 3},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        emails = data.get("data", {}).get("emails", [])
        if emails:
            # Prefer management titles
            for e in emails:
                pos = e.get("position", "").lower()
                if any(t in pos for t in ["ceo", "md", "director", "manager", "head", "vp", "president"]):
                    return {
                        "email": e.get("value", "").strip().lower(),
                        "name": e.get("first_name", "") + " " + e.get("last_name", ""),
                        "role": e.get("position", "").strip(),
                        "source": "hunter",
                    }
            # Fallback: first email
            e = emails[0]
            return {
                "email": e.get("value", "").strip().lower(),
                "name": e.get("first_name", "") + " " + e.get("last_name", ""),
                "role": e.get("position", "").strip(),
                "source": "hunter",
            }
    except Exception as exc:
        print(f"  Hunter error for {domain}: {exc}")
    return None


def _build_search_queries(domain: str, location: str) -> list[str]:
    """Build Serper search queries based on domain and location."""
    if domain.lower() == "medical":
        return [
            f"hospitals near {location}",
            f"eye hospitals near {location}",
            f"dental clinics near {location}",
            f"multispecialty hospitals {location}",
            f"cancer hospitals {location}",
            f"diagnostic centre {location}",
            f"Apollo Fortis Max hospital {location}",
        ]
    else:  # Defence
        return [
            f"BSF headquarters {location}",
            f"CRPF headquarters {location}",
            f"Indian Army corps headquarters {location}",
            f"CISF headquarters {location}",
            f"NDRF battalions {location}",
            f"Indian Air Force base {location}",
            f"Defence PSU {location}",
        ]





def find_leads(domain: str, locations: list[str]) -> list[dict]:
    """Find organizations via Serper, then enrich with Hunter/scraping.

    Args:
        domain: "Defence" or "Medical".
        locations: List of geography strings (e.g., ["Delhi", "Noida"]).

    Returns:
        List of deduplicated lead dicts.
    """
    if not SERPER_API_KEY:
        print("Warning: SERPER_API_KEY not set. Skipping lead discovery.")
        return []

    all_leads: list[dict] = []
    seen_names: set[str] = set()

    for location in locations:
        location = location.strip()
        if not location:
            continue

        queries = _build_search_queries(domain, location)

        for query in queries:
            if len(all_leads) >= MAX_SENDS_PER_RUN:
                break

            print(f"\n🔍 Searching: {query}")
            places = _serper_search(query)
            if not places:
                time.sleep(1)
                continue

            for place in places:
                org_name = place.get("name", "")
                if not org_name or org_name in seen_names:
                    continue
                seen_names.add(org_name)

                website = place.get("website", "")
                org_domain = _get_domain(website)
                city = place.get("city", location)

                print(f"  [{org_name}] → {website or 'no website'}")

                # Hunter enrichment (with rate limit delay)
                time.sleep(2.5)
                hunter_data = _hunter_domain_search(org_domain) if org_domain else None

                # Website scraping
                scraped = _scrape_website(website) if website else {}

                # Build lead
                email = ""
                name = ""
                role = ""
                source = ""

                if hunter_data and hunter_data.get("email"):
                    email = hunter_data["email"]
                    name = hunter_data["name"].strip()
                    role = hunter_data["role"]
                    source = "hunter"
                    print(f"    ✅ Hunter: {email} ({role})")

                if not email and scraped.get("email"):
                    email = scraped["email"].strip().lower()
                    source = "scraped"
                    print(f"    ✅ Scraped: {email}")

                if not email:
                    print(f"    ⚠️ No email found")
                    continue  # Skip if no email — can't outreach

                lead = {
                    "name": name or org_name,
                    "email": email,
                    "phone": place.get("phone", "") or scraped.get("phone", ""),
                    "organization": org_name,
                    "organization_domain": org_domain,
                    "role": role,
                    "category": domain,
                    "linkedin_url": "",
                    "city": city,
                    "country": "India",
                    "apollo_id": f"serper-{hash(org_name) % 100000000}",  # fake ID for dedup
                    "source": source,
                }
                all_leads.append(lead)
                print(f"    ✅ Lead added: {email}")

                if len(all_leads) >= MAX_SENDS_PER_RUN:
                    break

            time.sleep(1)

        if len(all_leads) >= MAX_SENDS_PER_RUN:
            break

    insert_leads(all_leads)
    print(f"\n{'=' * 50}")
    print(f"Serper + Hunter found {len(all_leads)} new leads for {domain} in {locations}")
    print(f"{'=' * 50}")
    return all_leads
