"""Medical Tourism Scraper — Serper web search + Apollo.io enrichment + website scraping.

Finds medical tourism facilitators, dental tourism companies, travel agencies,
international patient coordinators, and India-based dental tourism operators
across Canada, India, and UAE.
"""

import os
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")

SERPER_SEARCH_URL = "https://google.serper.dev/search"
APOLLO_SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"

# ── Regex helpers ─────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"^[^@\s]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
EMAIL_RE_LOOSE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# ── Priority → Search Queries ─────────────────────────────────────────────────

PRIORITY_QUERIES: dict[str, list[str]] = {
    "P1": [  # Medical Tourism Facilitators
        "medical tourism facilitator Canada",
        "medical tourism facilitator India",
        "medical tourism facilitator UAE",
        "health tourism coordinator Canada",
        "international patient services India",
    ],
    "P2": [  # Dental Tourism Companies
        "dental tourism company Canada",
        "dental tourism company India",
        "dental implants abroad Canada",
        "dental tourism packages India",
        "cosmetic dentistry tourism UAE",
    ],
    "P3": [  # Travel Agencies Medical Travel
        "medical travel agency Canada",
        "healthcare travel agency India",
        "medical travel facilitator UAE",
    ],
    "P4": [  # International Patient Coordinators
        "international patient coordinator Canada",
        "patient concierge medical India",
        "medical visa support UAE",
    ],
    "P5": [  # India-Based Dental Tourism
        "dental tourism India",
        "dental tourism facilitator India",
        "international dental patients India",
    ],
}


def get_all_queries() -> list[tuple[str, str]]:
    """Return flat list of (priority, query) tuples covering all priorities."""
    out = []
    for priority, queries in PRIORITY_QUERIES.items():
        for q in queries:
            out.append((priority, q))
    return out


def get_default_queries() -> list[str]:
    """Return all default search queries."""
    return [q for _, qs in PRIORITY_QUERIES.items() for q in qs]


# ── Serper Web Search ─────────────────────────────────────────────────────────


def _extract_domain(url: str) -> str:
    """Extract clean domain from a URL."""
    if not url:
        return ""
    url = url.strip()
    for prefix in ("https://", "http://", "https://www.", "http://www."):
        if url.startswith(prefix):
            url = url[len(prefix) :]
    domain = url.split("/")[0].split("?")[0]
    return domain.lower()


def _search_serper(query: str) -> list[dict]:
    """Call Serper Google Search API. Return organic results as dicts."""
    if not SERPER_API_KEY:
        print("[medtour] SERPER_API_KEY not set — skipping")
        return []
    try:
        resp = requests.post(
            SERPER_SEARCH_URL,
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 20},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("organic", []):
            link = (item.get("link") or "").strip()
            domain = _extract_domain(link)
            if not domain or domain in (
                "google.com",
                "maps.google.com",
                "youtube.com",
                "google.co.in",
                "google.ca",
                "google.ae",
            ):
                continue
            results.append(
                {
                    "title": (item.get("title") or "").strip(),
                    "domain": domain,
                    "website": f"https://{domain}" if domain else "",
                    "description": (item.get("snippet") or "").strip(),
                    "link": link,
                }
            )
        return results
    except Exception as exc:
        print(f"[medtour] Serper error for '{query}': {exc}")
        return []


# ── Apollo.io Enrichment (free plan: org data only) ───────────────────────────

APOLLO_ORG_ENRICH_URL = "https://api.apollo.io/v1/organizations/enrich"


