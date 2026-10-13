"""Regression: the NIFTY price CSV behind the vol forecast must keep refreshing.

NIFTY.csv was a one-off snapshot no job updated, so nifty_volatility.as_of froze
at 2026-07-16 while the GPR side stayed current. Checks the dual-signal refresh
tops it up (merging, never dropping history), the daily workflow commits it,
and the payload flags stale vol data.
"""

import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("DATABASE_URL", "postgresql://test@localhost/test")  # import-time guard; DB is mocked
sys.path.insert(0, str(ROOT))

from news_dataset.api import gpr_service, market_service  # noqa: E402
from news_dataset.pipeline import daily_index  # noqa: E402


def test_refresh_appends_new_closes_and_keeps_history():
    with tempfile.TemporaryDirectory() as tmp:
        csv = Path(tmp) / "NIFTY.csv"
        csv.write_text("Date,NIFTY\n2026-07-15,100.0\n2026-07-16,101.0\n")
        idx = pd.DatetimeIndex(["2026-07-16", "2026-10-13"]).tz_localize("Asia/Kolkata")
        fake_yf = mock.Mock()
        fake_yf.Ticker.return_value.history.return_value = pd.DataFrame({"Close": [102.0, 200.0]}, index=idx)
        with mock.patch.object(market_service, "_get_yfinance", return_value=fake_yf):
            assert market_service.refresh_nifty_csv(csv) == "2026-10-13"
        out = pd.read_csv(csv)
        assert list(out.columns) == ["Date", "NIFTY"]
        assert list(out["Date"]) == ["2026-07-15", "2026-07-16", "2026-10-13"]
        assert list(out["NIFTY"]) == [100.0, 102.0, 200.0]

        fake_yf.Ticker.return_value.history.side_effect = RuntimeError("yahoo down")
        with mock.patch.object(market_service, "_get_yfinance", return_value=fake_yf):
            assert market_service.refresh_nifty_csv(csv) == "2026-10-13"
        assert len(pd.read_csv(csv)) == 3


def test_dual_signal_refresh_tops_up_nifty_first():
    calls = []
    payload = {"geopolitical": {"as_of": "2026-10-13"}}
    with (
        mock.patch.object(market_service, "refresh_nifty_csv", side_effect=lambda: calls.append("nifty")),
        mock.patch.object(gpr_service, "build_dual_signal_payload",
                          side_effect=lambda **_: calls.append("build") or payload),
        mock.patch.object(daily_index.db, "upsert_dual_signal"),
    ):
        daily_index.refresh_dual_signal()
    assert calls == ["nifty", "build"]


def test_daily_workflow_commits_nifty_csv():
    wf = (ROOT / ".github/workflows/daily_index.yml").read_text()
    assert "nifty-50/data/NIFTY.csv" in wf


def test_vol_staleness_flag():
    fri_on_mon = {"as_of": "2026-10-09"}
    gpr_service._flag_vol_staleness(fri_on_mon, today=date(2026, 10, 12))
    assert fri_on_mon == {"as_of": "2026-10-09", "trading_days_old": 0, "stale": False}
    old = {"as_of": "2026-07-16"}
    gpr_service._flag_vol_staleness(old, today=date(2026, 10, 14))
    assert old["stale"] is True


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
