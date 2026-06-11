"""Product catalogue loader.

Reads irus_products.csv and serves JSON to the frontend as well as a
formatted text block for Claude's system prompt.
"""

import csv
from config import PRODUCTS_FILE


def get_catalogue_json() -> list[dict]:
    """Return the full product catalogue as a list of dicts.

    Each dict contains:
        - product_name (str)
        - description (str)
        - domain (str)  # "Defence" or "Medical"
    """
    products = []
    with open(PRODUCTS_FILE, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            products.append(
                {
                    "product_name": row.get("Product Name", "").strip(),
                    "description": row.get("Description", "").strip(),
                    "domain": row.get("Domain", "").strip(),
                }
            )
    return products


def format_selected_catalogue(selected_products: list[str]) -> str:
    """Format *only* the user-selected products for Claude's system prompt.

    Args:
        selected_products: List of product names chosen in the UI.

    Returns:
        A clean text block:
            - PRODUCT NAME: Short description (first 120 chars)
    """
    catalogue = get_catalogue_json()
    selected_set = {name.strip() for name in selected_products}

    lines = []
    for item in catalogue:
        if item["product_name"] in selected_set:
            short_desc = item["description"][:120]
            if len(item["description"]) > 120:
                short_desc = short_desc.rsplit(" ", 1)[0] + "..."
            lines.append(f"- {item['product_name']}: {short_desc}")

    return "\n".join(lines) if lines else "No products selected."
