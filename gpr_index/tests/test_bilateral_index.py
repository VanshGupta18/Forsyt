"""Bilateral (India-relative) GPR + country-card banding — logic checks.

Run: pytest gpr_index/tests/test_bilateral_index.py
(from repo root, so `news_dataset` and `scripts` both import).
"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for p in (str(REPO), str(REPO / "gpr_index")):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts import bilateral_index as bi  # noqa: E402


def test_self_check():
    """The module's own synthetic invariants (India excluded, conflict > calm, etc.)."""
    bi._self_check()


def test_no_india_comention_yields_empty():
    df = pd.DataFrame([{
        "SQLDATE": "2026-08-10", "gpr_score": 0.9, "event_category": "sanctions",
        "V2Locations": "1#Russia#RS#RS#60#100#0;1#US#US#US#38#-97#0",
    }])
    df["date"] = pd.to_datetime(df["SQLDATE"]).dt.normalize()
    assert bi.build(df).empty


def test_country_banding():
    from news_dataset.api.country import _band
    assert _band(50) == "Low"
    assert _band(100) == "Normal"
    assert _band(150) == "Elevated"
    assert _band(500) == "High"


if __name__ == "__main__":  # runnable without pytest installed
    test_self_check()
    test_no_india_comention_yields_empty()
    test_country_banding()
    print("test_bilateral_index: ALL PASS")
