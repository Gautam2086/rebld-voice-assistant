from openai import OpenAI

from config import settings

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def synthesize(text: str, voice: str = "echo") -> bytes:
    """Convert text to speech using OpenAI TTS. Returns WAV bytes."""
    client = _get_client()
    resp = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="wav",
    )
    return resp.content
