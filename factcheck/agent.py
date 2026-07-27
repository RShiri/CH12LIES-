"""The Fact-Checker Agent.

Given a category-filtered article: extract its central claim, search the web for
evidence, then have Claude return a schema-constrained verdict. The verdict is
validated (Hebrew explanation, sources traceable to real search results) before
it is trusted; a violation is fed back to the model as a retry rather than
being stored.
"""
from __future__ import annotations

from common.labels import CHANNEL_HE
from common.logging import get_logger
from common.models import Article, FactCheckResult
from factcheck.llm_provider import LLMProvider, LLMRefusal
from factcheck.prompts import (
    CLAIM_EXTRACTION_SYSTEM,
    FACT_CHECK_SYSTEM,
    HEBREW_RETRY_NOTE,
    build_factcheck_prompt,
    build_search_queries,
)
from factcheck.schemas import LLMVerdict
from factcheck.search_provider import SearchProvider, SearchResult
from factcheck.validators import VerdictRejected, validate_verdict

log = get_logger("factcheck.agent")


class FactCheckFailed(Exception):
    """The article could not be fact-checked (refusal, or retries exhausted)."""


class FactCheckerAgent:
    """Vendor-neutral: it talks to an LLMProvider and a SearchProvider only."""

    def __init__(
        self,
        search_provider: SearchProvider,
        llm: LLMProvider,
        max_search_results: int = 8,
        max_retries: int = 3,
    ):
        self.search = search_provider
        self.llm = llm
        self.max_search_results = max_search_results
        self.max_retries = max_retries

    # -- public API --------------------------------------------------------

    def check(self, article: Article) -> FactCheckResult:
        claim = self.extract_claim(article)
        results = self.gather_evidence(article, claim)
        return self.adjudicate(article, claim, results)

    # -- pipeline stages ---------------------------------------------------

    def extract_claim(self, article: Article) -> str:
        """Reduce the article to the single factual claim worth checking."""
        prompt = (
            f"<כותרת>\n{article.headline}\n</כותרת>\n\n"
            f"<גוף_הכתבה>\n{article.full_text[:8000]}\n</גוף_הכתבה>\n\n"
            "מהי הטענה העובדתית המרכזית בכתבה?"
        )
        try:
            claim = self.llm.complete_text(
                system=CLAIM_EXTRACTION_SYSTEM, prompt=prompt, max_tokens=1000
            )
        except LLMRefusal as exc:
            raise FactCheckFailed(f"claim extraction refused: {exc}") from exc
        return claim.strip() or article.headline

    def gather_evidence(self, article: Article, claim: str) -> list[SearchResult]:
        """Search once per query angle, de-duplicating by URL."""
        seen: set[str] = set()
        evidence: list[SearchResult] = []
        for query in build_search_queries(article.headline, claim, article.category):
            try:
                hits = self.search.search(query, max_results=self.max_search_results)
            except Exception as exc:
                log.warning("search failed", extra={"ctx": {"query": query, "error": str(exc)}})
                continue
            for hit in hits:
                if hit.url not in seen:
                    seen.add(hit.url)
                    evidence.append(hit)
        log.info(
            "evidence gathered",
            extra={"ctx": {"article": article.article_id, "sources": len(evidence)}},
        )
        return evidence

    def adjudicate(
        self, article: Article, claim: str, results: list[SearchResult]
    ) -> FactCheckResult:
        if not results:
            raise FactCheckFailed("no search results — cannot ground a verdict")

        allowed_urls = [r.url for r in results]
        prompt = build_factcheck_prompt(
            headline=article.headline,
            full_text=article.full_text,
            claim=claim,
            category=article.category,
            channel_he=CHANNEL_HE[article.channel],
            results=results,
        )
        # Rejection feedback is appended to the prompt rather than sent as an
        # extra turn, so the retry works the same on providers with no
        # multi-turn message list.
        attempt_prompt = prompt
        last_reason = ""

        for attempt in range(1, self.max_retries + 1):
            try:
                verdict = self.llm.complete_structured(
                    system=FACT_CHECK_SYSTEM,
                    prompt=attempt_prompt,
                    schema=LLMVerdict,
                    max_tokens=8000,
                )
            except LLMRefusal as exc:
                raise FactCheckFailed(f"fact-check refused: {exc}") from exc

            try:
                result = validate_verdict(verdict, allowed_urls)
            except VerdictRejected as exc:
                last_reason = str(exc)
                log.warning(
                    "verdict rejected",
                    extra={"ctx": {"attempt": attempt, "reason": last_reason}},
                )
                attempt_prompt = (
                    f"{prompt}\n\n{HEBREW_RETRY_NOTE.format(reason=last_reason)}"
                )
                continue

            log.info(
                "verdict accepted",
                extra={
                    "ctx": {
                        "article": article.article_id,
                        "status": result.fact_check_status.value,
                        "attempt": attempt,
                    }
                },
            )
            return result

        raise FactCheckFailed(f"no valid verdict after {self.max_retries} attempts: {last_reason}")
