"""
CRUD for promotional offers, plus the discount-computation logic shared by
storage/store.py (order total recalculation) and the WhatsApp ordering
agent (so it can mention active offers when relevant).
"""
import json
from datetime import datetime, timezone

from storage.store import _get_conn


def list_offers(status: str = None):
    conn = _get_conn()
    where, params = "", []
    if status:
        where, params = "WHERE status = ?", [status]
    cur = conn.execute(f"""
        SELECT id, title, description, discount_type, discount_value, scope_type, scope_value,
               starts_at, ends_at, status, created_by_admin_id, created_at
        FROM offers {where}
        ORDER BY created_at DESC
    """, params)
    return [_row_to_dict(row) for row in cur.fetchall()]


def get_offer(offer_id: int):
    conn = _get_conn()
    cur = conn.execute("""
        SELECT id, title, description, discount_type, discount_value, scope_type, scope_value,
               starts_at, ends_at, status, created_by_admin_id, created_at
        FROM offers WHERE id = ?
    """, (offer_id,))
    row = cur.fetchone()
    return _row_to_dict(row) if row else None


def create_offer(title: str, description: str, discount_type: str, discount_value: float,
                  scope_type: str = "all", scope_value: list = None, starts_at: str = None,
                  ends_at: str = None, status: str = "draft", created_by_admin_id: int = None) -> int:
    conn = _get_conn()
    cur = conn.execute("""
        INSERT INTO offers (title, description, discount_type, discount_value, scope_type, scope_value,
                             starts_at, ends_at, status, created_by_admin_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, description, discount_type, discount_value, scope_type,
          json.dumps(scope_value or []), starts_at, ends_at, status, created_by_admin_id,
          datetime.now(timezone.utc).isoformat()))
    conn.commit()
    return cur.lastrowid


def set_offer_status(offer_id: int, status: str):
    conn = _get_conn()
    conn.execute("UPDATE offers SET status = ? WHERE id = ?", (status, offer_id))
    conn.commit()


def delete_offer(offer_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM offers WHERE id = ?", (offer_id,))
    conn.commit()


def get_active_offers():
    """Active offers whose date range currently covers 'now' (or has no range set)."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    cur = conn.execute("""
        SELECT id, title, description, discount_type, discount_value, scope_type, scope_value,
               starts_at, ends_at, status, created_by_admin_id, created_at
        FROM offers
        WHERE status = 'active'
          AND (starts_at IS NULL OR starts_at <= ?)
          AND (ends_at IS NULL OR ends_at >= ?)
    """, (now, now))
    return [_row_to_dict(row) for row in cur.fetchall()]


def compute_discount(offer: dict, subtotal: float) -> float:
    """Discount amount in currency units for a given subtotal under this
    offer. Scope narrowing (category/specific items) is intentionally not
    applied here - this computes against the whole order subtotal, which is
    correct for scope_type='all' and a reasonable approximation otherwise
    for v1 (per-line-item scoped discounts are a natural follow-up)."""
    if offer["discount_type"] == "percent":
        return round(subtotal * (offer["discount_value"] / 100), 2)
    return min(offer["discount_value"], subtotal)


def _row_to_dict(row):
    keys = ["id", "title", "description", "discount_type", "discount_value", "scope_type", "scope_value",
            "starts_at", "ends_at", "status", "created_by_admin_id", "created_at"]
    d = dict(zip(keys, row))
    d["scope_value"] = json.loads(d["scope_value"]) if d["scope_value"] else []
    return d
