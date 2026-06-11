"""Master orchestrator for the IRUS AI Outreach Pipeline.

Triggered by api.py with a configuration payload. Executes the full pipeline:
lead discovery → enrichment → email drafting → storage for review → sending.
"""

import json
import os
import random
import sys
import time
from typing import Any

from config import (
    DELAY_MAX_SECONDS,
    DELAY_MIN_SECONDS,
    DRY_RUN,
    MAX_SENDS_PER_RUN,
    REVIEW_BEFORE_SEND,
)
from claude_drafter import draft_email
from email_drafts import clear_drafts, get_sendable_drafts, mark_failed, mark_sent, save_draft
from email_sender import send_email
from lead_enricher import enrich_leads
from lead_finder import find_leads
from logger import already_contacted, print_summary, write_log
from product_loader import format_selected_catalogue


def run_campaign(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute lead discovery + enrichment + AI drafting. Store drafts for review.

    Args:
        payload: Dict with keys:
            - domain (str): "Defence" or "Medical"
            - locations (list[str]): Target geographies, e.g., ["India", "UAE"]
            - selected_products (list[str]): Product names chosen in the UI
            - dry_run (bool, optional): Overrides config.DRY_RUN

    Returns:
        Summary dict with status, counts, and messages.
    """
    domain = payload.get("domain", "")
    locations = payload.get("locations", [])
    selected_products = payload.get("selected_products", [])
    is_dry_run = payload.get("dry_run", DRY_RUN)
    review_first = payload.get("review_before_send", REVIEW_BEFORE_SEND)

    if not domain or not locations or not selected_products:
        return {
            "status": "error",
            "message": "Missing required fields: domain, locations, or selected_products.",
        }

    print("=" * 60)
    print(f"IRUS AI Outreach Pipeline — {domain} campaign")
    print(f"Locations: {locations}")
    print(f"Selected products ({len(selected_products)}): {selected_products}")
    print(f"Dry run: {is_dry_run} | Review before send: {review_first}")
    print("=" * 60)

    # Clear old drafts at the start of every campaign
    clear_drafts()

    # ── Format selected products for xAI ───────────────────────────────────────
    selected_products_text = format_selected_catalogue(selected_products)
    if selected_products_text == "No products selected.":
        return {
            "status": "error",
            "message": "Selected products could not be matched in the catalogue.",
        }

    # ── Lead Discovery ─────────────────────────────────────────────────────────
    try:
        raw_leads = find_leads(domain, locations)
    except Exception as exc:
        print(f"Lead discovery failed: {exc}")
        return {"status": "error", "message": f"Lead discovery failed: {exc}"}

    if not raw_leads:
        print("No leads found. Pipeline complete.")
        return {"status": "success", "message": "No leads found.", "leads_found": 0}

    print(f"Raw leads saved to leads_raw.csv. Found {len(raw_leads)} leads.")

    # ── Lead Enrichment ────────────────────────────────────────────────────────
    try:
        enriched_leads = enrich_leads()
    except Exception as exc:
        print(f"Lead enrichment failed: {exc}")
        return {"status": "error", "message": f"Lead enrichment failed: {exc}"}

    if not enriched_leads:
        print("No enriched leads. Pipeline complete.")
        return {"status": "success", "message": "No enriched leads.", "leads_found": len(raw_leads)}

    # ── Shuffle and cap ────────────────────────────────────────────────────────
    random.shuffle(enriched_leads)
    leads_to_process = enriched_leads[:MAX_SENDS_PER_RUN]

    print(f"\nProcessing {len(leads_to_process)} leads (capped at {MAX_SENDS_PER_RUN}).")

    # ── Outreach loop: draft + store ───────────────────────────────────────────
    drafted = 0
    skipped = 0
    errors = 0

    for idx, lead in enumerate(leads_to_process, start=1):
        email = lead.get("email", "").strip()
        name = lead.get("name", "").strip()
        print(f"\n[{idx}/{len(leads_to_process)}] {name} — {email}")

        # Skip if already contacted (log exists in log.csv)
        if email and already_contacted(email):
            print("  → Already contacted. Skipping.")
            write_log(lead, "skipped_already_sent", note="Previously contacted.")
            skipped += 1
            continue

        # Skip if no email
        if not email:
            print("  → No email. Skipping.")
            write_log(lead, "skipped_no_email", note="No email after enrichment.")
            skipped += 1
            continue

        # Draft email via xAI
        try:
            subject, body = draft_email(lead, selected_products_text)
        except Exception as exc:
            print(f"  → Drafting error: {exc}")
            write_log(lead, "error_draft", note=str(exc))
            errors += 1
            continue

        print(f"  → Drafted: {subject[:60]}")

        # Save draft for review
        try:
            save_draft(lead, subject, body, status="drafted")
            write_log(lead, "drafted", subject=subject, note="AI drafted, queued for review.")
            drafted += 1
        except Exception as exc:
            print(f"  → Draft save error: {exc}")
            write_log(lead, "error_draft", subject=subject, note=f"Failed to save draft: {exc}")
            errors += 1

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"DRAFTING COMPLETE — {drafted} drafted, {skipped} skipped, {errors} errors")
    if review_first:
        print("Open the dashboard → Review & Send tab to send emails.")
    print("=" * 60)
    print_summary()

    return {
        "status": "success",
        "message": f"Drafting complete. {drafted} emails ready for review.",
        "leads_found": len(raw_leads),
        "leads_enriched": len(enriched_leads),
        "leads_processed": len(leads_to_process),
        "drafted": drafted,
        "skipped": skipped,
        "errors": errors,
        "dry_run": is_dry_run,
        "review_before_send": review_first,
    }


def send_single(email: str) -> dict:
    """Send a single drafted email after user review.

    Args:
        email: The recipient email address (used as draft ID).

    Returns:
        Dict with status message.
    """
    draft_row = None
    for d in get_sendable_drafts():
        if d.get("email", "").strip().lower() == email.strip().lower():
            draft_row = d
            break

    if not draft_row:
        return {"status": "error", "message": f"No pending draft found for {email}"}

    name = draft_row.get("name", "")
    subject = draft_row.get("subject", "")
    body = draft_row.get("body", "")

    try:
        success = send_email(email, name, subject, body)
        if success:
            mark_sent(email)
            write_log({
                "email": email, "name": name,
                "organization": draft_row.get("organization", ""),
            }, "sent", subject=subject, note="Sent after manual review.")
            return {"status": "success", "message": f"Sent to {email}"}
        else:
            mark_failed(email)
            write_log({
                "email": email, "name": name,
                "organization": draft_row.get("organization", ""),
            }, "error_send", subject=subject, note="send_email returned False.")
            return {"status": "error", "message": f"Failed to send to {email}"}
    except Exception as exc:
        mark_failed(email)
        write_log({
            "email": email, "name": name,
            "organization": draft_row.get("organization", ""),
        }, "error_send", subject=subject, note=str(exc))
        return {"status": "error", "message": f"Exception sending to {email}: {exc}"}


def send_all() -> dict:
    """Send all pending (drafted/edited) emails.

    Returns:
        Dict with sent/failed counts.
    """
    drafts = get_sendable_drafts()
    sent_count = 0
    failed_count = 0

    for idx, draft_row in enumerate(drafts, start=1):
        email = draft_row.get("email", "").strip()
        name = draft_row.get("name", "")
        subject = draft_row.get("subject", "")
        body = draft_row.get("body", "")

        if not email:
            failed_count += 1
            continue

        try:
            success = send_email(email, name, subject, body)
            if success:
                mark_sent(email)
                sent_count += 1
                print(f"  [{idx}/{len(drafts)}] Sent → {email}")
            else:
                mark_failed(email)
                failed_count += 1
                print(f"  [{idx}/{len(drafts)}] Failed → {email}")
        except Exception as exc:
            mark_failed(email)
            failed_count += 1
            print(f"  [{idx}/{len(drafts)}] Exception → {email}: {exc}")

        # Throttle between sends
        if idx < len(drafts):
            delay = random.randint(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS)
            print(f"    → Sleeping {delay}s before next send...")
            time.sleep(delay)

    return {
        "status": "success",
        "message": f"Batch send complete. Sent: {sent_count}, Failed: {failed_count}.",
        "sent": sent_count,
        "failed": failed_count,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        payload = json.loads(sys.argv[1])
    else:
        payload = {
            "domain": "Medical",
            "locations": ["Noida"],
            "selected_products": ["Advanced Cancer Detection Vehicle"],
            "dry_run": True,
        }
    result = run_campaign(payload)
    print(json.dumps(result, indent=2))