def _enrich_company_via_apollo(domain: str) -> dict:
    """Enrich company metadata via Apollo.io free endpoint.

    Returns dict with social links, founded_year, estimated_num_employees,
    industry, and primary_phone (all available on free plan).
    """
    if not APOLLO_API_KEY or not domain:
        return {}
    clean_domain = domain.lower().removeprefix("www.").strip()
    if not clean_domain:
        return {}
    try:
        payload = {"api_key": APOLLO_API_KEY, "domain": clean_domain}
        resp = requests.post(
            APOLLO_ORG_ENRICH_URL,
            headers={"Content-Type": "application/json", "X-Api-Key": APOLLO_API_KEY},
            json=payload,
            timeout=15,
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        org = data.get("organization", {})
        result = {}
        # Social links
        for key in ("linkedin_url", "twitter_url", "facebook_url", "angellist_url", "crunchbase_url"):
            val = org.get(key)
            if val:
                result[key.replace("_url", "")] = val
        # Phone
        phone = org.get("primary_phone")
        if isinstance(phone, str) and phone.strip():
            result["phone"] = phone.strip()
        elif isinstance(phone, dict):
            phone_str = phone.get("number") or phone.get("raw_number") or ""
            if phone_str.strip():
                result["phone"] = phone_str.strip()
        # Metadata
        for key in ("founded_year", "estimated_num_employees", "industry"):
            val = org.get(key)
            if val not in (None, "", 0):
                result[key] = val
        return result
    except Exception as exc:
        print(f"[medtour] Apollo org enrich error for '{domain}': {exc}")
        return {}


# ── Website Scraping ──────────────────────────────────────────────────────────


# Keywords that flag India relevance
INDIA_KEYWORDS = {
    "india", "delhi", "mumbai", "bangalore", "bengaluru", "chennai",
    "hyderabad", "kolkata", "pune", "ahmedabad", "jaipur", "goa",
    "kerala", "trivandrum", "indian hospital", "india medical",
    "medical tourism india", "treatment in india", "healthcare india",
    "indian healthcare", "india travel",
}

# Keywords that flag dental relevance
DENTAL_KEYWORDS = {
    "dental", "dentist", "tooth", "teeth", "implant", "implants",
    "cosmetic dentistry", " veneers ", "crown", "crowns",
    "bridge", "bridges", "root canal", "orthodontist", "braces",
    "invisalign", "smile makeover", "teeth whitening", "all-on-4",
    "all-on-6", "full mouth reconstruction", "oral surgery",
    "periodontist", "endodontist", "pediatric dentist",
    "dental tourism", "affordable dentistry", "dental holiday",
    "dental clinic abroad", "dental vacation",
}

# Trust / accreditation keywords
TRUST_KEYWORDS = {
    "jci", "nabh", "nabc", "iso ", "iso-", "hipaa compliant",
    "joint commission", "medical tourism association",
    "international society", "accredited ", "certified ",
    "years in business", "established", "since 19", "since 20",
}

# Social link patterns
_SOCIAL_PATTERNS = {
    "linkedin": re.compile(r"linkedin\.com/company/([^/\?]+)", re.IGNORECASE),
    "facebook": re.compile(r"facebook\.com/([^/\?]+)", re.IGNORECASE),
    "instagram": re.compile(r"instagram\.com/([^/\?]+)", re.IGNORECASE),
    "youtube": re.compile(r"youtube\.com/([^/\?]+)", re.IGNORECASE),
}


def _scrape_website(domain: str) -> dict:
    """Fetch org website and extract emails, phones, social links, service keywords."""
    found_emails: set[str] = set()
    found_phones: set[str] = set()
    linkedin = ""
    facebook = ""
    instagram = ""
    youtube = ""
    services: list[str] = []
    accreditations: list[str] = []
    india_related = False
    dental_related = False

    urls_to_try = [
        f"https://{domain}",
        f"https://www.{domain}",
        f"http://{domain}",
        f"http://www.{domain}",
    ]

    # Also try /about, /about-us, /contact, /contact-us
    for base in urls_to_try[:2]:
        urls_to_try.extend([f"{base.rstrip('/')}/about", f"{base.rstrip('/')}/about-us",
                            f"{base.rstrip('/')}/contact", f"{base.rstrip('/')}/contact-us"])

    seen_urls: set[str] = set()
    for url in urls_to_try:
        if url in seen_urls or len(seen_urls) >= 6:
            continue
        seen_urls.add(url)
        try:
            resp = requests.get(
                url,
                timeout=8,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; FermentBot/1.0; +https://irus.ind.in)"
                    )
                },
            )
            if resp.status_code not in (200, 301, 302):
                continue
            text = resp.text
            soup = BeautifulSoup(text, "html.parser")

            # Emails from mailto: links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("mailto:"):
                    email = href.replace("mailto:", "").split("?")[0].strip()
                    if email and EMAIL_RE.match(email):
                        found_emails.add(email.lower())

            # All emails from raw text
            for match in EMAIL_RE_LOOSE.findall(text):
                e = match.strip().lower()
                if not e or "@" not in e:
                    continue
                # Skip garbage
                if any(
                    bad in e
                    for bad in (
                        "example.com",
                        "test@",
                        "domain.com",
                        "localhost",
                        ".png",
                        ".jpg",
                        ".gif",
                        ".svg",
                        ".webp",
                    )
                ):
                    continue
                if len(e) > 80 or len(e.split("@")[0]) > 50:
                    continue
                found_emails.add(e)

            # Phone numbers
            phone_pattern = re.compile(
                r"(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}"
                r"|(?:\+?91[-\s]?)?[6-9]\d{9}"
                r"|(?:00|\+)?[1-9]\d[\s.-]?\d{4}[\s.-]?\d{4}"
            )
            for phone in phone_pattern.findall(text):
                cleaned = re.sub(r"[^\d+]", "", phone)
                if 7 <= len(cleaned) <= 20:
                    found_phones.add(cleaned)

            # Social links from anchor hrefs
            for a in soup.find_all("a", href=True):
                href = a["href"]
                for key, pattern in _SOCIAL_PATTERNS.items():
                    m = pattern.search(href)
                    if m and not locals()[key]:
                        locals()[key] = f"https://{key}.com/{m.group(1)}"
                        break
            for meta in soup.find_all("meta"):
                content = (meta.get("content") or "").strip()
                for key, pattern in _SOCIAL_PATTERNS.items():
                    if not locals()[key] and pattern.search(content):
                        m = pattern.search(content)
                        if m:
                            setattr(
                                _SOCIAL_PATTERNS, key, type(pattern)(pattern.pattern, pattern.flags)
                            )
                            # simple reassign
                            if key == "linkedin":
                                linkedin = content if "linkedin.com" in content.lower() else ""
                            break

            # Keyword detection in page text (case-insensitive)
            text_lower = text.lower()
            for kw in INDIA_KEYWORDS:
                if kw in text_lower:
                    india_related = True
                    break
            for kw in DENTAL_KEYWORDS:
                if kw in text_lower:
                    dental_related = True
                    break
            for kw in TRUST_KEYWORDS:
                if kw in text_lower:
                    accreditations.append(kw.strip())

            # Extract visible services from lists
            for ul in soup.find_all(["ul", "ol"]):
                items = [li.get_text(strip=True) for li in ul.find_all("li", recursive=False)]
                if 2 <= len(items) <= 12:  # plausible service list
                    services.extend(items)

            # Also grab meta description for reference
            desc = ""
            for meta in soup.find_all("meta", attrs={"name": "description"}):
                desc = (meta.get("content") or "").strip()
                break

        except Exception:
            continue

    # Clean emails
    cleaned_emails = []
    for email in found_emails:
        e = email.lower().strip()
        local = e.split("@")[0]
        if len(local) > 50:
            continue
        if any(e.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")):
            continue
        if "example" in e or "test@" in e or "domain.com" in e or "%" in e:
            continue
        cleaned_emails.append(e)

    return {
        "emails": cleaned_emails,
        "phones": list(found_phones)[:5],
        "linkedin": linkedin,
        "facebook": facebook,
        "instagram": instagram,
        "youtube": youtube,
        "services": list(dict.fromkeys(services))[:20],
        "accreditations": list(dict.fromkeys(accreditations))[:10],
        "india_related": india_related,
        "dental_related": dental_related,
    }


# ── Outreach Score ────────────────────────────────────────────────────────────


def compute_outreach_score(lead: dict) -> int:
    """Compute outreach score (0–100) for a medical-tourism lead."""
    score = 0

    # Priority bonus
    priority_scores = {"P1": 30, "P2": 25, "P3": 20, "P4": 15, "P5": 10}
    score += priority_scores.get(lead.get("priority", "P3"), 15)

    # Dental relevance
    if lead.get("dental_related"):
        score += 20

    # India relevance
    if lead.get("india_related"):
        score += 20

    # Has domain
    if lead.get("domain"):
        score += 5

    # Has emails (up to +15)
    emails = lead.get("emails", [])
    score += min(len(emails) * 5, 15)

    # Has decision makers (up to +15)
    dms = lead.get("decision_makers", [])
    score += min(len(dms) * 5, 15)

    # Has LinkedIn
    if lead.get("linkedin"):
        score += 5

    # Has phone
    if lead.get("phones"):
        score += 5

    return min(score, 100)


# ── Country / Region Detection ────────────────────────────────────────────────


def _detect_country(query: str) -> str:
    """Detect country from search query."""
    q = query.lower()
    if "canada" in q:
        return "Canada"
    if "uae" in q or "dubai" in q or "abu dhabi" in q:
        return "UAE"
    if "india" in q:
        return "India"
    return ""


def _detect_province(query: str) -> str:
    """Naively detect province/state from query."""
    q = query.lower()
    provinces = {
        "ontario": "Ontario", "ont": "Ontario",
        "british columbia": "British Columbia", "bc": "British Columbia",
        "quebec": "Quebec", "qc": "Quebec",
        "alberta": "Alberta", "ab": "Alberta",
        "manitoba": "Manitoba", "mb": "Manitoba",
        "saskatchewan": "Saskatchewan", "sk": "Saskatchewan",
        "nova scotia": "Nova Scotia", "ns": "Nova Scotia",
        "dubai": "Dubai", "abu dhabi": "Abu Dhabi",
        "sharjah": "Sharjah", "uae": "Dubai",
    }
    for key, val in provinces.items():
        if key in q:
            return val
    return ""


# ── Parallel Website Scrape Helper ───────────────────────────────────────────


def _parallel_scrape(domains: list[str]) -> dict[str, dict]:
    """Scrape multiple domains in parallel. Returns {domain: scrape_result}."""
    results: dict[str, dict] = {}
    unique = list(dict.fromkeys(d for d in domains if d))
    if not unique:
        return results

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_scrape_website, d): d for d in unique}
        for future in futures:
            domain = futures[future]
            try:
                result = future.result(timeout=30)
                results[domain] = result
            except Exception as exc:
                print(f"[medtour] Website scrape error for {domain}: {exc}")
    return results


