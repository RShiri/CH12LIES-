"""Web search providers used to ground fact-checks in real sources.

The agent must never cite a URL it did not actually retrieve, so every result
returned here is kept and later used to validate the model's `sources` list.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from common.logging import get_logger

log = get_logger("factcheck.search")


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str

    def as_prompt_block(self) -> str:
        return f"- כותרת: {self.title}\n  כתובת: {self.url}\n  תקציר: {self.snippet}"


class SearchProvider(ABC):
    """Pluggable search backend."""

    @abstractmethod
    def search(self, query: str, max_results: int = 8) -> list[SearchResult]: ...


class TavilyProvider(SearchProvider):
    ENDPOINT = "https://api.tavily.com/search"

    def __init__(self, api_key: str, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout

    def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        response = httpx.post(
            self.ENDPOINT,
            json={
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "advanced",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", "")[:800],
            )
            for item in response.json().get("results", [])
            if item.get("url")
        ]


class SerperProvider(SearchProvider):
    ENDPOINT = "https://google.serper.dev/search"

    def __init__(self, api_key: str, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout

    def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        response = httpx.post(
            self.ENDPOINT,
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results, "gl": "il", "hl": "he"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", "")[:800],
            )
            for item in response.json().get("organic", [])[:max_results]
            if item.get("link")
        ]


class PerplexityProvider(SearchProvider):
    """Perplexity Sonar — a search-grounded model rather than a raw search API.

    The answer text is discarded; only the sources it consulted are kept, since
    the fact-checking verdict has to come from our own prompt and be traceable
    to real URLs. `search_results` carries title/url/snippet directly; older
    responses only carry a `citations` list of bare URLs, so both are handled.
    """

    ENDPOINT = "https://api.perplexity.ai/chat/completions"

    def __init__(self, api_key: str, model: str = "sonar", timeout: float = 60.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        response = httpx.post(
            self.ENDPOINT,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": query}],
                "search_recency_filter": "month",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return self.parse_response(response.json(), max_results)

    @staticmethod
    def parse_response(payload: dict, max_results: int = 8) -> list[SearchResult]:
        results = payload.get("search_results") or []
        if results:
            return [
                SearchResult(
                    title=item.get("title", ""),
                    url=item["url"],
                    snippet=(item.get("snippet") or "")[:800],
                )
                for item in results[:max_results]
                if item.get("url")
            ]

        # Fallback: bare citation URLs, with the model's answer as shared context.
        answer = ""
        choices = payload.get("choices") or []
        if choices:
            answer = (choices[0].get("message") or {}).get("content", "")
        return [
            SearchResult(title=url, url=url, snippet=answer[:800])
            for url in (payload.get("citations") or [])[:max_results]
            if url
        ]


_PROVIDERS: dict[str, type[SearchProvider]] = {
    "tavily": TavilyProvider,
    "serper": SerperProvider,
    "perplexity": PerplexityProvider,
}


def get_search_provider(name: str, api_key: str | None = None) -> SearchProvider:
    key = api_key or os.getenv("SEARCH_API_KEY", "")
    if not key:
        raise ValueError("SEARCH_API_KEY is not set — the fact-checker needs a search provider")
    if name not in _PROVIDERS:
        raise ValueError(f"unknown search provider {name!r}; known: {sorted(_PROVIDERS)}")
    return _PROVIDERS[name](key)
