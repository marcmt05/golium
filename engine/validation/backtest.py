from __future__ import annotations

from .metrics import build_metrics_report


def backtest_snapshot(picks: list[dict]) -> dict:
    """Aggregate metrics for one snapshot or a merged ledger."""
    return build_metrics_report(picks)
