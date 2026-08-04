"""
Seam for a real POS API integration. No POS API access exists yet for
Al Madina Nawes Supermarket, so this is a stub - the app currently gets
stock data via Excel import (catalog/excel_import.py) instead.

When a POS vendor is identified (e.g. Foodics, Loyverse, Odoo, or a custom
system), implement fetch_stock() below to call that vendor's API and return
the same shape excel_import.import_file() consumes. Nothing else in the app
(ai/agent.py, main.py, dashboard.py) needs to change - they only ever read
from catalog/store.py.
"""


class PosNotConfiguredError(Exception):
    pass


def fetch_stock() -> list[dict]:
    """Should return a list of dicts shaped like:
        {"sku": str | None, "name": str, "category": str | None, "unit": str | None,
         "price": float, "stock_qty": float}
    """
    raise PosNotConfiguredError(
        "No POS API configured yet for this store. Use the dashboard's Stock panel "
        "to upload an Excel export, or run: python -m catalog.excel_import <file.xlsx>"
    )


def sync_from_pos():
    """Once fetch_stock() is implemented, call this (e.g. from a scheduled
    job or an admin-triggered endpoint) to upsert live POS stock into
    catalog_items with source='pos_api'."""
    from catalog import store as catalog_store

    items = fetch_stock()
    for item in items:
        catalog_store.upsert_item(
            name=item["name"], price=item["price"], stock_qty=item["stock_qty"],
            sku=item.get("sku"), category=item.get("category"), unit=item.get("unit"),
            source="pos_api",
        )
    return len(items)
