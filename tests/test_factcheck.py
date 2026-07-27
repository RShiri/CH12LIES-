"""Fact-checker tests with a stub Claude client and stub search provider."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from common.labels import Verdict
from common.models import Article
from factcheck.agent import FactCheckerAgent, FactCheckFailed
from factcheck.schemas import LLMVerdict
from factcheck.search_provider import SearchProvider, SearchResult, get_search_provider
from factcheck.validators import VerdictRejected, validate_verdict

HEBREW_EXPLANATION = (
    "הטענה שהוצגה בכותרת הכתבה אינה עולה בקנה אחד עם הנתונים הרשמיים שפורסמו. "
    "לפי הודעת דובר צה״ל והדיווחים המצטברים, מספר האירועים שדווח בכתבה גבוה מהמספר בפועל. "
    "לכן הדירוג שנקבע הוא שקר, בהתבסס על שני מקורות עצמאיים."
)

RESULTS = [
    SearchResult(title="הודעת דובר צה״ל", url="https://idf.il/report", snippet="נתונים רשמיים"),
    SearchResult(title="סקירה", url="https://haaretz.co.il/news/1", snippet="ניתוח הנתונים"),
]


class StubSearch(SearchProvider):
    def __init__(self, results=RESULTS, fail=False):
        self.results = results
        self.fail = fail
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("search backend down")
        return list(self.results)


class StubMessages:
    """Mimics client.messages: `.create` for claims, `.parse` for verdicts."""

    def __init__(self, claim: str, verdicts: list, stop_reason: str = "end_turn"):
        self.claim = claim
        self.verdicts = list(verdicts)
        self.stop_reason = stop_reason
        self.parse_calls: list[dict] = []

    def create(self, **kwargs):
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="text", text=self.claim)],
        )

    def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        verdict = self.verdicts.pop(0)
        return SimpleNamespace(stop_reason=self.stop_reason, parsed_output=verdict)


def make_agent(search: StubSearch, verdicts: list, claim="הטענה המרכזית", stop_reason="end_turn"):
    agent = FactCheckerAgent.__new__(FactCheckerAgent)  # bypass real Anthropic client
    agent.client = SimpleNamespace(messages=StubMessages(claim, verdicts, stop_reason))
    agent.search = search
    agent.model = "claude-opus-5"
    agent.max_search_results = 8
    agent.max_retries = 3
    agent.effort = "high"
    return agent


ARTICLE = Article(
    channel="n12",
    category="security",
    url="https://www.mako.co.il/news-military/Article-1.htm",
    headline="צה״ל תקף מטרות בדרום לבנון",
    full_text="גוף הכתבה המלא, הכולל את הטענות שיש לבדוק מול מקורות חיצוניים.",
)


def good_verdict(status="False", sources=None):
    return LLMVerdict(
        fact_check_status=status,
        explanation=HEBREW_EXPLANATION,
        sources=sources if sources is not None else ["https://idf.il/report"],
    )


# -- validator ----------------------------------------------------------------


def test_validator_accepts_hebrew_verdict_with_real_sources():
    result = validate_verdict(good_verdict(), [r.url for r in RESULTS])
    assert result.fact_check_status is Verdict.FALSE
    assert str(result.sources[0]) == "https://idf.il/report"


def test_validator_rejects_english_explanation():
    verdict = LLMVerdict(
        fact_check_status="True",
        explanation="This explanation is in English, which the system does not accept at all.",
        sources=["https://idf.il/report"],
    )
    with pytest.raises(VerdictRejected, match="עברית"):
        validate_verdict(verdict, [r.url for r in RESULTS])


def test_validator_rejects_hallucinated_source():
    verdict = good_verdict(sources=["https://invented.example/fake"])
    with pytest.raises(VerdictRejected, match="אינם מופיעים"):
        validate_verdict(verdict, [r.url for r in RESULTS])


def test_validator_rejects_empty_sources():
    with pytest.raises(VerdictRejected, match="מקורות"):
        validate_verdict(good_verdict(sources=[]), [r.url for r in RESULTS])


def test_validator_tolerates_url_formatting_differences():
    # Same page, cosmetically different URL — must not be treated as invented.
    verdict = good_verdict(sources=["https://www.idf.il/report/"])
    assert validate_verdict(verdict, [r.url for r in RESULTS]).sources


def test_validator_rejects_too_short_explanation():
    verdict = LLMVerdict(
        fact_check_status="True", explanation="נכון.", sources=["https://idf.il/report"]
    )
    with pytest.raises(VerdictRejected, match="קצר"):
        validate_verdict(verdict, [r.url for r in RESULTS])


# -- agent --------------------------------------------------------------------


def test_check_end_to_end():
    agent = make_agent(StubSearch(), [good_verdict()])
    result = agent.check(ARTICLE)
    assert result.fact_check_status is Verdict.FALSE
    assert result.explanation == HEBREW_EXPLANATION


def test_retries_then_succeeds_after_bad_verdict():
    english = LLMVerdict(
        fact_check_status="True",
        explanation="An English explanation that must be rejected by the validator here.",
        sources=["https://idf.il/report"],
    )
    agent = make_agent(StubSearch(), [english, good_verdict()])
    result = agent.check(ARTICLE)
    assert result.fact_check_status is Verdict.FALSE
    # Second attempt carries the rejection reason back to the model.
    second_call = agent.client.messages.parse_calls[1]
    assert "עברית" in second_call["messages"][-1]["content"]


def test_gives_up_after_max_retries():
    bad = LLMVerdict(
        fact_check_status="True",
        explanation="Still English and therefore still invalid for this system to store.",
        sources=["https://idf.il/report"],
    )
    agent = make_agent(StubSearch(), [bad, bad, bad])
    with pytest.raises(FactCheckFailed, match="no valid verdict"):
        agent.check(ARTICLE)


def test_refusal_is_surfaced_not_swallowed():
    agent = make_agent(StubSearch(), [good_verdict()], stop_reason="refusal")
    with pytest.raises(FactCheckFailed, match="refused"):
        agent.check(ARTICLE)


def test_no_search_results_means_no_verdict():
    agent = make_agent(StubSearch(results=[]), [good_verdict()])
    with pytest.raises(FactCheckFailed, match="no search results"):
        agent.check(ARTICLE)


def test_search_failure_does_not_crash_the_run():
    agent = make_agent(StubSearch(fail=True), [good_verdict()])
    with pytest.raises(FactCheckFailed, match="no search results"):
        agent.check(ARTICLE)


def test_evidence_is_deduplicated_across_queries():
    search = StubSearch()
    agent = make_agent(search, [good_verdict()])
    evidence = agent.gather_evidence(ARTICLE, "הטענה")
    assert len(search.queries) == 3  # three query angles
    assert len(evidence) == 2  # deduplicated to the two unique URLs


def test_claim_falls_back_to_headline_when_model_returns_nothing():
    agent = make_agent(StubSearch(), [good_verdict()], claim="   ")
    assert agent.extract_claim(ARTICLE) == ARTICLE.headline


# -- provider factory ---------------------------------------------------------


def test_provider_factory_requires_key(monkeypatch):
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)
    with pytest.raises(ValueError, match="SEARCH_API_KEY"):
        get_search_provider("tavily", api_key="")


def test_provider_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="unknown search provider"):
        get_search_provider("bing", api_key="k")
