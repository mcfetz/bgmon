"""AI-powered KE (Kohlenhydrateinheiten) estimation from meal descriptions.

Calls an OpenAI-compatible chat-completions endpoint with a German
nutritionist system prompt and parses the JSON response into a typed
``KeEstimate`` value.  Raises ``KeEstimationError`` for any failure that
the caller should surface as 503 (LLM unavailable, malformed response,
missing config).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final

from bgmon_api.config import Config

logger = logging.getLogger("bgmon.ke_estimator")

_REQUEST_TIMEOUT_S: Final = 15
_TEMPERATURE: Final = 0.1
_MAX_DESCRIPTION_LEN: Final = 2000

_SYSTEM_PROMPT: Final = (
    "Du bist ein Ernährungsberater für Diabetiker. Analysiere die "
    "Mahlzeitenbeschreibung und schätze die Kohlenhydrateinheiten (KE). "
    "1 KE = 10g Kohlenhydrate. Antworte NUR mit einem JSON-Objekt: "
    '{"ke_value": <float>, "reasoning": "<kurze Begründung auf Deutsch>"}. '
    "Sei konservativ — lieber etwas zu hoch schätzen als zu niedrig."
)


class KeEstimationError(RuntimeError):
    """Raised when the LLM cannot produce a usable KE estimate."""


@dataclass(frozen=True, slots=True)
class KeEstimate:
    """Structured result of an LLM-based KE estimation."""

    ke_value: float
    reasoning: str


def estimate_ke_from_description(description: str) -> dict[str, float | str]:
    """Estimate KE for a free-text meal description.

    Returns a dict ``{"ke_value": float, "reasoning": str}`` ready for
    ``jsonify``.  Raises ``KeEstimationError`` for any failure (missing
    config, transport error, malformed response, out-of-range value).
    """
    estimate = _call_llm(description)
    return {"ke_value": estimate.ke_value, "reasoning": estimate.reasoning}


def _call_llm(description: str) -> KeEstimate:
    """Issue the chat-completions request and parse the typed result."""
    base_url = Config.LLM_BASE_URL.rstrip("/")
    if not base_url or not Config.LLM_MODEL or not Config.LLM_API_KEY:
        raise KeEstimationError("llm_not_configured")

    payload = json.dumps({
        "model": Config.LLM_MODEL,
        "temperature": _TEMPERATURE,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _truncate(description)},
        ],
    }).encode("utf-8")

    request = urllib.request.Request(  # noqa: S310 — base_url is operator-controlled
        url=f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.LLM_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_S) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        logger.warning("LLM request failed: %s", exc)
        raise KeEstimationError(f"llm_unavailable: {exc}") from exc

    return _parse_response(raw)


def _truncate(description: str) -> str:
    """Cap the user message so an unbounded input cannot blow the context."""
    cleaned = description.strip()
    if len(cleaned) <= _MAX_DESCRIPTION_LEN:
        return cleaned
    return cleaned[:_MAX_DESCRIPTION_LEN]


def _parse_response(raw: str) -> KeEstimate:
    """Decode the chat-completions payload and extract ``KeEstimate``."""
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise KeEstimationError(f"invalid_json: {exc}") from exc

    content = _extract_message_content(outer)
    if content is None:
        raise KeEstimationError("missing_message_content")

    inner = _coerce_json(content)
    if not isinstance(inner, dict):
        raise KeEstimationError("response_not_object")

    raw_value = inner.get("ke_value")
    raw_reasoning = inner.get("reasoning")

    if not isinstance(raw_value, (int, float)) or isinstance(raw_value, bool):
        raise KeEstimationError("ke_value_not_numeric")

    ke_value = float(raw_value)
    if ke_value < 0 or ke_value > 50:
        raise KeEstimationError(f"ke_value_out_of_range: {ke_value}")

    if not isinstance(raw_reasoning, str) or not raw_reasoning.strip():
        reasoning = "Keine Begründung vom Modell erhalten."
    else:
        reasoning = raw_reasoning.strip()

    return KeEstimate(ke_value=ke_value, reasoning=reasoning)


def _extract_message_content(outer: object) -> str | None:
    """Pull the assistant message text out of the OpenAI-shaped response.

    Tolerates ``choices[0].message.content`` as either a ``str`` or a list
    of content-part dicts (multimodal responses).  Returns ``None`` when
    the structure is missing or empty.
    """
    if not isinstance(outer, dict):
        return None
    choices = outer.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content if content else None
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                parts.append(text)
        joined = "".join(parts).strip()
        return joined or None
    return None


def _coerce_json(content: str) -> object:
    """Parse JSON, tolerating models that wrap it in ```json fences."""
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = _strip_code_fence(stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        # Last resort: grab the first {...} block.
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


def _strip_code_fence(text: str) -> str:
    """Remove a leading ```json / trailing ``` markdown fence."""
    lines = text.splitlines()
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
