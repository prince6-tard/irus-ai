"""xAI email drafting module.

Drafts personalised cold emails using the xAI API (grok-3-latest)
by injecting the *specifically selected* IRUS products into the system prompt.
"""

import os
from typing import Tuple

import requests
from dotenv import load_dotenv

from config import XAI_MAX_TOKENS, XAI_MODEL

load_dotenv()

XAI_API_KEY = os.getenv("XAI_API_KEY", "")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
FROM_NAME = os.getenv("FROM_NAME", "IRUS Business Development")


def _build_system_prompt(domain: str, selected_products_text: str) -> str:
    """Assemble the system prompt for xAI."""
    if domain.lower() == "defence":
        tone = "formal, peer-to-peer, and confident"
    elif domain.lower() == "medical":
        tone = "warm, credible, and human"
    else:
        tone = "professional and concise"

    prompt = f"""You are an expert business development executive at IRUS, an Indian company that manufactures defence technology and medical mobility solutions.

Your task is to draft a single, highly personalised cold outreach email to a prospective client.

TONE: {tone}

WRITING RULES:
- Use plain text ONLY. No bullet points, markdown, bold, italics, or asterisks.
- The body must be under 180 words.
- Select only 1 or 2 products from the provided list that are strictly relevant to the recipient's organisation.
- Start with a natural, context-aware opening sentence.
- Do NOT mention pricing, discounts, or promotional language.
- End by inviting the recipient to a 20-minute call or demo.
- Sign off exactly as:

Warm regards,
{FROM_NAME}
IRUS | www.irus.in

SELECTED PRODUCTS FOR THIS CAMPAIGN:
{selected_products_text}

OUTPUT FORMAT (strict):
SUBJECT: <write an engaging, specific subject line here>
BODY:
<write the email body here, following all rules above>
"""
    return prompt


def _build_user_content(lead: dict) -> str:
    """Build the user message content from lead metadata."""
    org = lead.get("organization", "their organisation")
    role = lead.get("role", "professional")
    city = lead.get("city", "")
    country = lead.get("country", "")
    name = lead.get("name", "").strip()

    parts = [f"Recipient name: {name or 'Unknown'}"]
    parts.append(f"Organisation: {org}")
    parts.append(f"Role: {role}")
    if city and country:
        parts.append(f"Location: {city}, {country}")
    elif country:
        parts.append(f"Location: {country}")
    parts.append("\nPlease draft the outreach email now.")

    return "\n".join(parts)


def draft_email(lead: dict, selected_products_text: str) -> Tuple[str, str]:
    """Draft a personalised email for a single lead using xAI.

    Args:
        lead: Enriched lead dict.
        selected_products_text: Formatted text of user-selected products.

    Returns:
        (subject, body) strings. Falls back to a safe default on any error.
    """
    if not XAI_API_KEY:
        print("Warning: XAI_API_KEY not set. Returning fallback email.")
        return _fallback_email(lead)

    domain = lead.get("category", "")
    system_prompt = _build_system_prompt(domain, selected_products_text)
    user_content = _build_user_content(lead)

    try:
        resp = requests.post(
            XAI_API_URL,
            headers={
                "Authorization": f"Bearer {XAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": XAI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": XAI_MAX_TOKENS,
                "temperature": 0.7,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"xAI API error for {lead.get('name', 'Unknown')}: {exc}")
        return _fallback_email(lead)

    return _parse_response(raw, lead)


def _parse_response(raw: str, lead: dict) -> Tuple[str, str]:
    """Parse xAI response into (subject, body)."""
    subject = "Exploring synergies with IRUS"
    body = raw.strip()

    try:
        normalized = raw.replace("Body:", "BODY:")
        if "SUBJECT:" in normalized and "BODY:" in normalized:
            subject_part = normalized.split("SUBJECT:", 1)[1]
            subject_body = subject_part.split("BODY:", 1)
            subject = subject_body[0].strip()
            body = subject_body[1].strip() if len(subject_body) > 1 else raw.strip()
        elif "BODY:" in normalized:
            body = normalized.split("BODY:", 1)[1].strip()
    except Exception as exc:
        print(f"Email parsing error for {lead.get('name', 'Unknown')}: {exc}")
        body = raw.strip()

    if not subject:
        subject = "Exploring synergies with IRUS"

    return subject, body


def _fallback_email(lead: dict) -> Tuple[str, str]:
    """Return a safe fallback email when xAI is unavailable."""
    org = lead.get("organization", "your organisation")
    name = lead.get("name", "").strip().split()[0] if lead.get("name") else "there"
    if not name:
        name = "there"

    subject = "Exploring synergies with IRUS"
    body = (
        f"Hi {name},\n\n"
        f"I hope this message finds you well. I came across {org} and was impressed by "
        "the work you are doing in the space.\n\n"
        "At IRUS, we specialise in advanced defence technology and medical mobility solutions. "
        "I believe there may be meaningful synergies between our offerings and your organisation's goals.\n\n"
        "Would you be open to a brief 20-minute call this week to explore how we might collaborate?\n\n"
        "Warm regards,\n"
        f"{FROM_NAME}\n"
        "IRUS | www.irus.in"
    )
    return subject, body
