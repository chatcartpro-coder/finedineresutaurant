"""Shared Jinja2 environment for the admin dashboard."""
import os

from fastapi.templating import Jinja2Templates

from config import config

templates = Jinja2Templates(directory=os.path.join(config.BASE_DIR, "templates"))


def render(request, template_name: str, **context):
    context.setdefault("store_name", config.STORE_NAME)
    context.setdefault("currency", config.CURRENCY)
    context.setdefault("config", config)
    return templates.TemplateResponse(request, template_name, context)
