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
                    email           TEXT NOT NULL UNIQUE,
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


def get_leads_by_ids(ids: list[int]) -> list[dict]:
    """Return leads matching the provided IDs."""
    if not ids:
        return []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM leads WHERE id = ANY(%s) ORDER BY created_at DESC",
                (ids,),
            )
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


def _json_encode_lead(lead: dict) -> str:
    """Serialize a lead dict to JSON, handling datetime objects."""

    class _DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            from datetime import date, datetime

            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return super().default(obj)

    return json.dumps(lead, ensure_ascii=False, cls=_DateTimeEncoder)


def save_email_draft(
    lead: dict,
    subject: str,
    body: str,
    status: str = "drafted",
) -> None:
    lead_json = _json_encode_lead(lead)
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

# ═══════════════════════════════════════════════════════════════════════════════
#  Dental Connect — Tables
# ═══════════════════════════════════════════════════════════════════════════════

import re
import csv
import os

_dental_db_reachable: bool | None = None


def _check_dental_db_reachable() -> bool:
    """Check once whether PostgreSQL is reachable; cache the result."""
    global _dental_db_reachable
    if _dental_db_reachable is not None:
        return _dental_db_reachable
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        _dental_db_reachable = True
        return True
    except psycopg2.OperationalError:
        _dental_db_reachable = False
        return False


DENTAL_LEADS_CSV = os.path.join(PROJECT_ROOT, "dental_leads.csv")
DENTAL_EMAIL_LOG_CSV = os.path.join(PROJECT_ROOT, "dental_email_log.csv")

