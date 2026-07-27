"""Factory so the Orchestrator never imports a concrete scraper class."""
from __future__ import annotations

from common.labels import Channel
from scrapers.base import BaseNewsScraper
from scrapers.channel13_scraper import Channel13Scraper
from scrapers.channel14_scraper import Channel14Scraper
from scrapers.n12_scraper import N12Scraper

_REGISTRY: dict[Channel, type[BaseNewsScraper]] = {
    Channel.N12: N12Scraper,
    Channel.CHANNEL13: Channel13Scraper,
    Channel.CHANNEL14: Channel14Scraper,
}


class ScraperFactory:
    @staticmethod
    def get_scraper(channel: Channel | str, **kwargs) -> BaseNewsScraper:
        try:
            key = Channel(str(channel))
        except ValueError as exc:
            raise ValueError(
                f"unknown channel {channel!r}; known: {[c.value for c in _REGISTRY]}"
            ) from exc
        return _REGISTRY[key](**kwargs)

    @staticmethod
    def available() -> list[str]:
        return [c.value for c in _REGISTRY]

    @staticmethod
    def register(channel: Channel, cls: type[BaseNewsScraper]) -> None:
        """Hook for adding a channel without editing this module."""
        _REGISTRY[channel] = cls
