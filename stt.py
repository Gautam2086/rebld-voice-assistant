import httpx

from config import settings


def transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV audio bytes to text using Deepgram REST API (nova-3)."""
    if not wav_bytes:
        return ""

    resp = httpx.post(
        "https://api.deepgram.com/v1/listen",
        params={"model": "nova-3", "smart_format": "true"},
        headers={
            "Authorization": f"Token {settings.deepgram_api_key}",
            "Content-Type": "audio/wav",
        },
        content=wav_bytes,
        timeout=30.0,
    )
    resp.raise_for_status()

    data = resp.json()
    alternatives = (
        data.get("results", {})
        .get("channels", [{}])[0]
        .get("alternatives", [{}])
    )
    if alternatives:
        return alternatives[0].get("transcript", "")
    return ""
