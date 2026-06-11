"""FastAPI application for the IRUS AI Outreach Pipeline.

Bridges the Next.js frontend with the Python orchestration engine.
"""

from typing import Any

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import get_all_leads, get_lead_count
from email_drafts import get_all_drafts, get_sendable_drafts, update_draft
from logger import get_logs
from main import run_campaign, send_all, send_single
from product_loader import get_catalogue_json

# In-memory status tracker for the active campaign
_campaign_status: dict[str, Any] = {
    "running": False,
    "result": None,
}


def _run_campaign_task(payload: dict) -> None:
    """Wrapper that runs the campaign and updates in-memory status."""
    global _campaign_status
    _campaign_status["running"] = True
    _campaign_status["result"] = None
    try:
        result = run_campaign(payload)
        _campaign_status["result"] = result
    except Exception as exc:
        _campaign_status["result"] = {"status": "error", "message": str(exc)}
    finally:
        _campaign_status["running"] = False


# ── FastAPI App ────────────────────────────────────────────────────────────────

app = FastAPI(title="IRUS AI Outreach API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Products ───────────────────────────────────────────────────────────────────

@app.get("/products")
def get_products() -> dict:
    """Return the full product catalogue as JSON."""
    try:
        products = get_catalogue_json()
        return {"status": "success", "count": len(products), "products": products}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# ── Campaign Launch ────────────────────────────────────────────────────────────

@app.post("/launch")
def launch_campaign(payload: dict, background_tasks: BackgroundTasks) -> dict:
    """Start the pipeline: discovery → enrichment → AI drafting.

    Expected payload:
        {
            "domain": "Defence" | "Medical",
            "locations": ["India", "UAE"],
            "selected_products": ["Product A", "Product B"],
            "dry_run": true
        }
    """
    if _campaign_status["running"]:
        return {
            "status": "busy",
            "message": "A campaign is already running. Please wait.",
        }

    required = {"domain", "locations", "selected_products"}
    missing = required - set(payload.keys())
    if missing:
        return {
            "status": "error",
            "message": f"Missing required fields: {', '.join(sorted(missing))}",
        }

    background_tasks.add_task(_run_campaign_task, payload)
    return {
        "status": "started",
        "message": "Campaign started in the background.",
        "payload": {k: payload[k] for k in required if k in payload},
    }


# ── Drafts ─────────────────────────────────────────────────────────────────────

@app.get("/drafts")
def get_drafts(status: str | None = None) -> dict:
    """Return all AI-drafted emails. Optional status filter: drafted, edited, sent, failed."""
    try:
        drafts = get_all_drafts(status=status)
        return {"status": "success", "count": len(drafts), "drafts": drafts}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.get("/drafts/pending")
def get_pending_drafts() -> dict:
    """Return all drafts that are ready to send (drafted or edited)."""
    try:
        drafts = get_sendable_drafts()
        return {"status": "success", "count": len(drafts), "drafts": drafts}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.put("/drafts/{email}")
def edit_draft(email: str, payload: dict) -> dict:
    """Update the subject and/or body of a drafted email. Sets status to 'edited'."""
    try:
        subject = payload.get("subject")
        body = payload.get("body")
        if subject is None and body is None:
            return {"status": "error", "message": "Nothing to update. Provide subject or body."}
        updated = update_draft(email, subject=subject, body=body)
        if updated:
            return {"status": "success", "message": f"Draft for {email} updated."}
        return {"status": "error", "message": f"Draft for {email} not found."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.post("/drafts/{email}/send")
def send_one(email: str) -> dict:
    """Send a single reviewed email."""
    try:
        return send_single(email)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.post("/drafts/send-all")
def send_all_drafts(background_tasks: BackgroundTasks) -> dict:
    """Send all pending (drafted/edited) emails in the background."""
    background_tasks.add_task(send_all)
    return {
        "status": "started",
        "message": "Sending all pending emails in the background.",
    }


# ── Leads ──────────────────────────────────────────────────────────────────────

@app.get("/leads")
def get_leads(category: str | None = None, search: str | None = None, limit: int = 500, offset: int = 0) -> dict:
    """Return all scraped leads with optional filters."""
    try:
        leads = get_all_leads(category=category, search=search, limit=limit, offset=offset)
        total = get_lead_count(category=category, search=search)
        return {"status": "success", "count": len(leads), "total": total, "leads": leads}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# ── Logs & Status ──────────────────────────────────────────────────────────────

@app.get("/logs")
def get_logs_endpoint(limit: int = 500) -> dict:
    try:
        rows = get_logs(limit=limit)
        return {"status": "success", "count": len(rows), "logs": rows}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.get("/status")
def get_status() -> dict:
    return {
        "status": "success",
        "running": _campaign_status["running"],
        "last_result": _campaign_status["result"],
    }
