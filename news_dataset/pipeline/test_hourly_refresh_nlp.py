"""Check that the refresh tags today/yesterday before the older backlog.

Regression: get_articles_pending_nlp() is oldest-first, so a backlog larger
than one batch used to consume the whole budget and leave today untagged,
scoring today's GPR at ~0.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from news_dataset.pipeline import hourly_refresh as hr


def _run(window_pending, total_pending):
    calls = []

    def fake_run_nlp(limit, start=None):
        calls.append({"limit": limit, "start": start})
        return (min(limit, window_pending if start else total_pending - window_pending), 0)

    def fake_count(_version, start=None):
        return window_pending if start else total_pending

    with (
        mock.patch.object(hr, "run_nlp", side_effect=fake_run_nlp),
        mock.patch.object(hr.db, "count_articles_pending_nlp", side_effect=fake_count),
        mock.patch.object(hr, "backfill_missing_parquets", return_value=[]),
        mock.patch.object(hr, "run_daily_index", return_value={}),
        mock.patch.object(hr, "run_gpr_range"),
        mock.patch.object(hr, "sync_all", return_value={}),
        mock.patch.object(hr.db, "log_pipeline_run"),
        mock.patch.object(hr, "_warm_api_caches", return_value={}),
    ):
        details = hr.run_platform_refresh(skip_dual_signal=True)
    return calls, details


def test_recent_window_tagged_first_despite_large_backlog():
    calls, details = _run(window_pending=50, total_pending=5000)

    assert calls, "expected NLP to run"
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    assert calls[0]["start"] is not None, "recent window must be tagged first"
    assert calls[0]["start"].date() == yesterday
    assert calls[0]["limit"] == hr.NLP_WINDOW_MAX
    # Backlog only gets what the window pass left of the per-run batch budget.
    assert calls[1]["start"] is None
    assert calls[1]["limit"] == hr.NLP_BATCH - 50
    assert details["nlp_window_pending_before"] == 50


def test_window_alone_can_consume_whole_batch_budget():
    calls, _ = _run(window_pending=hr.NLP_BATCH + 10, total_pending=5000)

    assert len(calls) == 1, "no budget left for backlog once window exceeds batch"
    assert calls[0]["start"] is not None


def test_no_pending_runs_nothing():
    calls, _ = _run(window_pending=0, total_pending=0)

    assert calls == []


if __name__ == "__main__":
    test_recent_window_tagged_first_despite_large_backlog()
    test_window_alone_can_consume_whole_batch_budget()
    test_no_pending_runs_nothing()
    print("ok")
