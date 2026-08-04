"""
Loads all configuration from environment variables (.env).
No secrets live in code - this file only reads them.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # WhatsApp
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v20.0")

    # OpenRouter
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free")
    # Used only for image messages - must be a vision/multimodal-capable model.
    # Defaults to the same model; override if OPENROUTER_MODEL doesn't support images.
    OPENROUTER_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL") or OPENROUTER_MODEL
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    # Voice transcription (Groq's Whisper endpoint by default - fast, free-tier
    # friendly, OpenAI-compatible. Swap to OpenAI's whisper-1 by changing
    # WHISPER_BASE_URL/WHISPER_API_KEY/WHISPER_MODEL - ai/voice.py doesn't
    # care which provider, it's a plain REST call either way.
    WHISPER_API_KEY = os.getenv("WHISPER_API_KEY", "")
    WHISPER_BASE_URL = os.getenv("WHISPER_BASE_URL", "https://api.groq.com/openai/v1")
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3")

    # Admin session auth
    ADMIN_SESSION_SECRET = os.getenv("ADMIN_SESSION_SECRET", "")
    ADMIN_SESSION_COOKIE = "finedine_admin_session"
    ADMIN_SESSION_MAX_AGE = 60 * 60 * 12  # 12 hours

    # Print agent auth - a shared secret the restaurant's local print-agent
    # script sends as a header on every request; separate from admin session
    # cookies since a print client isn't a logged-in admin browser session.
    # Printer integration is deferred for this restaurant (per scope), but the
    # module is present and ready the moment they get a printer.
    PRINT_AGENT_TOKEN = os.getenv("PRINT_AGENT_TOKEN", "")

    # Restaurant info
    STORE_NAME = os.getenv("STORE_NAME", "Fine Dine Family Restaurant")
    STORE_PHONE = os.getenv("STORE_PHONE", "")
    STORE_LAT = os.getenv("STORE_LAT", "")
    STORE_LNG = os.getenv("STORE_LNG", "")

    # Delivery pricing
    DELIVERY_FEE = float(os.getenv("DELIVERY_FEE", "10"))
    FREE_DELIVERY_THRESHOLD = float(os.getenv("FREE_DELIVERY_THRESHOLD", "100"))
    CURRENCY = os.getenv("CURRENCY", "AED")

    PORT = int(os.getenv("PORT", "8000"))

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    DB_PATH = os.path.join(DATA_DIR, "app.db")
    CATALOG_SEED_PATH = os.path.join(DATA_DIR, "catalog_seed.xlsx")


config = Config()
