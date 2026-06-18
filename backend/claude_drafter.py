"""Email drafting module.

Generates personalised emails using a fixed template with product-specific references.
"""

from typing import Tuple


FROM_NAME = "IRUS Business Development"
PHONE = "+91 956091633"


def _extract_product_names(selected_products_text: str) -> str:
    """Extract clean product names from the formatted catalogue text.

    Returns:
        A human-readable product clause for the email body.
    """
    names = []
    for line in selected_products_text.split("\n"):
        line = line.strip()
        if line.startswith("-"):
            without_bullet = line[1:].strip()
            if ":" in without_bullet:
                names.append(without_bullet.split(":", 1)[0].strip())
            else:
                names.append(without_bullet)

    if not names:
        return "our new Mobile Medical Vehicle product"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def draft_email(lead: dict, selected_products_text: str) -> Tuple[str, str]:
    """Return a template-based outreach email for a single lead.

    Args:
        lead: Enriched lead dict.
        selected_products_text: Formatted text of user-selected products.

    Returns:
        (subject, body) strings.
    """
    name = lead.get("name", "").strip()
    product_line = _extract_product_names(selected_products_text)

    product_phrase = ""
    subject = ""
    if "," in product_line or " and " in product_line:
        product_phrase = f"regarding new products that we were keen to launch which include {product_line}"
        subject = "Meeting Request - New Product Launch"
    else:
        product_phrase = f"regarding a new product that we were keen to launch which is a {product_line}"
        subject = f"Meeting Request - {product_line}"

    body = (
        f"Hello {name or 'Sir/Madam'},\n\n"
        "I lead Oxygen 2 Innovation and we provide hospitals with digital healthcare solutions "
        "integrated with Mobile Medical Vehicles enabling hospitals to deliver smarter and more "
        "connected healthcare services.\n\n"
        f"I was keen to meet to demonstrate these solutions and to take your inputs "
        f"{product_phrase}.\n\n"
        "I wanted to meet you with that regard. Would appreciate it if you could let me know a "
        "convenient time.\n\n"
        "You can learn more about us at https://www.irus.ind.in/\n\n"
        "Best Regards,\n"
        f"{FROM_NAME}\n"
        f"Ph - {PHONE}"
    )

    return subject, body


# Keep signatures compatible with older callers / fallback paths.

def _build_system_prompt(domain: str, selected_products_text: str) -> str:
    return ""


def _build_user_content(lead: dict) -> str:
    return ""


def _parse_response(raw: str, lead: dict) -> Tuple[str, str]:
    return draft_email(lead, raw)


def _fallback_email(lead: dict) -> Tuple[str, str]:
    return draft_email(lead, "")
