"""CLI entrypoint — cron-friendly.

    python -m orchestrator.cli run --channels n12
    python -m orchestrator.cli backfill --channels n12 --days 30
    python -m orchestrator.cli status
"""
from __future__ import annotations

import argparse
import sys

from common.config import get_settings
from common.labels import CATEGORY_HE, VERDICT_HE, Category, Verdict


def _enabled_channels(settings) -> list[str]:
    return [name for name, cfg in settings.channels.items() if cfg.enabled]


def cmd_run(args, settings) -> int:
    from orchestrator.pipeline import build_orchestrator

    channels = args.channels or _enabled_channels(settings)
    report = build_orchestrator(settings).run_once(channels, limit=args.limit)
    print(report.summary())
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if report.errors else 0


def cmd_backfill(args, settings) -> int:
    from orchestrator.pipeline import build_orchestrator

    channels = args.channels or _enabled_channels(settings)
    report = build_orchestrator(settings).backfill(channels, days=args.days, limit=args.limit)
    print(report.summary())
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if report.errors else 0


def cmd_status(args, settings) -> int:
    """Print what's in the database — a quick health check after a run."""
    from database.metrics import channel_stats
    from database.repository import get_repository

    repo = get_repository(settings.db_url)
    records = repo.get_checked_articles()
    print(f"fact-checked articles: {len(records)}")
    if not records:
        return 0

    for channel in sorted({r.channel_name for r in records}):
        stats = channel_stats(
            records,
            channel,
            weights=settings.lie_index.weights,
            half_life_days=settings.lie_index.recency_half_life_days,
        )
        counts = ", ".join(
            f"{VERDICT_HE[Verdict(v)]}={n}" for v, n in sorted(stats.verdict_counts.items())
        )
        print(f"  {channel}: lie_index={stats.lie_index} n={stats.total_checked} [{counts}]")

    by_category: dict[str, int] = {}
    for record in records:
        by_category[record.category] = by_category.get(record.category, 0) + 1
    print("  categories: " + ", ".join(
        f"{CATEGORY_HE[Category(c)]}={n}" for c, n in sorted(by_category.items())
    ))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orchestrator", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler, help_text in (
        ("run", cmd_run, "scrape and fact-check the latest articles"),
        ("backfill", cmd_backfill, "recover the past N days of coverage"),
        ("status", cmd_status, "summarise what is already in the database"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.set_defaults(handler=handler)
        if name != "status":
            sub.add_argument("--channels", nargs="+", help="channel ids (default: enabled in config)")
            sub.add_argument("--limit", type=int, help="max articles to process")
        if name == "backfill":
            sub.add_argument("--days", type=int, default=30, help="how far back to go")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args, get_settings())


if __name__ == "__main__":
    raise SystemExit(main())
