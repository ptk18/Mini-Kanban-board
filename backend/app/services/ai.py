"""Gemini access behind a one-method interface (issue #16).

Routers depend on ``get_ai_client`` and call ``generate(prompt)``; tests
override the dependency with a fake. ``GeminiClient`` talks to the
``generateContent`` REST endpoint with the standard library so no extra
package is needed (``httpx`` is only a dev dependency here).

Every action prompt asks for a small JSON object; ``parse_json_reply`` is
lenient about the ``` fences models like to add and raises ``AIError`` when
the reply is unusable, which the router turns into a 502. A missing
``GEMINI_API_KEY`` is a 503: the rest of the API keeps working without AI.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol

from fastapi import HTTPException, status

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"
REQUEST_TIMEOUT_SECONDS = 30


class AIError(RuntimeError):
    """The provider could not be reached or returned something unusable."""


class AIClient(Protocol):
    def generate(self, prompt: str) -> str:
        """Return the model's text reply for ``prompt``; raise ``AIError``."""


class GeminiClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str) -> str:
        body = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            GEMINI_API_URL.format(model=self._model),
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key},
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise AIError(f"Gemini returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AIError(f"Gemini request failed: {exc}") from exc
        return extract_text(payload)


def extract_text(payload: Any) -> str:
    """The concatenated text parts of the first candidate of a
    ``generateContent`` response."""
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise AIError("Gemini response has no candidates") from exc
    if not text.strip():
        raise AIError("Gemini response is empty")
    return text


def parse_json_reply(reply: str) -> dict[str, Any]:
    text = reply.strip()
    if text.startswith("```"):
        # ```json\n{...}\n``` -> {...}
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIError("AI reply is not valid JSON") from exc
    if not isinstance(data, dict):
        raise AIError("AI reply is not a JSON object")
    return data


def get_ai_client() -> AIClient:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI is not configured: set GEMINI_API_KEY",
        )
    return GeminiClient(api_key, os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))
