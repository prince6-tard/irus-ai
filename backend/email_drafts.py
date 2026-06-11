"""Email drafts storage and management.

Stores AI-drafted emails in Neon DB for manual review before sending.
Supports: list drafts, update content, send single, send all.
"""

from typing import Any

from db import (
    clear_email_drafts,
    get_all_email_drafts,
    get_email_draft,
    get_sendable_email_drafts,
    mark_email_failed,
    mark_email_sent,
    save_email_draft,
    update_email_draft,
)


# Re-export with original names so api.py / main.py don't break


def get_all_drafts(status: str | None = None) -> list[dict]:
    """Return all drafted emails from DB."""
    return get_all_email_drafts(status)


def get_draft(email: str) -> dict | None:
    """Return a single draft by email address."""
    return get_email_draft(email)


def save_draft(
    lead: dict,
    subject: str,
    body: str,
    status: str = "drafted",
) -> None:
    """Save a single draft row to the DB."""
    save_email_draft(lead, subject, body, status)


def update_draft(email: str, subject: str | None = None, body: str | None = None) -> bool:
    """Update subject and/or body of a single draft. Sets status to 'edited'."""
    return update_email_draft(email, subject, body)


def mark_sent(email: str) -> bool:
    """Mark a single draft as 'sent'."""
    return mark_email_sent(email)


def mark_failed(email: str) -> bool:
    """Mark a single draft as 'failed'."""
    return mark_email_failed(email)


def clear_drafts() -> None:
    """Delete drafted/edited email_drafts rows (preserve sent/failed history)."""
    clear_email_drafts()


def get_sendable_drafts() -> list[dict]:
    """Return all drafts that are ready to send (status = drafted or edited)."""
    return get_sendable_email_drafts()
