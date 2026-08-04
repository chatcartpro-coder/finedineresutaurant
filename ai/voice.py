"""
Thin client for transcribing WhatsApp voice notes via a hosted Whisper
endpoint. Defaults to Groq's OpenAI-compatible whisper-large-v3 (fast, cheap,
generous free tier, strong multilingual/Arabic+English accuracy) - swap to
OpenAI's whisper-1 by changing WHISPER_BASE_URL/WHISPER_API_KEY/WHISPER_MODEL
in .env, no code change needed since both expose the same
multipart /audio/transcriptions endpoint shape.
"""
import mimetypes

import requests

from config import config


class TranscriptionError(Exception):
    pass


def transcribe(audio_bytes: bytes, mime_type: str) -> str:
    if not config.WHISPER_API_KEY:
        raise TranscriptionError("WHISPER_API_KEY is not set in .env")

    ext = mimetypes.guess_extension(mime_type) or ".ogg"
    filename = f"voice-note{ext}"

    resp = requests.post(
        f"{config.WHISPER_BASE_URL}/audio/transcriptions",
        headers={"Authorization": f"Bearer {config.WHISPER_API_KEY}"},
        files={"file": (filename, audio_bytes, mime_type)},
        data={"model": config.WHISPER_MODEL},
        timeout=30,
    )

    if resp.status_code != 200:
        raise TranscriptionError(f"Transcription error {resp.status_code}: {resp.text}")

    try:
        data = resp.json()
    except ValueError as e:
        raise TranscriptionError(f"Transcription API returned non-JSON response: {resp.text[:500]}") from e

    text = data.get("text")
    if text is None:
        raise TranscriptionError(f"Unexpected transcription response: {data}")
    return text
