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


def get_search_provider(name: str, api_key: str | None = None) -> SearchProvider:
    key = api_key or os.getenv("SEARCH_API_KEY", "")
    if not key:
        raise ValueError("SEARCH_API_KEY is not set — the fact-checker needs a search provider")
    providers = {"tavily": TavilyProvider, "serper": SerperProvider}
    if name not in providers:
        raise ValueError(f"unknown search provider {name!r}; known: {sorted(providers)}")
    return providers[name](key)
