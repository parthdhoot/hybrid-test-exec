from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import GEMINI_API_KEY, GEMINI_MODEL

T = TypeVar("T", bound=BaseModel)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add a free "
            "key from https://aistudio.google.com/apikey"
        )
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def generate_structured(prompt: str, response_schema: type[T]) -> T:
    """Call Gemini and force the response into the given pydantic schema.

    Using response_schema (controlled generation) instead of asking the model
    to "please return JSON" avoids the usual parsing flakiness of free-form
    LLM output for something this loop depends on structurally.
    """
    client = _get_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.2,
        ),
    )
    parsed = response.parsed
    if parsed is None:
        raise RuntimeError(f"Gemini returned no parseable structured output: {response.text!r}")
    return parsed
