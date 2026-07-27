"""Loads config.yaml + .env into a typed settings object."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ChannelConfig(BaseModel):
    enabled: bool
    display_name: str
    base_url: str


class ScrapingConfig(BaseModel):
    backfill_days: int = 30
    max_articles_per_run: int = 50
    screenshot_dir: str = "data/screenshots"
    request_delay_seconds: float = 2


class FactCheckConfig(BaseModel):
    provider: str = "gemini"
    model: str
    rate_limit_per_minute: int | None = None
    effort: str = "high"
    max_search_results: int = 8
    max_retries: int = 3


class LieIndexConfig(BaseModel):
    weights: dict[str, float]
    recency_half_life_days: float = 14


class Settings(BaseModel):
    channels: dict[str, ChannelConfig]
    allowed_categories: dict[str, str]
    scraping: ScrapingConfig
    factcheck: FactCheckConfig
    lie_index: LieIndexConfig

    # from environment
    db_url: str = "sqlite:///data/db.sqlite3"
    search_provider: str = "perplexity"
    search_api_key: str = ""
    # The LLM key is deliberately absent: each provider resolves its own env
    # var (GEMINI_API_KEY, ANTHROPIC_API_KEY) in `get_llm_provider`, so adding
    # a backend never means touching this class.


@lru_cache
def get_settings(config_path: Path | None = None) -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    path = config_path or PROJECT_ROOT / "config.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Settings(
        **raw,
        db_url=os.getenv("DB_URL", "sqlite:///data/db.sqlite3"),
        search_provider=os.getenv("SEARCH_PROVIDER", "perplexity"),
        search_api_key=os.getenv("SEARCH_API_KEY", ""),
    )
