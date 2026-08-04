"""
DEMO-ONLY module: an in-dashboard chat simulator so the restaurant owner can
show a client how the WhatsApp ordering flow (knowledge-base clarifications,
cart building, delivery/pickup, order confirmation) behaves, without a live,
Meta-approved WhatsApp number - useful while Business/Access verification is
still under review.

This talks to the exact same ai/agent.py + main.py::handle_customer_message
logic real WhatsApp messages go through, so what's demoed here matches
production behavior. The only difference: outbound WhatsApp API calls are
stubbed out for the duration of each request (via unittest.mock.patch on
whatsapp.client.send_text_message) so no real message is ever sent - this
also covers _notify_delivery_agent, so a demo order reaching CONFIRM can't
page a real delivery rider.

Conversations here are stored under a reserved phone-number namespace
("demo:<session-id>") so they never collide with or pollute real customer
data/analytics.

Note: the patch target is "main.send_text_message", not
"whatsapp.client.send_text_message" - main.py imports the function by name
(`from whatsapp.client import send_text_message`), which binds it directly
into main's module namespace, so patching the original module has no effect
on main's already-bound reference.

Remove this file, its router include in main.py, the templates/test_chat.html
file, and the "Test Chat" nav link in templates/base.html before going live -
none of it is needed for production and it's isolated here specifically to
make that removal a 4-file, no-side-effects operation.
"""
import secrets
from unittest.mock import patch

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from admin.auth import get_current_admin
from admin.templating import render
from storage import store

router = APIRouter(prefix="/admin/test-chat")

DEMO_PHONE_PREFIX = "demo:"


def _new_demo_phone() -> str:
    return f"{DEMO_PHONE_PREFIX}{secrets.token_hex(4)}"


def _wipe_demo_conversation(phone: str):
    conn = store._get_conn()
    conn.execute("DELETE FROM conversations WHERE phone = ?", (phone,))
    order_ids = [r[0] for r in conn.execute("SELECT id FROM orders WHERE phone = ?", (phone,)).fetchall()]
    for oid in order_ids:
        conn.execute("DELETE FROM order_items WHERE order_id = ?", (oid,))
    conn.execute("DELETE FROM orders WHERE phone = ?", (phone,))
    conn.execute("DELETE FROM customers WHERE phone = ?", (phone,))
    conn.commit()


@router.get("")
def test_chat_page(request: Request, phone: str = None, admin=Depends(get_current_admin)):
    if not phone or not phone.startswith(DEMO_PHONE_PREFIX):
        phone = _new_demo_phone()
        return RedirectResponse(f"/admin/test-chat?phone={phone}", status_code=303)

    transcript = store.get_conversation(phone)
    order = store.get_active_order(phone)
    order_items = store.get_order_items(order["id"]) if order else []
    return render(
        request, "test_chat.html", active_page="test_chat", admin=admin,
        phone=phone, transcript=transcript, order=order, order_items=order_items,
    )


@router.post("/send")
def test_chat_send(request: Request, phone: str = Form(...), message: str = Form(...), admin=Depends(get_current_admin)):
    import main as app_main

    if phone.startswith(DEMO_PHONE_PREFIX) and message.strip():
        with patch("main.send_text_message", return_value={"messages": [{"id": "demo"}]}):
            app_main.handle_customer_message(phone, message.strip())

    return RedirectResponse(f"/admin/test-chat?phone={phone}", status_code=303)


@router.post("/reset")
def test_chat_reset(phone: str = Form(...), admin=Depends(get_current_admin)):
    if phone.startswith(DEMO_PHONE_PREFIX):
        _wipe_demo_conversation(phone)
    new_phone = _new_demo_phone()
    return RedirectResponse(f"/admin/test-chat?phone={new_phone}", status_code=303)