_EMAIL_RE = re.compile(r"^[^@\s]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def init_dental_tables() -> None:
    """Create dental_leads and dental_email_log tables."""
    if _check_dental_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS dental_leads (
                            id SERIAL PRIMARY KEY,
                            name TEXT,
                            email TEXT UNIQUE,
                            email_source TEXT,
                            phone TEXT,
                            organization TEXT,
                            organization_domain TEXT,
                            linkedin_url TEXT,
                            city TEXT,
                            country TEXT,
                            scrape_query TEXT,
                            status TEXT DEFAULT 'new',
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                        """
                    )
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS dental_email_log (
                            id SERIAL PRIMARY KEY,
                            dental_lead_id INT REFERENCES dental_leads(id),
                            email TEXT,
                            name TEXT,
                            organization TEXT,
                            city TEXT,
                            country TEXT,
                            status TEXT,
                            sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                        """
                    )
                conn.commit()
        except psycopg2.Error as exc:
            print(f"[dental_db] Table init warning: {exc}")
    # Always ensure CSV files exist as fallback
    leads_header = "id,name,email,email_source,phone,organization,organization_domain,linkedin_url,city,country,scrape_query,status,created_at"
    log_header = "id,dental_lead_id,email,name,organization,city,country,status,sent_at"
    if not os.path.exists(DENTAL_LEADS_CSV):
        with open(DENTAL_LEADS_CSV, "w", newline="", encoding="utf-8") as f:
            f.write(leads_header + "\n")
    if not os.path.exists(DENTAL_EMAIL_LOG_CSV):
        with open(DENTAL_EMAIL_LOG_CSV, "w", newline="", encoding="utf-8") as f:
            f.write(log_header + "\n")


def save_dental_lead(lead: dict) -> bool:
    """Insert a dental lead. Skip if email is null/invalid/duplicate."""
    email = (lead.get("email") or "").strip()
    if not email:
        return False
    if not _EMAIL_RE.match(email):
        return False
    if _check_dental_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO dental_leads
                        (name, email, email_source, phone, organization, organization_domain,
                         linkedin_url, city, country, scrape_query, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (email) DO NOTHING;
                        """,
                        (
                            lead.get("name", ""),
                            email,
                            lead.get("email_source", ""),
                            lead.get("phone", ""),
                            lead.get("organization", ""),
                            lead.get("organization_domain", ""),
                            lead.get("linkedin_url", ""),
                            lead.get("city", ""),
                            lead.get("country", ""),
                            lead.get("scrape_query", ""),
                            lead.get("status", "new"),
                        ),
                    )
                    saved = cur.rowcount > 0
                conn.commit()
            return saved
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    rows = []
    existing_ids = []
    if os.path.exists(DENTAL_LEADS_CSV):
        with open(DENTAL_LEADS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                try:
                    existing_ids.append(int(row["id"]))
                except (ValueError, KeyError):
                    pass
                if row.get("email", "").lower() == email.lower():
                    return False
    next_id = max(existing_ids) + 1 if existing_ids else 1
    new_row = {
        "id": str(next_id),
        "name": lead.get("name", ""),
        "email": email,
        "email_source": lead.get("email_source", ""),
        "phone": lead.get("phone", ""),
        "organization": lead.get("organization", ""),
        "organization_domain": lead.get("organization_domain", ""),
        "linkedin_url": lead.get("linkedin_url", ""),
        "city": lead.get("city", ""),
        "country": lead.get("country", ""),
        "scrape_query": lead.get("scrape_query", ""),
        "status": lead.get("status", "new"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rows.append(new_row)
    fieldnames = ["id", "name", "email", "email_source", "phone", "organization",
                  "organization_domain", "linkedin_url", "city", "country", "scrape_query", "status", "created_at"]
    with open(DENTAL_LEADS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return True


def get_dental_leads(status: str | None = None) -> list[dict]:
    if _check_dental_db_reachable():
        try:
            sql = "SELECT * FROM dental_leads"
            params = []
            if status:
                sql += " WHERE status = %s"
                params.append(status)
            sql += " ORDER BY created_at DESC"
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    colnames = [desc[0] for desc in cur.description]
                    return [dict(zip(colnames, row)) for row in cur.fetchall()]
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    if not os.path.exists(DENTAL_LEADS_CSV):
        return []
    rows = []
    with open(DENTAL_LEADS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row["id"] = int(row["id"])
            except (ValueError, KeyError):
                row["id"] = 0
            if status is None or row.get("status") == status:
                rows.append(row)
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return rows


def update_dental_lead_status(lead_id: int, status: str) -> bool:
    if _check_dental_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE dental_leads SET status = %s WHERE id = %s",
                        (status, lead_id),
                    )
                    updated = cur.rowcount > 0
                conn.commit()
            return updated
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    if not os.path.exists(DENTAL_LEADS_CSV):
        return False
    rows = []
    found = False
    with open(DENTAL_LEADS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row_id = int(row["id"])
            except (ValueError, KeyError):
                row_id = -1
            if row_id == lead_id:
                row["status"] = status
                found = True
            rows.append(row)
    if not found:
        return False
    fieldnames = ["id", "name", "email", "email_source", "phone", "organization",
                  "organization_domain", "linkedin_url", "city", "country", "scrape_query", "status", "created_at"]
    with open(DENTAL_LEADS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return True


def log_dental_email(
    lead_id: int,
    email: str,
    name: str,
    organization: str,
    city: str,
    country: str,
    status: str,
) -> None:
    if _check_dental_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO dental_email_log
                        (dental_lead_id, email, name, organization, city, country, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """,
                        (lead_id, email, name, organization, city, country, status),
                    )
                conn.commit()
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    rows = []
    existing_ids = []
    if os.path.exists(DENTAL_EMAIL_LOG_CSV):
        with open(DENTAL_EMAIL_LOG_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                try:
                    existing_ids.append(int(row["id"]))
                except (ValueError, KeyError):
                    pass
    next_id = max(existing_ids) + 1 if existing_ids else 1
    new_row = {
        "id": str(next_id),
        "dental_lead_id": str(lead_id),
        "email": email,
        "name": name,
        "organization": organization,
        "city": city,
        "country": country,
        "status": status,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    rows.append(new_row)
    fieldnames = ["id", "dental_lead_id", "email", "name", "organization",
                  "city", "country", "status", "sent_at"]
    with open(DENTAL_EMAIL_LOG_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_dental_email_log() -> list[dict]:
    if _check_dental_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, dental_lead_id, email, name, organization,
                               city, country, status, sent_at
                        FROM dental_email_log
                        ORDER BY sent_at DESC
                        """
                    )
                    colnames = [desc[0] for desc in cur.description]
                    return [dict(zip(colnames, row)) for row in cur.fetchall()]
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    if not os.path.exists(DENTAL_EMAIL_LOG_CSV):
        return []
    rows = []
    with open(DENTAL_EMAIL_LOG_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    rows.sort(key=lambda r: r.get("sent_at", ""), reverse=True)
    return rows


def get_dental_leads_by_ids(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    if _check_dental_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM dental_leads WHERE id = ANY(%s) ORDER BY created_at DESC",
                        (ids,),
                    )
                    colnames = [desc[0] for desc in cur.description]
                    return [dict(zip(colnames, row)) for row in cur.fetchall()]
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    if not os.path.exists(DENTAL_LEADS_CSV):
        return []
    rows = []
    id_set = set(ids)
    with open(DENTAL_LEADS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row_id = int(row["id"])
            except (ValueError, KeyError):
                row_id = -1
            if row_id in id_set:
                rows.append(row)
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
#  Medical Tourism — Tables
# ═══════════════════════════════════════════════════════════════════════════════

_medtour_db_reachable: bool | None = None


def _check_medtour_db_reachable() -> bool:
    """Check once whether PostgreSQL is reachable; cache the result."""
    global _medtour_db_reachable
    if _medtour_db_reachable is not None:
        return _medtour_db_reachable
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        _medtour_db_reachable = True
        return True
    except psycopg2.OperationalError:
        _medtour_db_reachable = False
        return False


MEDTOUR_LEADS_CSV = os.path.join(PROJECT_ROOT, "medical_tourism_leads.csv")
MEDTOUR_EMAIL_LOG_CSV = os.path.join(PROJECT_ROOT, "medical_tourism_email_log.csv")


# JSONB helper — store arrays/objects as JSON strings
def _json_or_none(val):
    """Return a JSON-encoded string or None."""
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    return val


def init_medical_tourism_tables() -> None:
    """Create medical_tourism_leads and medical_tourism_email_log tables."""
    if _check_medtour_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS medical_tourism_leads (
                            id                  SERIAL PRIMARY KEY,
                            company_name        TEXT,
                            website             TEXT,
                            domain              TEXT UNIQUE,
                            description         TEXT,
                            country             TEXT,
                            province            TEXT,
                            city                TEXT,
                            address             TEXT,
                            postal_code         TEXT,
                            emails              JSONB,
                            phones              JSONB,
                            whatsapp_numbers    JSONB,
                            linkedin            TEXT,
                            facebook            TEXT,
                            instagram           TEXT,
                            youtube             TEXT,
                            decision_makers     JSONB,
                            services            JSONB,
                            india_related       BOOLEAN DEFAULT FALSE,
                            dental_related      BOOLEAN DEFAULT FALSE,
                            hospital_partners   JSONB,
                            clinic_partners     JSONB,
                            accreditations      JSONB,
                            testimonials_count  INT DEFAULT 0,
                            outreach_score      INT DEFAULT 0,
                            priority            TEXT DEFAULT 'P3',
                            scrape_query        TEXT,
                            status              TEXT DEFAULT 'new',
                            created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                        """
                    )
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS medical_tourism_email_log (
                            id                  SERIAL PRIMARY KEY,
                            medtour_lead_id     INT REFERENCES medical_tourism_leads(id),
                            email               TEXT,
                            name                TEXT,
                            organization        TEXT,
                            city                TEXT,
                            country             TEXT,
                            status              TEXT,
                            sent_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                        """
                    )
                conn.commit()
        except psycopg2.Error as exc:
            print(f"[medtour_db] Table init warning: {exc}")
    # Always ensure CSV files exist as fallback
    leads_header = (
        "id,company_name,website,domain,description,country,province,city,address," +
        "postal_code,emails,phones,whatsapp_numbers,linkedin,facebook,instagram,youtube," +
        "decision_makers,services,india_related,dental_related,hospital_partners," +
        "clinic_partners,accreditations,testimonials_count,outreach_score,priority," +
        "scrape_query,status,created_at"
    )
    log_header = (
        "id,medtour_lead_id,email,name,organization,city,country,status,sent_at"
    )
    if not os.path.exists(MEDTOUR_LEADS_CSV):
        with open(MEDTOUR_LEADS_CSV, "w", newline="", encoding="utf-8") as f:
            f.write(leads_header + "\n")
    if not os.path.exists(MEDTOUR_EMAIL_LOG_CSV):
        with open(MEDTOUR_EMAIL_LOG_CSV, "w", newline="", encoding="utf-8") as f:
            f.write(log_header + "\n")


_MEDTOUR_LEAD_FIELDS = [
    "company_name", "website", "domain", "description", "country", "province",
    "city", "address", "postal_code", "emails", "phones", "whatsapp_numbers",
    "linkedin", "facebook", "instagram", "youtube", "decision_makers",
    "services", "india_related", "dental_related", "hospital_partners",
    "clinic_partners", "accreditations", "testimonials_count", "outreach_score",
    "priority", "scrape_query", "status", "created_at",
]


def save_medical_tourism_lead(lead: dict) -> bool:
    """Insert a medical-tourism lead. Deduplicates by domain.

    Returns True if a new row was inserted, False otherwise (duplicate or error).
    """
    domain = (lead.get("domain") or "").strip().lower()
    if _check_medtour_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO medical_tourism_leads
                        (company_name, website, domain, description,
                         country, province, city, address, postal_code,
                         emails, phones, whatsapp_numbers,
                         linkedin, facebook, instagram, youtube,
                         decision_makers, services,
                         india_related, dental_related,
                         hospital_partners, clinic_partners, accreditations,
                         testimonials_count, outreach_score, priority,
                         scrape_query, status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (domain) DO NOTHING;
                        """,
                        (
                            lead.get("company_name", ""),
                            lead.get("website", ""),
                            domain,
                            lead.get("description", ""),
                            lead.get("country", ""),
                            lead.get("province", ""),
                            lead.get("city", ""),
                            lead.get("address", ""),
                            lead.get("postal_code", ""),
                            _json_or_none(lead.get("emails")),
                            _json_or_none(lead.get("phones")),
                            _json_or_none(lead.get("whatsapp_numbers")),
                            lead.get("linkedin", ""),
                            lead.get("facebook", ""),
                            lead.get("instagram", ""),
                            lead.get("youtube", ""),
                            _json_or_none(lead.get("decision_makers")),
                            _json_or_none(lead.get("services")),
                            bool(lead.get("india_related")),
                            bool(lead.get("dental_related")),
                            _json_or_none(lead.get("hospital_partners")),
                            _json_or_none(lead.get("clinic_partners")),
                            _json_or_none(lead.get("accreditations")),
                            lead.get("testimonials_count", 0),
                            lead.get("outreach_score", 0),
                            lead.get("priority", "P3"),
                            lead.get("scrape_query", ""),
                            lead.get("status", "new"),
                        ),
                    )
                    saved = cur.rowcount > 0
                conn.commit()
            return saved
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback — deduplicate by domain
    rows = []
    existing_ids = []
    if os.path.exists(MEDTOUR_LEADS_CSV):
        with open(MEDTOUR_LEADS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                try:
                    existing_ids.append(int(row["id"]))
                except (ValueError, KeyError):
                    pass
                if (row.get("domain") or "").lower() == domain and domain:
                    return False  # duplicate domain
    next_id = max(existing_ids) + 1 if existing_ids else 1
    new_row = {
        "id": str(next_id),
        "company_name": lead.get("company_name", ""),
        "website": lead.get("website", ""),
        "domain": domain,
        "description": lead.get("description", ""),
        "country": lead.get("country", ""),
        "province": lead.get("province", ""),
        "city": lead.get("city", ""),
        "address": lead.get("address", ""),
        "postal_code": lead.get("postal_code", ""),
        "emails": json.dumps(lead.get("emails")) if lead.get("emails") else "",
        "phones": json.dumps(lead.get("phones")) if lead.get("phones") else "",
        "whatsapp_numbers": json.dumps(lead.get("whatsapp_numbers")) if lead.get("whatsapp_numbers") else "",
        "linkedin": lead.get("linkedin", ""),
        "facebook": lead.get("facebook", ""),
        "instagram": lead.get("instagram", ""),
        "youtube": lead.get("youtube", ""),
        "decision_makers": json.dumps(lead.get("decision_makers")) if lead.get("decision_makers") else "",
        "services": json.dumps(lead.get("services")) if lead.get("services") else "",
        "india_related": str(bool(lead.get("india_related"))).lower(),
        "dental_related": str(bool(lead.get("dental_related"))).lower(),
        "hospital_partners": json.dumps(lead.get("hospital_partners")) if lead.get("hospital_partners") else "",
        "clinic_partners": json.dumps(lead.get("clinic_partners")) if lead.get("clinic_partners") else "",
        "accreditations": json.dumps(lead.get("accreditations")) if lead.get("accreditations") else "",
        "testimonials_count": lead.get("testimonials_count", 0),
        "outreach_score": lead.get("outreach_score", 0),
        "priority": lead.get("priority", "P3"),
        "scrape_query": lead.get("scrape_query", ""),
        "status": lead.get("status", "new"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rows.append(new_row)
    with open(MEDTOUR_LEADS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_MEDTOUR_LEAD_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return True


def get_medical_tourism_leads(
    status: str | None = None,
    country: str | None = None,
    priority: str | None = None,
    dental_related: bool | None = None,
    india_related: bool | None = None,
    min_score: int | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    """Return medical-tourism leads with optional filters."""
    if _check_medtour_db_reachable():
        try:
            where_clauses: list[str] = []
            params: list[Any] = []
            if status:
                where_clauses.append("status = %s")
                params.append(status)
            if country:
                where_clauses.append("country ILIKE %s")
                params.append(country)
            if priority:
                where_clauses.append("priority = %s")
                params.append(priority)
            if dental_related is not None:
                where_clauses.append("dental_related = %s")
                params.append(dental_related)
            if india_related is not None:
                where_clauses.append("india_related = %s")
                params.append(india_related)
            if min_score is not None:
                where_clauses.append("outreach_score >= %s")
                params.append(min_score)
            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            sql = f"""
                SELECT * FROM medical_tourism_leads
                {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    colnames = [desc[0] for desc in cur.description]
                    return [dict(zip(colnames, row)) for row in cur.fetchall()]
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    if not os.path.exists(MEDTOUR_LEADS_CSV):
        return []
    rows = []
    with open(MEDTOUR_LEADS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if status and row.get("status") != status:
                continue
            if country and row.get("country", "").lower() != country.lower():
                continue
            if priority and row.get("priority") != priority:
                continue
            if dental_related is not None:
                val = row.get("dental_related", "").lower() in ("true", "1", "yes")
                if val != dental_related:
                    continue
            if india_related is not None:
                val = row.get("india_related", "").lower() in ("true", "1", "yes")
                if val != india_related:
                    continue
            if min_score is not None:
                try:
                    if int(row.get("outreach_score", 0)) < min_score:
                        continue
                except ValueError:
                    pass
            rows.append(row)
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return rows[offset : offset + limit]


def get_medical_tourism_leads_by_ids(ids: list[int]) -> list[dict]:
    """Return medical-tourism leads matching the provided IDs."""
    if not ids:
        return []
    if _check_medtour_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM medical_tourism_leads
                        WHERE id = ANY(%s)
                        ORDER BY created_at DESC
                        """,
                        (ids,),
                    )
                    colnames = [desc[0] for desc in cur.description]
                    return [dict(zip(colnames, row)) for row in cur.fetchall()]
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    if not os.path.exists(MEDTOUR_LEADS_CSV):
        return []
    rows = []
    id_set = set(ids)
    with open(MEDTOUR_LEADS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row_id = int(row["id"])
            except (ValueError, KeyError):
                row_id = -1
            if row_id in id_set:
                rows.append(row)
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return rows


def update_medical_tourism_lead_status(lead_id: int, status: str) -> bool:
    """Update the status of a medical-tourism lead."""
    if _check_medtour_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE medical_tourism_leads SET status = %s WHERE id = %s",
                        (status, lead_id),
                    )
                    updated = cur.rowcount > 0
                conn.commit()
            return updated
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    if not os.path.exists(MEDTOUR_LEADS_CSV):
        return False
    rows = []
    found = False
    with open(MEDTOUR_LEADS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row_id = int(row["id"])
            except (ValueError, KeyError):
                row_id = -1
            if row_id == lead_id:
                row["status"] = status
                found = True
            rows.append(row)
    if not found:
        return False
    with open(MEDTOUR_LEADS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_MEDTOUR_LEAD_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return True


def get_medical_tourism_lead_count(
    status: str | None = None,
    country: str | None = None,
    priority: str | None = None,
    dental_related: bool | None = None,
    india_related: bool | None = None,
    min_score: int | None = None,
) -> int:
    """Return total count of medical-tourism leads matching filters."""
    if _check_medtour_db_reachable():
        try:
            where_clauses: list[str] = []
            params: list[Any] = []
            if status:
                where_clauses.append("status = %s")
                params.append(status)
            if country:
                where_clauses.append("country ILIKE %s")
                params.append(country)
            if priority:
                where_clauses.append("priority = %s")
                params.append(priority)
            if dental_related is not None:
                where_clauses.append("dental_related = %s")
                params.append(dental_related)
            if india_related is not None:
                where_clauses.append("india_related = %s")
                params.append(india_related)
            if min_score is not None:
                where_clauses.append("outreach_score >= %s")
                params.append(min_score)
            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            sql = f"SELECT COUNT(*) FROM medical_tourism_leads {where_sql}"
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchone()[0] or 0
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback — count filtered rows
    return len(get_medical_tourism_leads(
        status=status, country=country, priority=priority,
        dental_related=dental_related, india_related=india_related,
        min_score=min_score, limit=999999, offset=0,
    ))


def log_medical_tourism_email(
    lead_id: int,
    email: str,
    name: str,
    organization: str,
    city: str,
    country: str,
    status: str,
) -> None:
    """Log an outreach email for a medical-tourism lead."""
    if _check_medtour_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO medical_tourism_email_log
                        (medtour_lead_id, email, name, organization, city, country, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """,
                        (lead_id, email, name, organization, city, country, status),
                    )
                conn.commit()
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    rows = []
    existing_ids = []
    if os.path.exists(MEDTOUR_EMAIL_LOG_CSV):
        with open(MEDTOUR_EMAIL_LOG_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                try:
                    existing_ids.append(int(row["id"]))
                except (ValueError, KeyError):
                    pass
    next_id = max(existing_ids) + 1 if existing_ids else 1
    new_row = {
        "id": str(next_id),
        "medtour_lead_id": str(lead_id),
        "email": email,
        "name": name,
        "organization": organization,
        "city": city,
        "country": country,
        "status": status,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    rows.append(new_row)
    log_fields = ["id", "medtour_lead_id", "email", "name", "organization",
                  "city", "country", "status", "sent_at"]
    with open(MEDTOUR_EMAIL_LOG_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=log_fields)
        writer.writeheader()
        writer.writerows(rows)


def get_medical_tourism_email_log() -> list[dict]:
    """Return the medical-tourism email log, newest first."""
    if _check_medtour_db_reachable():
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, medtour_lead_id, email, name, organization,
                               city, country, status, sent_at
                        FROM medical_tourism_email_log
                        ORDER BY sent_at DESC
                        """
                    )
                    colnames = [desc[0] for desc in cur.description]
                    return [dict(zip(colnames, row)) for row in cur.fetchall()]
        except psycopg2.OperationalError:
            pass  # fall through to CSV
    # CSV fallback
    if not os.path.exists(MEDTOUR_EMAIL_LOG_CSV):
        return []
    rows = []
    with open(MEDTOUR_EMAIL_LOG_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    rows.sort(key=lambda r: r.get("sent_at", ""), reverse=True)
    return rows
