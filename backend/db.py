"""PostgreSQL database module for the IRUS AI Outreach Pipeline.

Centralises all Neon DB access: schema, CRUD helpers, and CSV migration.
"""

import csv
import json
import os
from datetime import datetime, timezone
from typing import Any

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_N70sdZWreHfA@ep-red-meadow-apdboe3l-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
)

# Project root is the parent of backend/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Connection ────────────────────────────────────────────────────────────────


def get_conn():
    """Return a new psycopg2 connection."""
    return psycopg2.connect(DATABASE_URL)


# ── Schema ────────────────────────────────────────────────────────────────────


def init_tables() -> None:
    """Create tables if they don't exist. Safe to call on startup."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # All discovered/scraped leads (merged raw + enriched columns)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id              SERIAL PRIMARY KEY,
                    name            TEXT,
                    email           TEXT,
                    email_source    TEXT,
                    phone           TEXT,
                    has_phone       BOOLEAN DEFAULT FALSE,
                    organization    TEXT,
                    organization_domain TEXT,
                    role            TEXT,
                    category        TEXT,
                    linkedin_url    TEXT,
                    city            TEXT,
                    country         TEXT,
                    apollo_id       TEXT,
                    notes           TEXT,
                    source          TEXT,
                    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """
            )

            # AI drafted emails awaiting review / already sent
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS email_drafts (
                    id              SERIAL PRIMARY KEY,
                    timestamp       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    email           TEXT NOT NULL,
                    name            TEXT,
                    organization    TEXT,
                    subject         TEXT,
                    body            TEXT,
                    status          TEXT DEFAULT 'drafted',
                    lead_json       JSONB,
                    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """
            )

            # Pipeline action audit log
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS action_logs (
                    id              SERIAL PRIMARY KEY,
                    timestamp       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    email           TEXT,
                    name            TEXT,
                    organization    TEXT,
                    status          TEXT,
                    subject         TEXT,
                    note            TEXT,
                    apollo_id       TEXT,
                    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """
            )
        conn.commit()


# ── CSV → DB migration ────────────────────────────────────────────────────────


def _parse_iso_ts(ts: str) -> str | None:
    """Normalise an ISO timestamp string for PostgreSQL."""
    ts = ts.strip()
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.isoformat()
    except Exception:
        return None


def migrate_from_csv() -> dict[str, int]:
    """One-shot migration of existing CSV files into Neon.

    Returns:
        Dict with counts: {"leads": int, "email_drafts": int, "action_logs": int}
    """
    counts = {"leads": 0, "email_drafts": 0, "action_logs": 0}

    with get_conn() as conn:
        with conn.cursor() as cur:
            # ── leads ─────────────────────────────────────────────────────────
            # Prefer leads_enriched.csv (has all columns). Fallback to leads_raw.csv.
            leads_file = os.path.join(PROJECT_ROOT, "leads_enriched.csv")
            if not os.path.exists(leads_file):
                leads_file = os.path.join(PROJECT_ROOT, "leads_raw.csv")

            if os.path.exists(leads_file):
                leads_insert = """
                    INSERT INTO leads
                    (name, email, email_source, phone, has_phone, organization,
                     organization_domain, role, category, linkedin_url, city,
                     country, apollo_id, notes, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """
                with open(leads_file, newline="", encoding="utf-8") as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        has_phone_val = False
                        hp = row.get("has_phone", "").strip().lower()
                        if hp in ("true", "1", "yes"):
                            has_phone_val = True
                        cur.execute(
                            leads_insert,
                            (
                                row.get("name", ""),
                                row.get("email", ""),
                                row.get("email_source", ""),
                                row.get("phone", ""),
                                has_phone_val,
                                row.get("organization", ""),
                                row.get("organization_domain", ""),
                                row.get("role", ""),
                                row.get("category", ""),
                                row.get("linkedin_url", ""),
                                row.get("city", ""),
                                row.get("country", ""),
                                row.get("apollo_id", ""),
                                row.get("notes", ""),
                                row.get("source", ""),
                            ),
                        )
                        counts["leads"] += cur.rowcount

            # ── email_drafts ──────────────────────────────────────────────────
            if os.path.exists(os.path.join(PROJECT_ROOT, "email_drafts.csv")):
                drafts_insert = """
                    INSERT INTO email_drafts
                    (timestamp, email, name, organization, subject, body, status, lead_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """
                with open(os.path.join(PROJECT_ROOT, "email_drafts.csv"), newline="", encoding="utf-8") as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        ts = _parse_iso_ts(row.get("timestamp", ""))
                        lead_json = None
                        lj_raw = row.get("lead_json", "")
                        if lj_raw:
                            try:
                                lead_json = json.loads(lj_raw)
                            except json.JSONDecodeError:
                                lead_json = {"raw": lj_raw}
                        cur.execute(
                            drafts_insert,
                            (
                                ts,
                                row.get("email", ""),
                                row.get("name", ""),
                                row.get("organization", ""),
                                row.get("subject", ""),
                                row.get("body", ""),
                                row.get("status", "drafted"),
                                json.dumps(lead_json) if lead_json else None,
                            ),
                        )
                        counts["email_drafts"] += cur.rowcount

            # ── action_logs ───────────────────────────────────────────────────
            if os.path.exists(os.path.join(PROJECT_ROOT, "log.csv")):
                logs_insert = """
                    INSERT INTO action_logs
                    (timestamp, email, name, organization, status, subject, note, apollo_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """
                with open(os.path.join(PROJECT_ROOT, "log.csv"), newline="", encoding="utf-8") as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        ts = _parse_iso_ts(row.get("timestamp", ""))
                        cur.execute(
                            logs_insert,
                            (
                                ts,
                                row.get("email", ""),
                                row.get("name", ""),
                                row.get("organization", ""),
                                row.get("status", ""),
                                row.get("subject", ""),
                                row.get("note", ""),
                                row.get("apollo_id", ""),
                            ),
                        )
                        counts["action_logs"] += cur.rowcount

        conn.commit()

    return counts


