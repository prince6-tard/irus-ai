"""Tunable parameters for the IRUS AI Outreach Pipeline."""

import os

# ── Project Root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Apollo search filters ─────────────────────────────────────────────────────
DEFENCE_JOB_TITLES = [
    "Director Procurement", "Commandant", "Deputy Inspector General",
    "Equipment Acquisition Officer", "Chief of Staff", "Director General",
    "Head of Logistics", "Defence Attaché", "Procurement Officer",
    "Director Operations", "General Manager Defence", "VP Defence",
]

MEDICAL_JOB_TITLES = [
    "Chief Medical Officer", "Head of Telemedicine", "Program Director",
    "Hospital Administrator", "Director Health Services", "CEO",
    "Medical Superintendent", "Director Community Health", "VP Healthcare",
    "Head of Nursing", "Dean Medical College", "Director Rural Health",
]

DEFENCE_INDUSTRIES = [
    "Defense & Space", "Government Administration",
    "Law Enforcement", "Security & Investigations",
]

MEDICAL_INDUSTRIES = [
    "Hospital & Health Care", "Medical Devices",
    "Non-profit Organization Management", "Government Administration",
    "Health, Wellness & Fitness",
]

# ── Lead volume ───────────────────────────────────────────────────────────────
MAX_DEFENCE_LEADS = 100
MAX_MEDICAL_LEADS = 100
APOLLO_PER_PAGE = 25

# ── xAI Model ─────────────────────────────────────────────────────────────────
XAI_MODEL = "grok-3-latest"
XAI_MAX_TOKENS = 600

# ── Enrichment & Sending ──────────────────────────────────────────────────────
ENRICH_WITH_HUNTER = True
DRY_RUN = True
REVIEW_BEFORE_SEND = True  # True = draft only, queue for manual review
DELAY_MIN_SECONDS = 60
DELAY_MAX_SECONDS = 120
MAX_SENDS_PER_RUN = 50

# ── Logging ───────────────────────────────────────────────────────────────────
LEADS_RAW_FILE = os.path.join(PROJECT_ROOT, "leads_raw.csv")
LEADS_ENRICHED_FILE = os.path.join(PROJECT_ROOT, "leads_enriched.csv")
LOG_FILE = os.path.join(PROJECT_ROOT, "log.csv")
EMAIL_DRAFTS_FILE = os.path.join(PROJECT_ROOT, "email_drafts.csv")
PRODUCTS_FILE = os.path.join(PROJECT_ROOT, "irus_products.csv")
