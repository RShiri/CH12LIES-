"""Pluggable LLM backends for the fact-checker.

Mirrors the `SearchProvider` pattern: an ABC plus a name-keyed factory, so the
agent depends on a contract rather than on any one vendor's SDK. Two calls are
all the agent needs — free text for claim extraction, and schema-constrained
JSON for the verdict.

Safety refusals differ per vendor (Anthropic sets `stop_reason`, Gemini sets a
`finish_reason` or blocks the prompt outright); both are normalised to
`LLMRefusal` so the agent handles them identically.
"""
from __future__ import annotations

import os
import threading
import time
from abc import ABC, abstractmethod

from pydantic import BaseModel

from common.logging import get_logger

log = get_logger("factcheck.llm")

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5",
    # Google AI Studio's free tier: 10 requests/minute, 250/day.
    "gemini": "gemini-2.5-flash",
}

#: Requests per minute to self-impose, per provider. Gemini's free tier rejects
#: anything above 10 RPM, and the pipeline makes two calls per article, so
#: without this a backfill dies partway through with 429s.
DEFAULT_RATE_LIMITS = {"anthropic": 0, "gemini": 10}


class LLMRefusal(Exception):
    """The model declined to answer (safety classifier, recitation block…)."""


class LLMProvider(ABC):
    """What the fact-checker needs from a language model."""

    @abstractmethod
    def complete_text(self, *, system: str, prompt: str, max_tokens: int = 1000) -> str:
        """Free-form completion. Returns the text, possibly empty."""

    @abstractmethod
    def complete_structured(
        self, *, system: str, prompt: str, schema: type[BaseModel], max_tokens: int = 8000
    ) -> BaseModel:
        """Completion constrained to `schema`. Returns a validated instance."""


class _RateGate:
    """Spaces calls out to at most `per_minute`, blocking when they arrive faster.

    Thread-safe so a future parallel orchestrator can't defeat it.
    """

    def __init__(self, per_minute: int):
        self.min_interval = 60.0 / per_minute if per_minute else 0.0
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        if not self.min_interval:
            return
        with self._lock:
            elapsed = time.monotonic() - self._last
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last = time.monotonic()


class AnthropicProvider(LLMProvider):
    """Claude. Kept selectable so switching to Gemini isn't a one-way door."""

    def __init__(self, api_key: str, model: str, effort: str = "high", rate_limit: int = 0):
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.gate = _RateGate(rate_limit)

    def complete_text(self, *, system: str, prompt: str, max_tokens: int = 1000) -> str:
        self.gate.wait()
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            raise LLMRefusal("Claude declined the request")
        return "".join(b.text for b in response.content if b.type == "text").strip()

    def complete_structured(
        self, *, system: str, prompt: str, schema: type[BaseModel], max_tokens: int = 8000
    ) -> BaseModel:
        self.gate.wait()
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            output_config={"effort": self.effort},
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        if response.stop_reason == "refusal":
            raise LLMRefusal("Claude declined the request")
        return response.parsed_output


class GeminiProvider(LLMProvider):
    """Google Gemini via AI Studio — the free-tier option.

    Structured output uses `response_schema`, which accepts the same Pydantic
    class the Anthropic path uses, so `LLMVerdict` is defined once.
    """

    #: finish reasons that mean "declined", not "failed".
    _REFUSAL_REASONS = {
        "SAFETY",
        "RECITATION",
        "PROHIBITED_CONTENT",
        "BLOCKLIST",
        "IMAGE_SAFETY",
        "IMAGE_PROHIBITED_CONTENT",
    }

    def __init__(self, api_key: str, model: str, rate_limit: int = 10, max_attempts: int = 5):
        from google import genai

        self.genai = genai
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.gate = _RateGate(rate_limit)
        self.max_attempts = max_attempts

    # -- internals ---------------------------------------------------------

    def _config(self, system: str, max_tokens: int, schema: type[BaseModel] | None):
        from google.genai import types

        kwargs = {"system_instruction": system, "max_output_tokens": max_tokens}
        if schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_schema"] = schema
        return types.GenerateContentConfig(**kwargs)

    def _generate(self, prompt: str, config):
        """Call Gemini, retrying on rate limits and transient server errors."""
        from google.genai import errors

        delay = 2.0
        for attempt in range(1, self.max_attempts + 1):
            self.gate.wait()
            try:
                return self.client.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
            except errors.APIError as exc:
                retryable = getattr(exc, "code", None) in (429, 500, 502, 503, 504)
                if not retryable or attempt == self.max_attempts:
                    raise
                log.warning(
                    "gemini retry",
                    extra={"ctx": {"attempt": attempt, "code": exc.code, "sleep": delay}},
                )
                time.sleep(delay)
                delay = min(delay * 2, 60.0)
        raise RuntimeError("unreachable")

    def _guard_refusal(self, response) -> None:
        feedback = getattr(response, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            raise LLMRefusal(f"Gemini blocked the prompt: {feedback.block_reason}")
        for candidate in getattr(response, "candidates", None) or []:
            reason = getattr(candidate, "finish_reason", None)
            name = getattr(reason, "name", None) or str(reason or "")
            if name in self._REFUSAL_REASONS:
                raise LLMRefusal(f"Gemini declined the request: {name}")

    # -- contract ----------------------------------------------------------

    def complete_text(self, *, system: str, prompt: str, max_tokens: int = 1000) -> str:
        response = self._generate(prompt, self._config(system, max_tokens, None))
        self._guard_refusal(response)
        return (response.text or "").strip()

    def complete_structured(
        self, *, system: str, prompt: str, schema: type[BaseModel], max_tokens: int = 8000
    ) -> BaseModel:
        response = self._generate(prompt, self._config(system, max_tokens, schema))
        self._guard_refusal(response)
        parsed = response.parsed
        if parsed is None:
            # Schema-constrained output should always parse; when it doesn't the
            # caller's retry loop gets a usable reason rather than a None.
            raise ValueError(f"Gemini returned unparseable output: {(response.text or '')[:200]}")
        return parsed


_REGISTRY: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}

_ENV_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}


def get_llm_provider(
    name: str,
    api_key: str | None = None,
    model: str | None = None,
    rate_limit: int | None = None,
    **kwargs,
) -> LLMProvider:
    """Build a provider by name, falling back to its conventional env var."""
    if name not in _REGISTRY:
        raise ValueError(f"unknown LLM provider {name!r}; known: {sorted(_REGISTRY)}")

    key = api_key or os.getenv(_ENV_KEYS[name], "")
    if not key:
        raise ValueError(
            f"no API key for {name}: set {_ENV_KEYS[name]} in .env or pass api_key"
        )

    limit = DEFAULT_RATE_LIMITS[name] if rate_limit is None else rate_limit
    return _REGISTRY[name](
        api_key=key, model=model or DEFAULT_MODELS[name], rate_limit=limit, **kwargs
    )
