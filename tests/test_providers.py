"""Provider-layer tests: the LLM abstraction and the Perplexity search backend.

No network and no API keys — the vendor SDKs are exercised through recorded
response shapes and fake clients.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from factcheck.llm_provider import (
    DEFAULT_MODELS,
    DEFAULT_RATE_LIMITS,
    AnthropicProvider,
    GeminiProvider,
    LLMProvider,
    LLMRefusal,
    _RateGate,
    get_llm_provider,
)
from factcheck.schemas import LLMVerdict
from factcheck.search_provider import (
    PerplexityProvider,
    SearchProvider,
    get_search_provider,
)

# -- the contract -------------------------------------------------------------


@pytest.mark.parametrize("cls", [AnthropicProvider, GeminiProvider])
def test_providers_implement_the_contract(cls):
    assert issubclass(cls, LLMProvider)
    # Abstract methods must be overridden, not inherited.
    for method in ("complete_text", "complete_structured"):
        assert getattr(cls, method) is not getattr(LLMProvider, method)


def test_every_registered_provider_has_a_default_model_and_rate_limit():
    for name in ("anthropic", "gemini"):
        assert name in DEFAULT_MODELS
        assert name in DEFAULT_RATE_LIMITS


def test_gemini_default_is_the_free_tier_model():
    assert DEFAULT_MODELS["gemini"] == "gemini-2.5-flash"
    # Free tier allows 10 requests/minute; exceeding it returns 429s.
    assert DEFAULT_RATE_LIMITS["gemini"] == 10


# -- factory ------------------------------------------------------------------


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="unknown LLM provider"):
        get_llm_provider("gpt", api_key="k")


def test_factory_reports_the_missing_env_var_by_name(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        get_llm_provider("gemini")


def test_factory_reads_the_provider_specific_env_var(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    provider = get_llm_provider("gemini")
    assert isinstance(provider, GeminiProvider)
    assert provider.model == DEFAULT_MODELS["gemini"]


# -- rate gate ----------------------------------------------------------------


def test_rate_gate_spaces_calls_out():
    gate = _RateGate(per_minute=600)  # 0.1s apart
    import time

    start = time.monotonic()
    for _ in range(3):
        gate.wait()
    assert time.monotonic() - start >= 0.2  # first is free, next two wait


def test_rate_gate_disabled_does_not_block():
    gate = _RateGate(per_minute=0)
    import time

    start = time.monotonic()
    for _ in range(50):
        gate.wait()
    assert time.monotonic() - start < 0.1


# -- Gemini refusal mapping ---------------------------------------------------


def _gemini(monkeypatch, response):
    """A GeminiProvider whose SDK call returns `response`, without a real client."""
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = "gemini-2.5-flash"
    provider.gate = _RateGate(0)
    provider.max_attempts = 1
    provider._generate = lambda prompt, config: response
    return provider


def test_gemini_blocked_prompt_raises_refusal(monkeypatch):
    response = SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason="SAFETY"), candidates=[], text=""
    )
    with pytest.raises(LLMRefusal, match="blocked"):
        _gemini(monkeypatch, response).complete_text(system="s", prompt="p")


@pytest.mark.parametrize("reason", ["SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST"])
def test_gemini_refusal_finish_reasons(monkeypatch, reason):
    response = SimpleNamespace(
        prompt_feedback=None,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=reason))],
        text="",
    )
    with pytest.raises(LLMRefusal, match=reason):
        _gemini(monkeypatch, response).complete_text(system="s", prompt="p")


def test_gemini_normal_finish_is_not_a_refusal(monkeypatch):
    response = SimpleNamespace(
        prompt_feedback=None,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))],
        text="  הטענה המרכזית  ",
    )
    assert _gemini(monkeypatch, response).complete_text(system="s", prompt="p") == "הטענה המרכזית"


def test_gemini_unparseable_structured_output_is_an_error_not_a_none(monkeypatch):
    response = SimpleNamespace(
        prompt_feedback=None,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))],
        parsed=None,
        text="not json",
    )
    with pytest.raises(ValueError, match="unparseable"):
        _gemini(monkeypatch, response).complete_structured(
            system="s", prompt="p", schema=LLMVerdict
        )


def test_gemini_returns_the_parsed_schema_instance(monkeypatch):
    verdict = LLMVerdict(
        fact_check_status="False",
        explanation="ההסבר המלא נכתב בעברית ומפרט את ממצאי הבדיקה מול המקורות שנמצאו.",
        sources=["https://example.com/a"],
    )
    response = SimpleNamespace(
        prompt_feedback=None,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))],
        parsed=verdict,
        text="",
    )
    result = _gemini(monkeypatch, response).complete_structured(
        system="s", prompt="p", schema=LLMVerdict
    )
    assert result is verdict


# -- Gemini retry on rate limits ---------------------------------------------


def test_gemini_retries_on_429_then_succeeds(monkeypatch):
    from google.genai import errors

    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = "gemini-2.5-flash"
    provider.gate = _RateGate(0)
    provider.max_attempts = 3
    monkeypatch.setattr("time.sleep", lambda _s: None)

    calls = {"n": 0}
    ok = SimpleNamespace(prompt_feedback=None, candidates=[], text="ok")

    def flaky(model, contents, config):
        calls["n"] += 1
        if calls["n"] < 3:
            raise errors.ClientError(429, {"error": {"message": "quota"}})
        return ok

    provider.client = SimpleNamespace(models=SimpleNamespace(generate_content=flaky))
    assert provider.complete_text(system="s", prompt="p") == "ok"
    assert calls["n"] == 3


def test_gemini_does_not_retry_a_bad_request(monkeypatch):
    from google.genai import errors

    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = "gemini-2.5-flash"
    provider.gate = _RateGate(0)
    provider.max_attempts = 3
    calls = {"n": 0}

    def bad(model, contents, config):
        calls["n"] += 1
        raise errors.ClientError(400, {"error": {"message": "bad model"}})

    provider.client = SimpleNamespace(models=SimpleNamespace(generate_content=bad))
    with pytest.raises(errors.ClientError):
        provider.complete_text(system="s", prompt="p")
    assert calls["n"] == 1  # a 400 will not fix itself


# -- Perplexity ---------------------------------------------------------------


def test_perplexity_is_registered_as_a_search_provider(monkeypatch):
    monkeypatch.setenv("SEARCH_API_KEY", "k")
    assert isinstance(get_search_provider("perplexity"), PerplexityProvider)
    assert issubclass(PerplexityProvider, SearchProvider)


def test_perplexity_parses_search_results_shape():
    payload = {
        "search_results": [
            {"title": "דוח רשמי", "url": "https://gov.il/a", "snippet": "נתונים", "date": "2026"},
            {"title": "ניתוח", "url": "https://news.example/b", "snippet": "רקע"},
        ],
        "citations": ["https://ignored.example/c"],
    }
    results = PerplexityProvider.parse_response(payload)
    assert [r.url for r in results] == ["https://gov.il/a", "https://news.example/b"]
    assert results[0].title == "דוח רשמי"
    assert results[0].snippet == "נתונים"


def test_perplexity_falls_back_to_citations_when_no_search_results():
    payload = {
        "citations": ["https://gov.il/a", "https://news.example/b"],
        "choices": [{"message": {"content": "סיכום התשובה"}}],
    }
    results = PerplexityProvider.parse_response(payload)
    assert [r.url for r in results] == ["https://gov.il/a", "https://news.example/b"]
    # With no per-source snippet, the answer text is the shared context.
    assert all(r.snippet == "סיכום התשובה" for r in results)


def test_perplexity_respects_max_results():
    payload = {"search_results": [{"url": f"https://e.com/{i}"} for i in range(20)]}
    assert len(PerplexityProvider.parse_response(payload, max_results=5)) == 5


def test_perplexity_skips_entries_without_a_url():
    payload = {"search_results": [{"title": "no url"}, {"url": "https://e.com/ok"}]}
    results = PerplexityProvider.parse_response(payload)
    assert [r.url for r in results] == ["https://e.com/ok"]


def test_perplexity_empty_response_is_empty_not_an_error():
    assert PerplexityProvider.parse_response({}) == []
