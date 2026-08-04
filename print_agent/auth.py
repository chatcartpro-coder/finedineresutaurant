"""
Auth for the print-agent API surface (/print-agent/*) - a shared-secret
header token, deliberately separate from admin/auth.py's cookie-based admin
session scheme. The store's local print agent is a headless script, not a
logged-in admin browser session, so it gets its own minimal auth instead of
reusing (or working around) the cookie/redirect-oriented admin flow.
"""
from fastapi import HTTPException, Request

from config import config


def require_print_agent_token(request: Request):
    if not config.PRINT_AGENT_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="PRINT_AGENT_TOKEN is not configured on the server - set it in .env to enable printing.",
        )
    if request.headers.get("X-Print-Agent-Token") != config.PRINT_AGENT_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing print agent token")