# ── Main Orchestrator ─────────────────────────────────────────────────────────


def run_medical_tourism_scrape(
    queries: list[str] | None = None,
    max_per_priority: int = 50,
) -> dict[str, Any]:
    """Run full medical tourism scraping pipeline.

    Args:
        queries: Optional list of search queries. If None, uses all default
                 queries across all 5 priority categories.
        max_per_priority: Max results to save per priority tier (cap on DB growth).

    Returns: {"scraped": int, "saved": int, "skipped": int, "errors": int}
    """
    from db import save_medical_tourism_lead, init_medical_tourism_tables

    # Ensure DB table exists
    init_medical_tourism_tables()

    # Resolve queries
    if queries:
        priority_map: dict[str, str] = {}
        for priority, qs in PRIORITY_QUERIES.items():
            for q in qs:
                if q in queries:
                    priority_map[q] = priority
        # Any query not mapped, default to P3
        run_queries = [(priority_map.get(q, "P3"), q) for q in queries]
    else:
        run_queries = get_all_queries()

    scraped = 0
    saved = 0
    skipped = 0
    errors = 0
    seen_domains: set[str] = set()
    saved_per_priority: dict[str, int] = {p: 0 for p in PRIORITY_QUERIES}

    for priority, query in run_queries:
        print(f"\n[medtour] [{priority}] Searching: {query}")
        time.sleep(0.5)  # Be gentle on Serper

        results = _search_serper(query)
        scraped += len(results)
        print(f"[medtour]   Found {len(results)} organic results")

        if not results:
            continue

        # Deduplicate by domain
        new_results = [r for r in results if r["domain"] and r["domain"] not in seen_domains]
        print(f"[medtour]   {len(new_results)} new (after dedup)")

        # Collect domains for parallel scraping
        all_domains = [r["domain"] for r in new_results if r["domain"]]
        if not all_domains:
            continue

        # Step 1: Parallel website scraping
        print(f"[medtour]   Scraping {len(all_domains)} websites...")
        scrape_results = _parallel_scrape(all_domains)

        # Step 2: Apollo enrichment for each org (sequential to avoid rate limits)
        apollo_results: dict[str, list[dict]] = {}
        for result in new_results:
            domain = result["domain"]
            if not domain:
                continue
            print(f"[medtour]   Apollo enriching: {domain}")
            time.sleep(0.3)
            dms = _search_apollo_by_domain(domain, result.get("title", ""))
            if dms:
                apollo_results[domain] = dms
                print(f"[medtour]     Found {len(dms)} decision maker(s)")

        # Step 3: Build leads and save
        for result in new_results:
            domain = result["domain"]
            if domain in seen_domains:
                continue

            # Check per-priority cap
            if saved_per_priority.get(priority, 0) >= max_per_priority:
                print(f"[medtour]   Skipping {domain} — {priority} cap reached ({max_per_priority})")
                skipped += 1
                continue

            title = result.get("title", "")
            scrape_data = scrape_results.get(domain, {})
            dms = apollo_results.get(domain, [])

            # Detect India/dental relevance from description if not found by scraping
            desc_lower = (result.get("description", "") or "").lower()
            scrape_data.setdefault("india_related", False)
            scrape_data.setdefault("dental_related", False)
            if not scrape_data["india_related"]:
                scrape_data["india_related"] = any(kw in desc_lower for kw in INDIA_KEYWORDS)
            if not scrape_data["dental_related"]:
                scrape_data["dental_related"] = any(kw in desc_lower for kw in DENTAL_KEYWORDS)

            # Merge Apollo decision maker emails into email list if not already found
            all_emails = list(scrape_data.get("emails", []))
            seen_emails_set = set(all_emails)
            for dm in dms:
                if dm.get("email") and dm["email"] not in seen_emails_set:
                    all_emails.append(dm["email"])
                    seen_emails_set.add(dm["email"])

            # Skip if no contact info at all
            if not all_emails and not dms:
                print(f"  SKIP: no_contact — {title} ({domain})")
                skipped += 1
                continue

            # Compute outreach score
            lead = {
                "company_name": title,
                "website": result.get("website", ""),
                "domain": domain,
                "description": result.get("description", ""),
                "country": _detect_country(query),
                "province": _detect_province(query),
                "city": "",
                "address": "",
                "postal_code": "",
                "emails": all_emails,
                "phones": scrape_data.get("phones", []),
                "whatsapp_numbers": [],
                "linkedin": scrape_data.get("linkedin", ""),
                "facebook": scrape_data.get("facebook", ""),
                "instagram": scrape_data.get("instagram", ""),
                "youtube": scrape_data.get("youtube", ""),
                "decision_makers": dms,
                "services": scrape_data.get("services", []),
                "india_related": scrape_data.get("india_related", False),
                "dental_related": scrape_data.get("dental_related", False),
                "hospital_partners": [],
                "clinic_partners": [],
                "accreditations": scrape_data.get("accreditations", []),
                "testimonials_count": 0,
                "outreach_score": 0,  # compute below
                "priority": priority,
                "scrape_query": query,
                "status": "new",
            }

            lead["outreach_score"] = compute_outreach_score(lead)
            seen_domains.add(domain)

            if save_medical_tourism_lead(lead):
                saved += 1
                saved_per_priority[priority] = saved_per_priority.get(priority, 0) + 1
                print(
                    f"  [+] Saved ({priority}, score={lead['outreach_score']}): "
                    f"{title} | {domain} | emails={len(all_emails)} | dms={len(dms)}"
                )
            else:
                print(f"  SKIP: duplicate_domain — {domain}")
                skipped += 1

    print(
        f"\n[medtour] Done — scraped {scraped}, saved {saved}, "
        f"skipped {skipped}, errors {errors}"
    )
    print(f"[medtour] Saved per priority: {saved_per_priority}")
    return {"scraped": scraped, "saved": saved, "skipped": skipped, "errors": errors}


# ── CLI ───────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys

    queries = sys.argv[1:] if len(sys.argv) > 1 else None
    print(f"[medtour] Starting{' custom queries: ' + str(queries) if queries else ' all default queries'}")
    run_medical_tourism_scrape(queries=queries)