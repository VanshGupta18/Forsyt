"""Tests for split-era normalization (GKG warmup + India product era)."""

from __future__ import annotations

import unittest

import pandas as pd

from gpr_index.scripts.corridor_index import normalize_corridor_index
from gpr_index.scripts.gkg_gpr_pipeline import normalize_index
from gpr_index.scripts.split_era import should_split_era


class SplitEraNormalizationTests(unittest.TestCase):
    def test_should_split_when_both_eras_present(self) -> None:
        daily = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-01-01", "2026-08-09"]),
                "raw_ratio": [0.01, 0.001],
                "acts_ratio": [0.005, 0.0005],
                "threats_ratio": [0.005, 0.0005],
            }
        )
        self.assertTrue(should_split_era(daily, "2026-01-01"))

    def test_india_era_not_compressed_by_gkg_baseline(self) -> None:
        """India-era ratios stay near 100 when normalized on India-only baseline."""
        dates = pd.to_datetime(
            ["2026-01-01", "2026-01-02", "2026-08-09", "2026-08-10"]
        )
        daily = pd.DataFrame(
            {
                "date": dates,
                "raw_ratio": [0.010, 0.010, 0.001, 0.001],
                "acts_ratio": [0.005, 0.005, 0.0005, 0.0005],
                "threats_ratio": [0.005, 0.005, 0.0005, 0.0005],
            }
        )
        result = normalize_index(daily, "2026-01-01", "2026-08-10")
        india = result[result["date"] >= pd.Timestamp("2026-08-09")]
        self.assertGreaterEqual(float(india["gpr_index"].mean()), 50.0)
        self.assertTrue(pd.notna(india["gpr_7ma"]).all())

    def test_corridor_india_era_not_compressed_by_gkg_baseline(self) -> None:
        """Corridor threat_index stays near 100 on India-only baseline."""
        dates = pd.to_datetime(
            ["2026-01-01", "2026-01-02", "2026-08-09", "2026-08-10"]
        )
        rows = pd.DataFrame(
            {
                "date": dates,
                "corridor": ["strait_of_hormuz"] * 4,
                "gpr_sum": [10.0, 10.0, 1.0, 1.0],
                "corridor_hit_count": [1, 1, 1, 1],
                "total_articles": [1000, 1000, 100, 100],
                "positive_articles": [50, 50, 5, 5],
                "matched_positive_articles": [1, 1, 1, 1],
                "raw_ratio": [0.010, 0.010, 0.001, 0.001],
            }
        )
        result = normalize_corridor_index(rows, "2026-01-01", "2026-08-10")
        india = result[result["date"] >= pd.Timestamp("2026-08-09")]
        self.assertEqual(india["score_status"].iloc[-1], "ok")
        self.assertGreaterEqual(float(india["threat_index"].mean()), 50.0)
        self.assertTrue(pd.notna(india["corridor_risk_7ma"]).all())


if __name__ == "__main__":
    unittest.main()
