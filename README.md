# Fine Dine Family Restaurant — WhatsApp AI Ordering Agent

A single-tenant WhatsApp AI food-ordering assistant for Fine Dine Family
Restaurant, built by adapting the architecture proven out in the Al Madina
grocery WhatsApp agent: FastAPI + Meta webhook + OpenRouter (text, vision,
offer-drafting) + Groq Whisper voice + SQLite + a full admin dashboard, with
a real delivery-agent workflow driven over WhatsApp.

## What it does

- Customers chat naturally on WhatsApp to order food — by typing, voice
  note, or photo — grounded only in the actual menu (~335 items across ~31
  categories, seeded from the restaurant's own printed menu). The AI never
  invents a dish, price, or availability.
- Dishes with Half/Full sizes are separate menu entries; the AI asks which
  size a customer wants rather than guessing.
- Once the order settles, the AI proactively suggests one or two popular
  extras (a drink, a side, a dessert) — once, not pushed into every reply.
- Customers choose **delivery or pickup**. Pickup orders skip location and
  delivery fees entirely. For delivery, **returning customers get asked to
  confirm their last saved address** instead of re-sharing location from
  scratch.
- The customer must explicitly reply **CONFIRM** to place an order (or
  **CANCEL** to adjust it) — never placed automatically, regardless of
  whether the order started by text, voice, or image.
- **Delivery agent workflow**: once a delivery order is confirmed, an
  active registered delivery agent is notified on WhatsApp with the full
  order details. The agent drives the order through **PACKED → PICKED →
  DELIVERED** by replying with those exact words — each reply updates the
  order status live on the dashboard and can notify the customer.
- Staff manage everything through `/admin`: customers (with purchase-behavior
  analytics — favorite items, average order value, days since last order),
  conversations with full order history by month, orders (with delivery
  status and assigned agent), sales analytics, pre-built monthly/yearly
  reports, the menu (with search + an in-stock/out-of-stock switch per
  item), an AI-assisted offer creator, delivery agent management, and
  printer settings.

## Admin dashboard (`/admin`)

Create the first admin account:
```
python -m admin.create_admin <username> <password>
```
Then log in at `/admin/login`. Pages: Dashboard, Customers, Conversations,
Orders, Analytics, Reports, Menu, Offers, Delivery Agents, Billing (static
Free plan info), Settings, Printer.

## Delivery agents

Register a rider on the **Delivery Agents** page with their name and
WhatsApp number. Once registered:
1. A customer confirms a delivery order.
2. The system messages the first active agent with the order (items, total,
   customer phone, delivery address + map link).
3. The agent replies **PACKED** (kitchen has it ready) → **PICKED** (they've
   collected it) → **DELIVERED** (dropped off). Each reply must follow that
   exact order — a reply that skips a stage is rejected with a note of the
   order's current status.
4. The customer gets an automatic "on its way!" message on PICKED and a
   "delivered, enjoy your meal!" message on DELIVERED.

v1 assignment is simple: the first active agent gets every new delivery
order (fine for one or two riders). A message from a *registered agent's*
phone number is always routed to this flow, never treated as a customer
placing a food order.

## Menu / stock control

There's no live POS integration yet — the restaurant owner manages
availability directly:

- `data/catalog_seed.xlsx` has the full menu transcribed from the
  restaurant's printed menu (all categories, all pages). A few items marked
  "ASP" (as per size) were seeded with a placeholder price of 0 and a
  `(ASP - set real price)` label — **set these to a real price on the Menu
  page before going live.**
- The **Menu** page has a search box (searches name + category) and an
  in-stock / out-of-stock switch per item — flip it and the AI immediately
  stops offering that dish as available.
- Re-import the whole menu anytime via the Menu page's upload form, or:
  ```
  python -m catalog.excel_import path/to/file.xlsx
  ```
- When a real POS/live-stock feed becomes available, implement
  `catalog/pos_client.py`'s `fetch_stock()` — no other code needs to change.

## Thermal printer integration (optional, not yet configured)

The `print_agent/` module (network, Bluetooth, and USB printer support) is
included and ready to go, same as the grocery agent's — see that project's
README for full setup steps if/when this restaurant gets a printer. Nothing
needs to be configured for the WhatsApp ordering flow to work without it.

## Setup

```
pip install -r requirements.txt
cp .env.example .env   # fill in WhatsApp, OpenRouter, Whisper, ADMIN_SESSION_SECRET
python -m admin.create_admin <username> <password>
uvicorn main:app --reload
```

Expose your local server (e.g. via ngrok) and register the resulting URL as
your webhook in Meta's App Dashboard under WhatsApp > Configuration, using
`WHATSAPP_VERIFY_TOKEN` from `.env` as the verify token.

## Non-goals (v1)

- No live POS/inventory sync — the in-stock switch is manual.
- No online payment — orders are confirmed in-chat, payment is handled the
  same way the restaurant already does (cash/card on delivery or pickup).
- No real dispatch/load-balancing logic for delivery agents — v1 assigns
  every new delivery order to the first active agent.
- Printer integration is present but deliberately not configured yet.
- Date/quantity extraction from free text is a lightweight regex pass, not
  a robust NLP parser — same caveat as the grocery agent's item-quantity
  matching, more pronounced here given half/full size choices.
- Offer discounts apply to the whole order subtotal, not scoped to specific
  categories/dishes even when an offer's scope narrows to one — same
  caveat as the grocery agent.