# ═══════════════════════════════════════════════════════════════════════════════
#  Leads
# ═══════════════════════════════════════════════════════════════════════════════


def insert_leads(leads: list[dict[str, Any]]) -> int:
    """Insert multiple leads. Deduplicates by email + organization.

    Returns:
        Number of rows actually inserted.
    """
    if not leads:
        return 0

    inserted = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            for lead in leads:
                cur.execute(
                    """
                    INSERT INTO leads
                    (name, email, phone, organization, organization_domain,
                     role, category, linkedin_url, city, country, apollo_id, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (
                        lead.get("name", ""),
                        lead.get("email", ""),
                        lead.get("phone", ""),
                        lead.get("organization", ""),
                        lead.get("organization_domain", ""),
                        lead.get("role", ""),
                        lead.get("category", ""),
                        lead.get("linkedin_url", ""),
                        lead.get("city", ""),
                        lead.get("country", ""),
                        lead.get("apollo_id", ""),
                        lead.get("source", ""),
                    ),
                )
                inserted += cur.rowcount
        conn.commit()
    return inserted


def get_all_leads(
    category: str | None = None,
    search: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    """Return leads from DB with optional filters.

    Args:
        category: 'Defence' or 'Medical' (optional).
        search: Free-text search across name, organization, email, city (optional).
        limit: Max rows.
        offset: Pagination offset.

    Returns:
        List of lead dicts.
    """
    where_clauses: list[str] = []
    params: list[Any] = []

    if category:
        where_clauses.append("category ILIKE %s")
        params.append(category)

    if search:
        where_clauses.append(
            "(name ILIKE %s OR organization ILIKE %s OR email ILIKE %s OR city ILIKE %s)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    sql = f"""
        SELECT id, name, email, email_source, phone, has_phone, organization,
               organization_domain, role, category, linkedin_url, city, country,
               apollo_id, notes, source, created_at
        FROM leads
        {where_sql}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            return [dict(zip(colnames, row)) for row in rows]


def get_lead_count(category: str | None = None, search: str | None = None) -> int:
    """Return total lead count with optional filters."""
    where_clauses: list[str] = []
    params: list[Any] = []

    if category:
        where_clauses.append("category ILIKE %s")
        params.append(category)
    if search:
        where_clauses.append(
            "(name ILIKE %s OR organization ILIKE %s OR email ILIKE %s OR city ILIKE %s)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM leads {where_sql}", params)
            return cur.fetchone()[0] or 0


def update_lead(email: str, **kwargs: Any) -> bool:
    """Update enrichment columns for a single lead identified by email.

    Updates whichever columns are provided (e.g., email_source, has_phone, notes).
    """
    allowed = {"email_source", "has_phone", "notes", "email"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [email]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE leads SET {set_clause} WHERE email ILIKE %s",
                values,
            )
            updated = cur.rowcount > 0
        conn.commit()
    return updated


def get_raw_leads() -> list[dict]:
    """Return all leads as dicts (used by lead_enricher)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM leads ORDER BY created_at DESC")
            colnames = [desc[0] for desc in cur.description]
            return [dict(zip(colnames, row)) for row in cur.fetchall()]


# ═══════════════════════════════════════════════════════════════════════════════
#  Email Drafts
# ═══════════════════════════════════════════════════════════════════════════════


def get_all_email_drafts(status: str | None = None) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT * FROM email_drafts WHERE status = %s ORDER BY created_at DESC",
                    (status,),
                )
            else:
                cur.execute("SELECT * FROM email_drafts ORDER BY created_at DESC")
            colnames = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            results = []
            for row in rows:
                d = dict(zip(colnames, row))
                if d.get("lead_json"):
                    d["lead_json"] = json.dumps(d["lead_json"])
                results.append(d)
            return results


def get_sendable_email_drafts() -> list[dict]:
    """Return drafts ready to send (drafted or edited)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM email_drafts WHERE status IN ('drafted', 'edited') ORDER BY created_at DESC"
            )
            colnames = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            results = []
            for row in rows:
                d = dict(zip(colnames, row))
                if d.get("lead_json"):
                    d["lead_json"] = json.dumps(d["lead_json"])
                results.append(d)
            return results


