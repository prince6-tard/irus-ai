"""Dental Connect — scrapes medical tourism facilitators via Serper web search + Hunter.io."""

import os
import re
import time
from typing import Any

import requests
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")

_SERPER_SEARCH_URL = "https://google.serper.dev/search"
_HUNTER_URL = "https://api.hunter.io/v2/domain-search"

EMAIL_RE = re.compile(r"^[^@\s]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
EMAIL_RE_LOOSE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

_hunter_rate_limited = False

_COMMON_LOCAL_PARTS = [
    "info", "contact", "admin", "hello", "reception",
    "office", "clinic", "dental", "enquiries", "bookings",
    "appointments", "dr", "doctor", "team", "support", "care",
]

# ── Location parsing helpers ─────────────────────────────────────────────────

_COUNTRIES = {
    "canada": "Canada",
    "usa": "USA",
    "us": "USA",
    "united states": "USA",
    "uk": "UK",
    "united kingdom": "UK",
    "germany": "Germany",
    "france": "France",
    "uae": "UAE",
    "dubai": "UAE",
    "abu dhabi": "UAE",
    "india": "India",
    "australia": "Australia",
    "new zealand": "New Zealand",
    "kuwait": "Kuwait",
    "ireland": "Ireland",
    "netherlands": "Netherlands",
}

_CITIES = {
    "toronto": "Toronto",
    "vancouver": "Vancouver",
    "montreal": "Montreal",
    "calgary": "Calgary",
    "ottawa": "Ottawa",
    "edmonton": "Edmonton",
    "winnipeg": "Winnipeg",
    "quebec city": "Quebec City",
    "hamilton": "Hamilton",
    "kitchener": "Kitchener",
    "london": "London",
    "victoria": "Victoria",
    "halifax": "Halifax",
    "mississauga": "Mississauga",
    "brampton": "Brampton",
    "surrey": "Surrey",
    "new york": "New York",
    "los angeles": "Los Angeles",
    "chicago": "Chicago",
    "dubai": "Dubai",
    "abu dhabi": "Abu Dhabi",
    "delhi": "Delhi",
    "mumbai": "Mumbai",
    "bangalore": "Bangalore",
    "berlin": "Berlin",
    "munich": "Munich",
    "frankfurt": "Frankfurt",
    "sydney": "Sydney",
    "melbourne": "Melbourne",
    "auckland": "Auckland",
    "wellington": "Wellington",
    "dublin": "Dublin",
    "amsterdam": "Amsterdam",
}


def _parse_city_country(query: str) -> tuple[str, str]:
    """Extract city and country from query using keyword matching."""
    q = query.lower().strip()
    country = ""
    city = ""

    # Detect country
    for key, val in sorted(_COUNTRIES.items(), key=lambda x: -len(x[0])):
        if key in q:
            country = val
            break

    # Detect city
    for key, val in sorted(_CITIES.items(), key=lambda x: -len(x[0])):
        if key in q:
            city = val
            break

    return city, country


# ── Web search ───────────────────────────────────────────────────────────────

_GOOGLE_DOMAINS = {
    "google.com", "maps.google.com", "youtube.com", "google.co.in",
    "google.ca", "google.ae", "google.co.uk", "google.de",
}

# Domains that are not facilitator organisations and should be excluded from search results
_BLOCKED_SEARCH_DOMAINS = {
    "facebook.com", "twitter.com", "x.com", "instagram.com", "linkedin.com",
    "wikipedia.org", "wikimedia.org",
    "nih.gov", "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov",
    "springer.com", "link.springer.com", "nature.com",
    "reddit.com", "quora.com", "yelp.com", "tripadvisor.com",
    "scholar.google.com", "books.google.com",
}


def _extract_domain(url: str) -> str:
    """Extract clean domain from a URL."""
    if not url:
        return ""
    url = url.strip()
    for prefix in ("https://", "http://", "https://www.", "http://www."):
        if url.startswith(prefix):
            url = url[len(prefix):]
    domain = url.split("/")[0].split("?")[0]
    return domain.lower()


def _search_serper_web(query: str) -> list[dict]:
    """Call Serper Google Search API. Return organic results as dicts."""
    if not SERPER_API_KEY:
        print("[dental_scraper] SERPER_API_KEY not set")
        return []
    try:
        resp = requests.post(
            _SERPER_SEARCH_URL,
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
            if not domain or domain in _GOOGLE_DOMAINS or domain in _BLOCKED_SEARCH_DOMAINS:
                continue
            results.append({
                "title": (item.get("title") or "").strip(),
                "domain": domain,
                "website": f"https://{domain}" if domain else "",
                "description": (item.get("snippet") or "").strip(),
                "link": link,
            })
        return results
    except Exception as exc:
        print(f"[dental_scraper] Serper web error for '{query}': {exc}")
        return []


# ── Hunter.io ────────────────────────────────────────────────────────────────


def _find_emails_via_hunter(domain: str) -> dict:
    """Call Hunter.io domain-search. Return dict with email, email_source, linkedin_url."""
    global _hunter_rate_limited
    email = None
    email_source = ""
    linkedin_url = ""
    if _hunter_rate_limited or not HUNTER_API_KEY or not domain:
        return {"email": email, "email_source": email_source, "linkedin_url": linkedin_url}
    try:
        resp = requests.get(
            _HUNTER_URL,
            params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": 3},
            timeout=30,
        )
        if resp.status_code == 429:
            _hunter_rate_limited = True
            print("[dental_scraper] Hunter rate limit (429) detected. Disabling Hunter for this batch.")
            return {"email": email, "email_source": email_source, "linkedin_url": linkedin_url}
        resp.raise_for_status()
        data = resp.json()
        emails = data.get("data", {}).get("emails", [])
        for e in emails:
            candidate = (e.get("value") or "").strip()
            if candidate and EMAIL_RE.match(candidate):
                email = candidate
                email_source = "hunter"
                linkedin_url = (e.get("linkedin_url") or "").strip()
                break
    except Exception as exc:
        print(f"[dental_scraper] Hunter error for '{domain}': {exc}")
    return {"email": email, "email_source": email_source, "linkedin_url": linkedin_url}


# ── Website scraping ─────────────────────────────────────────────────────────


def _scrape_website(domain: str) -> dict:
    """Fetch org website and extract emails, phones, and social links."""
    found_emails: set[str] = set()
    found_phones: set[str] = set()
    linkedin_url = ""

    urls_to_try = [
        f"https://{domain}",
        f"https://www.{domain}",
        f"http://{domain}",
        f"http://www.{domain}",
    ]

    # Also try common contact pages
    for base in urls_to_try[:2]:
        base = base.rstrip("/")
        urls_to_try.extend([
            f"{base}/about",
            f"{base}/about-us",
            f"{base}/contact",
            f"{base}/contact-us",
        ])

    seen_urls: set[str] = set()
    for url in urls_to_try:
        if url in seen_urls or len(seen_urls) >= 6:
            continue
        seen_urls.add(url)
        try:
            resp = requests.get(
                url,
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0 (compatible; IRUSBot/1.0; +https://irus.ind.in)"},
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
                if any(
                    bad in e
                    for bad in (
                        "example.com", "test@", "domain.com", "localhost",
                        ".png", ".jpg", ".gif", ".svg", ".webp",
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
            )
            for phone in phone_pattern.findall(text):
                cleaned = re.sub(r"[^\d+]", "", phone)
                if 7 <= len(cleaned) <= 20:
                    found_phones.add(cleaned)

            # LinkedIn URLs from anchor hrefs
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                if "linkedin.com" in href and href.startswith("http"):
                    if not linkedin_url:
                        linkedin_url = href

            # LinkedIn from meta/link tags
            for meta in soup.find_all("meta"):
                content = (meta.get("content") or "").strip()
                if "linkedin.com" in content.lower() and content.startswith("http"):
                    if not linkedin_url:
                        linkedin_url = content

        except Exception:
            continue

    # Clean emails
    cleaned_emails = []
    for email in found_emails:
        e = email.strip()
        if len(e) > 80 or len(e.split("@")[0]) > 50:
            continue
        if any(e.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".css", ".js")):
            continue
        # Skip placeholder / tracking / analytics emails
        if any(bad in e for bad in ("example.com", "test@", "domain.com", "localhost", "@2x", "%")):
            continue
        # Skip known tracking / analytics domains
        if any(bad in e for bad in ("sentry.wixpress.com", "sentry.io", "bugsnag.com", "logrocket.com", "datadoghq.com", "facebook.com", "twitter.com", "instagram.com", "youtube.com")):
            continue
        # Skip suspiciously long local parts (UUIDs)
        local = e.split("@")[0]
        if len(local) >= 20 and all(c in "0123456789abcdef" for c in local):
            continue
        cleaned_emails.append(e)

    return {
        "emails": cleaned_emails,
        "phone": list(found_phones)[0] if found_phones else "",
        "linkedin_url": linkedin_url,
    }


# ── Email guessing ───────────────────────────────────────────────────────────


def _guess_emails_from_domain(domain: str) -> list[str]:
    """Generate likely email addresses from a domain using common local parts."""
    clean_domain = domain.removeprefix("www.")
    guesses = []
    for local in _COMMON_LOCAL_PARTS:
        guesses.append(f"{local}@{clean_domain}")
    return guesses


def _guess_emails_from_title(title: str, domain: str) -> list[str]:
    """Extract first/last name from title and generate email patterns."""
    clean_domain = domain.removeprefix("www.")
    guesses = []
    if not title or not clean_domain:
        return guesses
    name_part = re.sub(
        r"\b(dental|clinic|center|centre|practice|office|group|team|hospital|medical|health|care|staff|doctors|dentists|facilitator|tourism|travel|agency)\b",
        "", title, flags=re.IGNORECASE
    )
    words = re.findall(r"\b[A-Z][a-z]+\b", name_part)
    filtered = [w for w in words if w.lower() not in ("dr", "the", "and", "for", "dental", "clinic", "center")]
    if len(filtered) >= 2:
        first = filtered[0].lower()
        last = filtered[-1].lower()
        guesses.extend([
            f"{first}.{last}@{clean_domain}",
            f"{first}{last}@{clean_domain}",
            f"{first[0]}{last}@{clean_domain}",
            f"{first}@{clean_domain}",
        ])
    elif len(filtered) == 1:
        guesses.extend([f"{filtered[0].lower()}@{clean_domain}"])
    return guesses


# ── Main orchestrator ────────────────────────────────────────────────────────


def run_dental_scrape(queries: list[str]) -> dict[str, Any]:
    """Run full facilitator scraping pipeline for a list of queries.

    Uses Serper web search + website scraping + Hunter.io enrichment.

    Returns: {"scraped": int, "saved": int, "skipped": int}
    """
    from db import save_dental_lead

    scraped = 0
    saved = 0
    skipped = 0
    seen_emails: set[str] = set()

    for query in queries:
        print(f"[dental_scraper] Searching: {query}")
        results = _search_serper_web(query)
        city, country = _parse_city_country(query)
        scraped += len(results)
        print(f"[dental_scraper]   Found {len(results)} organic results")

        if not results:
            continue

        # Step 1: Enrichment pass — try Hunter.io for each domain
        enriched = []
        for result in results:
            domain = result.get("domain", "").strip()
            email = None
            email_source = ""
            linkedin_url = ""

            if domain and not _hunter_rate_limited:
                hunter_result = _find_emails_via_hunter(domain)
                email = hunter_result.get("email")
                email_source = hunter_result.get("email_source", "")
                linkedin_url = hunter_result.get("linkedin_url", "")
                time.sleep(0.3)

            enriched.append({
                "result": result,
                "domain": domain,
                "email": email,
                "email_source": email_source,
                "linkedin_url": linkedin_url,
                "city": city,
                "country": country,
            })

        # Step 2: Parallel website scraping for all domains
        all_domains = [item["domain"] for item in enriched if item["domain"]]
        unique_all_domains = list(dict.fromkeys(all_domains))
        website_results: dict[str, dict] = {}

        if unique_all_domains:
            print(f"[dental_scraper] Scraping {len(unique_all_domains)} websites for emails + LinkedIn...")
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(_scrape_website, d): d for d in unique_all_domains}
                for future in futures:
                    domain = futures[future]
                    try:
                        website_results[domain] = future.result(timeout=20)
                    except Exception as exc:
                        print(f"[dental_scraper] Website scrape error for {domain}: {exc}")

        # Step 3: Build leads and save
        for item in enriched:
            result = item["result"]
            domain = item["domain"]
            email = item["email"]
            email_source = item["email_source"]
            linkedin_url = item.get("linkedin_url", "")
            phone = ""

            # Merge website data
            if domain and domain in website_results:
                scrape_data = website_results[domain]
                if not linkedin_url:
                    linkedin_url = scrape_data.get("linkedin_url", "")
                if not email:
                    for candidate in scrape_data.get("emails", []):
                        if EMAIL_RE.match(candidate):
                            email = candidate
                            email_source = "website"
                            break
                if not phone:
                    phone = scrape_data.get("phone", "")

            if not email:
                # Last resort: pattern guessing
                title = result.get("title", "")
                for candidate in _guess_emails_from_title(title, domain):
                    if EMAIL_RE.match(candidate):
                        email = candidate
                        email_source = "guessed"
                        break
                if not email:
                    for candidate in _guess_emails_from_domain(domain):
                        if EMAIL_RE.match(candidate):
                            email = candidate
                            email_source = "guessed"
                            break

            if not email:
                if domain:
                    print(f"  SKIPPED: no_email — {result.get('title', '')} ({domain})")
                else:
                    print(f"  SKIPPED: no_domain — {result.get('title', '')}")
                skipped += 1
                continue

            # Deduplicate within this run
            if email.lower() in seen_emails:
                print(f"  SKIPPED: duplicate_email:{email} — {domain}")
                continue

            lead = {
                "name": result.get("title", ""),
                "email": email,
                "email_source": email_source,
                "phone": phone,
                "organization": result.get("title", ""),
                "organization_domain": domain,
                "linkedin_url": linkedin_url,
                "city": item["city"],
                "country": item["country"],
                "scrape_query": query,
                "status": "new",
            }

            if save_dental_lead(lead):
                saved += 1
                seen_emails.add(email.lower())
                print(f"  [+] Saved: {email} ({domain})")
            else:
                print(f"  SKIPPED: duplicate_email:{email} — {domain}")

    print(f"[dental_scraper] Done — scraped {scraped}, saved {saved}, skipped {skipped}")
    return {"scraped": scraped, "saved": saved, "skipped": skipped}
