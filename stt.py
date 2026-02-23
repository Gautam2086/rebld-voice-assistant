import httpx

from config import settings


def transcribe(wav_bytes: bytes) -> str:
    """REST (batch) instead of WebSocket — adds ~200ms but simpler to reason about.
    Production upgrade: Deepgram WebSocket for real-time partials while user speaks."""
    if not wav_bytes:
        return ""

    # nova-3: Deepgram's latest model, best accuracy for conversational english
    # smart_format: adds punctuation and casing, makes transcripts more readable
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