def get_email_draft(email: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM email_drafts WHERE email ILIKE %s ORDER BY created_at DESC LIMIT 1",
                (email,),
            )
            colnames = [desc[0] for desc in cur.description]
            row = cur.fetchone()
            if not row:
                return None
            d = dict(zip(colnames, row))
            if d.get("lead_json"):
                d["lead_json"] = json.dumps(d["lead_json"])
            return d


def save_email_draft(
    lead: dict,
    subject: str,
    body: str,
    status: str = "drafted",
) -> None:
    lead_json = json.dumps(lead, ensure_ascii=False)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_drafts
                (email, name, organization, subject, body, status, lead_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    name = EXCLUDED.name,
                    organization = EXCLUDED.organization,
                    subject = EXCLUDED.subject,
                    body = EXCLUDED.body,
                    status = EXCLUDED.status,
                    lead_json = EXCLUDED.lead_json,
                    timestamp = NOW();
                """,
                (
                    lead.get("email", ""),
                    lead.get("name", ""),
                    lead.get("organization", ""),
                    subject,
                    body,
                    status,
                    lead_json,
                ),
            )
        conn.commit()


def update_email_draft(
    email: str,
    subject: str | None = None,
    body: str | None = None,
) -> bool:
    fields: list[str] = []
    values: list[Any] = []

    if subject is not None:
        fields.append("subject = %s")
        values.append(subject)
    if body is not None:
        fields.append("body = %s")
        values.append(body)
    if not fields:
        return False

    fields.append("status = 'edited'")
    values.append(email)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE email_drafts SET {', '.join(fields)} WHERE email ILIKE %s",
                values,
            )
            updated = cur.rowcount > 0
        conn.commit()
    return updated


def mark_email_sent(email: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE email_drafts SET status = 'sent' WHERE email ILIKE %s",
                (email,),
            )
            updated = cur.rowcount > 0
        conn.commit()
    return updated


def mark_email_failed(email: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE email_drafts SET status = 'failed' WHERE email ILIKE %s",
                (email,),
            )
            updated = cur.rowcount > 0
        conn.commit()
    return updated


def clear_email_drafts() -> None:
    """Remove drafted/edited rows only; preserve sent/failed history."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM email_drafts WHERE status IN ('drafted', 'edited')")
        conn.commit()


# ═══════════════════════════════════════════════════════════════════════════════
#  Action Logs
# ═══════════════════════════════════════════════════════════════════════════════


def write_action_log(
    lead: dict,
    status: str,
    subject: str = "",
    note: str = "",
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO action_logs
                (timestamp, email, name, organization, status, subject, note, apollo_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    datetime.now(timezone.utc),
                    lead.get("email", ""),
                    lead.get("name", ""),
                    lead.get("organization", ""),
                    status,
                    subject,
                    note,
                    lead.get("apollo_id", ""),
                ),
            )
        conn.commit()


def already_contacted(email: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM action_logs WHERE email ILIKE %s)",
                (email,),
            )
            return cur.fetchone()[0]


def get_action_logs(limit: int = 500) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT timestamp, email, name, organization, status, subject, note, apollo_id
                FROM action_logs
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            colnames = [desc[0] for desc in cur.description]
            return [dict(zip(colnames, row)) for row in cur.fetchall()]


def print_log_summary() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, COUNT(*) FROM action_logs GROUP BY status")
            counts = dict(cur.fetchall())
            cur.execute("SELECT COUNT(*) FROM action_logs")
            total = cur.fetchone()[0]

    print("=" * 50)
    print(f"PIPELINE SUMMARY — {total} total log entries")
    print("=" * 50)
    for status, count in sorted(counts.items()):
        print(f"  {status:<25}: {count}")
    print("=" * 50)
