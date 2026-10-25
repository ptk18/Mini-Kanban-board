"""Model access behind a one-method interface (issues #16, OpenAI added later).

Routers depend on ``get_ai_client`` and call ``generate(prompt)``; tests
override the dependency with a fake. Two providers, both talked to with the
standard library so no extra package is needed:

* ``OpenAIClient`` — Chat Completions with JSON mode; ``OPENAI_API_KEY``,
  optional ``OPENAI_MODEL`` (default ``gpt-4.1-mini``).
* ``GeminiClient`` — ``generateContent``; ``GEMINI_API_KEY``, optional
  ``GEMINI_MODEL`` (default ``gemini-2.5-flash``).

``get_ai_client`` picks OpenAI when ``OPENAI_API_KEY`` is set, else Gemini
when ``GEMINI_API_KEY`` is set; ``AI_PROVIDER=openai|gemini`` forces one.
Neither key is a 503: the rest of the API keeps working without AI.

Every action prompt asks for a small JSON object; ``parse_json_reply`` is
lenient about the ``` fences models like to add and raises ``AIError`` when
the reply is unusable, which the router turns into a 502.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol

from fastapi import HTTPException, status

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
REQUEST_TIMEOUT_SECONDS = 30
NOT_CONFIGURED = "AI is not configured: set OPENAI_API_KEY or GEMINI_API_KEY"


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


class OpenAIClient:
    def __init__(self, api_key: str, model: str = DEFAULT_OPENAI_MODEL) -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str) -> str:
        body = json.dumps(
            {
                "model": self._model,
                "messages": [
                    # JSON mode requires the word "json" somewhere in the messages.
                    {"role": "system", "content": "Reply with a single JSON object and nothing else."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            OPENAI_API_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise AIError(f"OpenAI returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AIError(f"OpenAI request failed: {exc}") from exc
        return extract_openai_text(payload)


def extract_openai_text(payload: Any) -> str:
    """The content of the first choice of a Chat Completions response."""
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIError("OpenAI response has no choices") from exc
    if not isinstance(text, str) or not text.strip():
        raise AIError("OpenAI response is empty")
    return text


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
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    provider = os.environ.get("AI_PROVIDER", "").strip().lower()
    if not provider:
        provider = "openai" if openai_key else "gemini" if gemini_key else ""
    if provider == "openai" and openai_key:
        return OpenAIClient(openai_key, os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL))
    if provider == "gemini" and gemini_key:
        return GeminiClient(gemini_key, os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=NOT_CONFIGURED)
