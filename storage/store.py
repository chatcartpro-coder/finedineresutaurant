"""
Lightweight SQLite storage - no external DB needed to get started.
Tracks customers, conversation logs, in-progress/confirmed orders (incl. the
delivery-agent status lifecycle), and message dedup. Swap for Postgres later
by replacing this module if you outgrow SQLite (schema below avoids
SQLite-only syntax where practical).
"""
import os
import sqlite3
import threading
from datetime import datetime, timezone

from config import config

_local = threading.local()


def _get_conn():
    if not hasattr(_local, "conn"):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _local.conn.execute("PRAGMA foreign_keys = ON")
        _init_schema(_local.conn)
    return _local.conn


def _init_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS customers (
        phone TEXT PRIMARY KEY,
        name TEXT,
        last_lat REAL,
        last_lng REAL,
        last_location_label TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        direction TEXT,        -- 'in' or 'out'
        message TEXT,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS processed_messages (
        message_id TEXT PRIMARY KEY,
        processed_at TEXT
    );

    -- status lifecycle: draft -> awaiting_confirmation -> confirmed
    --                    -> packed -> picked_up -> delivered
    --                 (or -> cancelled at any point before packed)
    -- packed/picked_up/delivered only apply to delivery orders, driven by
    -- the assigned delivery_agents member replying on WhatsApp; pickup
    -- orders go confirmed -> delivered directly (customer collects in person).
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        status TEXT DEFAULT 'draft',
        subtotal REAL DEFAULT 0,
        delivery_fee REAL DEFAULT 0,
        total REAL DEFAULT 0,
        delivery_lat REAL,
        delivery_lng REAL,
        delivery_address_text TEXT,
        is_pickup INTEGER DEFAULT 0,
        delivery_agent_phone TEXT,
        notes TEXT,
        created_at TEXT,
        confirmed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER REFERENCES orders(id),
        catalog_item_id INTEGER,
        item_name_snapshot TEXT,
        unit_price_snapshot REAL,
        qty REAL,
        line_total REAL
    );

    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        discount_type TEXT NOT NULL,   -- 'percent' | 'fixed'
        discount_value REAL NOT NULL,
        scope_type TEXT NOT NULL DEFAULT 'all',  -- 'all' | 'category' | 'items'
        scope_value TEXT,              -- JSON list of category names or catalog_item_ids
        starts_at TEXT,
        ends_at TEXT,
        status TEXT NOT NULL DEFAULT 'draft',   -- draft | active | expired
        created_by_admin_id INTEGER,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS printer_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        connection_type TEXT NOT NULL DEFAULT 'network',  -- 'network' | 'bluetooth' | 'usb'
        printer_ip TEXT,
        printer_port TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS delivery_agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE NOT NULL,
        name TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT
    );
    """)
    conn.commit()

    # Additive columns on an existing table - guard against re-running on a DB
    # that already has them (SQLite has no "ADD COLUMN IF NOT EXISTS").
    cols = [row[1] for row in conn.execute("PRAGMA table_info(orders)").fetchall()]
    if "discount_applied" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN discount_applied INTEGER")
        conn.commit()
    if "printed_at" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN printed_at TEXT")
        conn.commit()


# ---- Message dedup (Meta webhook retry protection) ----

def already_processed(message_id: str) -> bool:
    conn = _get_conn()
    cur = conn.execute("SELECT 1 FROM processed_messages WHERE message_id = ?", (message_id,))
    return cur.fetchone() is not None


def mark_processed(message_id: str):
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO processed_messages (message_id, processed_at) VALUES (?, ?)",
        (message_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


# ---- Customers ----

def get_customer(phone: str):
    conn = _get_conn()
    cur = conn.execute(
        "SELECT phone, name, last_lat, last_lng, last_location_label FROM customers WHERE phone = ?",
        (phone,),
    )
    row = cur.fetchone()
    if not row:
        return None
    keys = ["phone", "name", "last_lat", "last_lng", "last_location_label"]
    return dict(zip(keys, row))


def upsert_customer(phone: str, name: str = None, lat: float = None, lng: float = None, label: str = None):
    existing = get_customer(phone)
    conn = _get_conn()
    conn.execute("""
        INSERT INTO customers (phone, name, last_lat, last_lng, last_location_label, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(phone) DO UPDATE SET
            name=COALESCE(excluded.name, customers.name),
            last_lat=COALESCE(excluded.last_lat, customers.last_lat),
            last_lng=COALESCE(excluded.last_lng, customers.last_lng),
            last_location_label=COALESCE(excluded.last_location_label, customers.last_location_label),
            updated_at=excluded.updated_at
    """, (phone, name, lat, lng, label, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    return existing


def set_customer_location(phone: str, lat: float, lng: float, label: str = None):
    upsert_customer(phone, lat=lat, lng=lng, label=label)


# ---- Conversations ----

def log_message(phone: str, direction: str, message: str):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO conversations (phone, direction, message, created_at) VALUES (?, ?, ?, ?)",
        (phone, direction, message, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_recent_history(phone: str, limit: int = 10):
    """Returns recent messages oldest-first, for conversation context."""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT direction, message FROM conversations WHERE phone = ? ORDER BY id DESC LIMIT ?",
        (phone, limit),
    )
    rows = cur.fetchall()
    return list(reversed(rows))


# ---- Orders ----

_ORDER_COLUMNS = (
    "id, phone, status, subtotal, delivery_fee, total, delivery_lat, delivery_lng, "
    "delivery_address_text, is_pickup, delivery_agent_phone, notes, created_at, confirmed_at, "
    "discount_applied, printed_at"
)


def get_active_order(phone: str):
    """Returns the customer's current draft/awaiting_confirmation order, if any."""
    conn = _get_conn()
    cur = conn.execute(f"""
        SELECT {_ORDER_COLUMNS}
        FROM orders
        WHERE phone = ? AND status IN ('draft', 'awaiting_confirmation')
        ORDER BY id DESC LIMIT 1
    """, (phone,))
    row = cur.fetchone()
    if not row:
        return None
    return _order_row_to_dict(row)


def create_order(phone: str) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO orders (phone, status, created_at) VALUES (?, 'draft', ?)",
        (phone, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def get_order(order_id: int):
    conn = _get_conn()
    cur = conn.execute(f"""
        SELECT {_ORDER_COLUMNS}
        FROM orders WHERE id = ?
    """, (order_id,))
    row = cur.fetchone()
    return _order_row_to_dict(row) if row else None


def get_order_items(order_id: int):
    conn = _get_conn()
    cur = conn.execute("""
        SELECT id, catalog_item_id, item_name_snapshot, unit_price_snapshot, qty, line_total
        FROM order_items WHERE order_id = ?
    """, (order_id,))
    keys = ["id", "catalog_item_id", "item_name_snapshot", "unit_price_snapshot", "qty", "line_total"]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def add_order_item(order_id: int, catalog_item_id: int, name: str, unit_price: float, qty: float):
    conn = _get_conn()
    line_total = round(unit_price * qty, 2)
    conn.execute("""
        INSERT INTO order_items (order_id, catalog_item_id, item_name_snapshot, unit_price_snapshot, qty, line_total)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (order_id, catalog_item_id, name, unit_price, qty, line_total))
    conn.commit()
    _recalc_order_totals(order_id)


def remove_order_item(item_id: int):
    conn = _get_conn()
    cur = conn.execute("SELECT order_id FROM order_items WHERE id = ?", (item_id,))
    row = cur.fetchone()
    if not row:
        return
    order_id = row[0]
    conn.execute("DELETE FROM order_items WHERE id = ?", (item_id,))
    conn.commit()
    _recalc_order_totals(order_id)


def _recalc_order_totals(order_id: int):
    """Recomputes subtotal/total from line items. If a discount offer is
    already applied (discount_applied), re-derives its amount via
    offers.store.compute_discount so adding/removing items keeps the
    discount consistent with the new subtotal."""
    conn = _get_conn()
    subtotal = conn.execute(
        "SELECT COALESCE(SUM(line_total), 0) FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchone()[0]
    order = get_order(order_id)
    delivery_fee = order["delivery_fee"] or 0

    discount = 0.0
    if order["discount_applied"]:
        from offers.store import compute_discount, get_offer
        offer = get_offer(order["discount_applied"])
        if offer:
            discount = compute_discount(offer, subtotal)

    conn.execute(
        "UPDATE orders SET subtotal = ?, total = ? WHERE id = ?",
        (subtotal, max(subtotal - discount, 0) + delivery_fee, order_id),
    )
    conn.commit()


def set_order_delivery(order_id: int, lat: float, lng: float, delivery_fee: float, address_text: str = None):
    conn = _get_conn()
    order = get_order(order_id)
    discount = 0.0
    if order["discount_applied"]:
        from offers.store import compute_discount, get_offer
        offer = get_offer(order["discount_applied"])
        if offer:
            discount = compute_discount(offer, order["subtotal"] or 0)
    total = max((order["subtotal"] or 0) - discount, 0) + delivery_fee
    conn.execute("""
        UPDATE orders SET delivery_lat = ?, delivery_lng = ?, delivery_fee = ?, total = ?, delivery_address_text = ?
        WHERE id = ?
    """, (lat, lng, delivery_fee, total, address_text, order_id))
    conn.commit()


def set_order_delivery_text(order_id: int, address_text: str, delivery_fee: float):
    """Sibling to set_order_delivery for customers who type their address as
    plain text instead of sharing a WhatsApp location pin - delivery_lat/lng
    are left NULL (no coordinates available), so callers that build a map
    link (e.g. main.py's delivery-agent notification) correctly skip it for
    these orders, same as if location were simply never shared."""
    conn = _get_conn()
    order = get_order(order_id)
    discount = 0.0
    if order["discount_applied"]:
        from offers.store import compute_discount, get_offer
        offer = get_offer(order["discount_applied"])
        if offer:
            discount = compute_discount(offer, order["subtotal"] or 0)
    total = max((order["subtotal"] or 0) - discount, 0) + delivery_fee
    conn.execute("""
        UPDATE orders SET delivery_lat = NULL, delivery_lng = NULL, delivery_fee = ?, total = ?, delivery_address_text = ?
        WHERE id = ?
    """, (delivery_fee, total, address_text, order_id))
    conn.commit()


def set_order_pickup(order_id: int):
    """Marks an order as pickup instead of delivery - no delivery fee, no
    location needed, and the delivery-agent flow is skipped entirely since
    there's nothing to hand off."""
    conn = _get_conn()
    order = get_order(order_id)
    discount = 0.0
    if order["discount_applied"]:
        from offers.store import compute_discount, get_offer
        offer = get_offer(order["discount_applied"])
        if offer:
            discount = compute_discount(offer, order["subtotal"] or 0)
    total = max((order["subtotal"] or 0) - discount, 0)
    conn.execute(
        "UPDATE orders SET is_pickup = 1, delivery_fee = 0, total = ? WHERE id = ?",
        (total, order_id),
    )
    conn.commit()


def apply_order_discount(order_id: int, offer_id: int | None):
    """Sets/clears which offer applies to an order and recomputes its total.
    offer_id=None clears any applied discount."""
    conn = _get_conn()
    conn.execute("UPDATE orders SET discount_applied = ? WHERE id = ?", (offer_id, order_id))
    conn.commit()
    _recalc_order_totals(order_id)


def set_order_status(order_id: int, status: str):
    conn = _get_conn()
    if status == "confirmed":
        conn.execute(
            "UPDATE orders SET status = ?, confirmed_at = ? WHERE id = ?",
            (status, datetime.now(timezone.utc).isoformat(), order_id),
        )
    else:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()


def assign_delivery_agent(order_id: int, agent_phone: str):
    conn = _get_conn()
    conn.execute("UPDATE orders SET delivery_agent_phone = ? WHERE id = ?", (agent_phone, order_id))
    conn.commit()


def get_order_assigned_to_agent(agent_phone: str):
    """The delivery agent's current active order (packed or picked_up) -
    used to route the agent's next PACKED/PICKED/DELIVERED reply to the
    right order without them needing to type an order number."""
    conn = _get_conn()
    cur = conn.execute(f"""
        SELECT {_ORDER_COLUMNS}
        FROM orders
        WHERE delivery_agent_phone = ? AND status IN ('confirmed', 'packed', 'picked_up')
        ORDER BY confirmed_at DESC LIMIT 1
    """, (agent_phone,))
    row = cur.fetchone()
    return _order_row_to_dict(row) if row else None


# ---- Thermal printer integration ----
# printed_at tracks whether a confirmed order has already been sent to the
# restaurant's print agent, so a flaky network retry from that agent can
# never print the same receipt twice (same idempotency shape as
# processed_messages, but a nullable column rather than a separate table
# since this is a simple one-shot per-order flag). Printer integration is
# deferred for this restaurant but the mechanism is ready to go.

def is_order_printed(order_id: int) -> bool:
    conn = _get_conn()
    cur = conn.execute("SELECT printed_at FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    return bool(row and row[0])


def mark_order_printed(order_id: int):
    conn = _get_conn()
    conn.execute(
        "UPDATE orders SET printed_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), order_id),
    )
    conn.commit()


def get_unprinted_confirmed_orders():
    conn = _get_conn()
    cur = conn.execute(f"""
        SELECT {_ORDER_COLUMNS}
        FROM orders
        WHERE status = 'confirmed' AND printed_at IS NULL
        ORDER BY confirmed_at ASC
    """)
    return [_order_row_to_dict(row) for row in cur.fetchall()]


def _order_row_to_dict(row):
    keys = ["id", "phone", "status", "subtotal", "delivery_fee", "total", "delivery_lat", "delivery_lng",
            "delivery_address_text", "is_pickup", "delivery_agent_phone", "notes", "created_at", "confirmed_at",
            "discount_applied", "printed_at"]
    return dict(zip(keys, row))


# ---- Delivery agents ----
# The restaurant's registered delivery riders. Each drives their assigned
# order's status (packed -> picked_up -> delivered) by replying on WhatsApp -
# see main.py::handle_delivery_agent_message.

def list_delivery_agents(active_only: bool = False):
    conn = _get_conn()
    where = "WHERE active = 1" if active_only else ""
    cur = conn.execute(f"SELECT id, phone, name, active, created_at FROM delivery_agents {where} ORDER BY name")
    keys = ["id", "phone", "name", "active", "created_at"]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def get_delivery_agent_by_phone(phone: str):
    conn = _get_conn()
    cur = conn.execute("SELECT id, phone, name, active, created_at FROM delivery_agents WHERE phone = ?", (phone,))
    row = cur.fetchone()
    if not row:
        return None
    keys = ["id", "phone", "name", "active", "created_at"]
    return dict(zip(keys, row))


def add_delivery_agent(phone: str, name: str):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO delivery_agents (phone, name, active, created_at) VALUES (?, ?, 1, ?)
        ON CONFLICT(phone) DO UPDATE SET name = excluded.name, active = 1
    """, (phone, name, datetime.now(timezone.utc).isoformat()))
    conn.commit()


def set_delivery_agent_active(agent_id: int, active: bool):
    conn = _get_conn()
    conn.execute("UPDATE delivery_agents SET active = ? WHERE id = ?", (int(active), agent_id))
    conn.commit()


def get_next_available_delivery_agent():
    """Simplest v1 assignment: the first active agent. A small restaurant
    with one or two riders doesn't need real dispatch/load-balancing yet."""
    agents = list_delivery_agents(active_only=True)
    return agents[0] if agents else None


# ---- Admins ----

def get_admin_by_username(username: str):
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, username, password_hash, created_at FROM admins WHERE username = ?", (username,)
    )
    row = cur.fetchone()
    if not row:
        return None
    keys = ["id", "username", "password_hash", "created_at"]
    return dict(zip(keys, row))


def get_admin_by_id(admin_id: int):
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, username, password_hash, created_at FROM admins WHERE id = ?", (admin_id,)
    )
    row = cur.fetchone()
    if not row:
        return None
    keys = ["id", "username", "password_hash", "created_at"]
    return dict(zip(keys, row))


def create_admin(username: str, password_hash: str) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, password_hash, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def set_admin_password(admin_id: int, password_hash: str):
    conn = _get_conn()
    conn.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (password_hash, admin_id))
    conn.commit()


def any_admin_exists() -> bool:
    conn = _get_conn()
    return conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0] > 0


# ---- Printer settings ----
# Single-row config (id is constrained to 1) for the restaurant's thermal
# printer connection, editable from the admin dashboard's Printer page.
# Not required to be configured - printer integration is deferred for this
# project, but the mechanism (and print_agent/) is copied over ready to go.

def get_printer_settings():
    conn = _get_conn()
    cur = conn.execute(
        "SELECT connection_type, printer_ip, printer_port, updated_at FROM printer_settings WHERE id = 1"
    )
    row = cur.fetchone()
    if not row:
        return None
    keys = ["connection_type", "printer_ip", "printer_port", "updated_at"]
    return dict(zip(keys, row))


def set_printer_settings(connection_type: str, printer_ip: str = None, printer_port: str = None):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO printer_settings (id, connection_type, printer_ip, printer_port, updated_at)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            connection_type=excluded.connection_type,
            printer_ip=excluded.printer_ip,
            printer_port=excluded.printer_port,
            updated_at=excluded.updated_at
    """, (connection_type, printer_ip, printer_port, datetime.now(timezone.utc).isoformat()))
    conn.commit()


# ---- Dashboard / analytics queries ----
# created_at is stored as ISO 8601 UTC. start/end below are "YYYY-MM-DD"
# strings (inclusive), compared as text - this works against ISO timestamps.

def get_stats(start: str = None, end: str = None):
    conn = _get_conn()
    where, params = _date_where(start, end)

    total_in = conn.execute(f"SELECT COUNT(*) FROM conversations WHERE direction='in' {where}", params).fetchone()[0]
    total_out = conn.execute(f"SELECT COUNT(*) FROM conversations WHERE direction='out' {where}", params).fetchone()[0]
    unique_customers = conn.execute(f"SELECT COUNT(DISTINCT phone) FROM conversations WHERE 1=1 {where}", params).fetchone()[0]
    orders_confirmed = conn.execute(
        f"SELECT COUNT(*) FROM orders WHERE status IN ('confirmed','packed','picked_up','delivered') {where}", params
    ).fetchone()[0]
    revenue = conn.execute(
        f"SELECT COALESCE(SUM(total), 0) FROM orders WHERE status IN ('confirmed','packed','picked_up','delivered') {where}", params
    ).fetchone()[0]

    return {
        "messages_received": total_in,
        "replies_sent": total_out,
        "unique_customers": unique_customers,
        "orders_confirmed": orders_confirmed,
        "revenue": revenue,
    }


def get_daily_counts(start: str = None, end: str = None):
    conn = _get_conn()
    where, params = _date_where(start, end)
    cur = conn.execute(f"""
        SELECT substr(created_at, 1, 10) AS day,
               SUM(CASE WHEN direction='in' THEN 1 ELSE 0 END) AS received,
               SUM(CASE WHEN direction='out' THEN 1 ELSE 0 END) AS sent
        FROM conversations
        WHERE 1=1 {where}
        GROUP BY day
        ORDER BY day
    """, params)
    return [{"day": row[0], "received": row[1], "sent": row[2]} for row in cur.fetchall()]


def get_customers_summary(start: str = None, end: str = None):
    conn = _get_conn()
    where, params = _date_where(start, end)
    cur = conn.execute(f"""
        SELECT c.phone,
               COALESCE(cu.name, ''),
               COUNT(*) AS message_count,
               MAX(c.created_at) AS last_message_at
        FROM conversations c
        LEFT JOIN customers cu ON cu.phone = c.phone
        WHERE 1=1 {where}
        GROUP BY c.phone
        ORDER BY last_message_at DESC
    """, params)
    keys = ["phone", "name", "message_count", "last_message_at"]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def get_conversation(phone: str, start: str = None, end: str = None):
    conn = _get_conn()
    where, params = _date_where(start, end)
    cur = conn.execute(f"""
        SELECT direction, message, created_at
        FROM conversations
        WHERE phone = ? {where}
        ORDER BY id ASC
    """, (phone, *params))
    keys = ["direction", "message", "created_at"]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def get_all_messages(start: str = None, end: str = None):
    conn = _get_conn()
    where, params = _date_where(start, end)
    cur = conn.execute(f"""
        SELECT c.created_at, c.phone, COALESCE(cu.name, ''), c.direction, c.message
        FROM conversations c
        LEFT JOIN customers cu ON cu.phone = c.phone
        WHERE 1=1 {where}
        ORDER BY c.created_at ASC
    """, params)
    keys = ["created_at", "phone", "name", "direction", "message"]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def get_orders(start: str = None, end: str = None, status: str = None):
    conn = _get_conn()
    where, params = _date_where(start, end)
    if status:
        where += " AND status = ?"
        params = list(params) + [status]
    cur = conn.execute(f"""
        SELECT {_ORDER_COLUMNS}
        FROM orders
        WHERE 1=1 {where}
        ORDER BY created_at DESC
    """, params)
    return [_order_row_to_dict(row) for row in cur.fetchall()]


def get_customer_orders(phone: str, start: str = None, end: str = None):
    """All orders for one customer, newest first - used for the per-customer
    order history view (grouped further by get_customer_orders_by_month)."""
    conn = _get_conn()
    where, params = _date_where(start, end)
    cur = conn.execute(f"""
        SELECT {_ORDER_COLUMNS}
        FROM orders
        WHERE phone = ? {where}
        ORDER BY created_at DESC
    """, (phone, *params))
    return [_order_row_to_dict(row) for row in cur.fetchall()]


def get_customer_orders_by_month(phone: str, start: str = None, end: str = None):
    """One row per calendar month this customer has orders in, newest first -
    same substr(created_at, 1, N) grouping style as get_daily_counts, just
    grouped by month (YYYY-MM) instead of day, and scoped to one phone."""
    conn = _get_conn()
    where, params = _date_where(start, end)
    cur = conn.execute(f"""
        SELECT substr(created_at, 1, 7) AS year_month,
               COUNT(*) AS order_count,
               COALESCE(SUM(total), 0) AS total_spent
        FROM orders
        WHERE phone = ? {where}
        GROUP BY year_month
        ORDER BY year_month DESC
    """, (phone, *params))
    return [{"year_month": row[0], "order_count": row[1], "total_spent": row[2]} for row in cur.fetchall()]


def get_orders_by_month(start: str = None, end: str = None):
    """Store-wide version of get_customer_orders_by_month - one row per
    calendar month across all customers, for the Reports yearly rollup."""
    conn = _get_conn()
    where, params = _date_where(start, end)
    cur = conn.execute(f"""
        SELECT substr(created_at, 1, 7) AS year_month,
               COUNT(*) AS order_count,
               COALESCE(SUM(total), 0) AS total_revenue,
               COUNT(DISTINCT phone) AS unique_customers
        FROM orders
        WHERE status IN ('confirmed', 'packed', 'picked_up', 'delivered') {where}
        GROUP BY year_month
        ORDER BY year_month DESC
    """, params)
    keys = ["year_month", "order_count", "total_revenue", "unique_customers"]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def get_top_selling_items(start: str = None, end: str = None, limit: int = 10):
    """Best-selling menu items by quantity sold, for the Reports monthly
    summary - grouped over order_items joined to confirmed+ orders in range."""
    conn = _get_conn()
    where, params = _date_where(start, end)
    cur = conn.execute(f"""
        SELECT oi.item_name_snapshot AS name,
               SUM(oi.qty) AS total_qty,
               COALESCE(SUM(oi.line_total), 0) AS total_revenue
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.status IN ('confirmed', 'packed', 'picked_up', 'delivered') {where}
        GROUP BY oi.item_name_snapshot
        ORDER BY total_qty DESC
        LIMIT ?
    """, (*params, limit))
    keys = ["name", "total_qty", "total_revenue"]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def get_customer_favorite_items(phone: str, limit: int = 5):
    """A customer's most-ordered menu items by quantity - purchase-behavior
    signal shown on their dashboard profile, same join shape as
    get_top_selling_items but scoped to one phone, across all time."""
    conn = _get_conn()
    cur = conn.execute("""
        SELECT oi.item_name_snapshot AS name,
               SUM(oi.qty) AS total_qty,
               COALESCE(SUM(oi.line_total), 0) AS total_spent
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.phone = ? AND o.status IN ('confirmed', 'packed', 'picked_up', 'delivered')
        GROUP BY oi.item_name_snapshot
        ORDER BY total_qty DESC
        LIMIT ?
    """, (phone, limit))
    keys = ["name", "total_qty", "total_spent"]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def _date_where(start: str, end: str):
    clauses, params = [], []
    if start:
        clauses.append("created_at >= ?")
        params.append(f"{start}T00:00:00")
    if end:
        clauses.append("created_at <= ?")
        params.append(f"{end}T23:59:59.999999")
    where = ("AND " + " AND ".join(clauses)) if clauses else ""
    return where, params
