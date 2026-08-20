"""Forward-day pipeline semantics: product batches and incremental updates."""

from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from gpr_index.scripts.corridor_index import (
    _merge_corridor_totals,
    _merge_prior_corridor_hits,
    normalize_corridor_index,
)
from gpr_index.scripts.gkg_gpr_pipeline import _ensure_ratio_fields, normalize_index
from gpr_index.scripts.paths import (
    GPR_WARMUP_START,
    INDIA_GPR_INDEX_START,
    gpr_score_start,
)
from gpr_index.scripts.split_era import should_split_era


class ScoreStartTests(unittest.TestCase):
    def test_warmup_batch_keeps_january_start(self) -> None:
        self.assertEqual(gpr_score_start(GPR_WARMUP_START), GPR_WARMUP_START)

    def test_product_batch_never_pulls_warmup(self) -> None:
        self.assertEqual(gpr_score_start(INDIA_GPR_INDEX_START), INDIA_GPR_INDEX_START)
        self.assertEqual(gpr_score_start(date(2026, 8, 16)), date(2026, 8, 16))


class ForwardDayNormalizationTests(unittest.TestCase):
    def test_product_only_batch_stays_near_100(self) -> None:
        dates = pd.date_range("2026-08-09", periods=8, freq="D")
        daily = pd.DataFrame(
            {
                "date": dates,
                "raw_ratio": [0.001] * 8,
                "acts_ratio": [0.0005] * 8,
                "threats_ratio": [0.0005] * 8,
            }
        )
        self.assertFalse(should_split_era(daily, INDIA_GPR_INDEX_START.isoformat()))
        result = normalize_index(
            daily,
            INDIA_GPR_INDEX_START.isoformat(),
            dates[-1].strftime("%Y-%m-%d"),
        )
        self.assertGreaterEqual(float(result["gpr_index"].mean()), 50.0)
        self.assertTrue(result["gpr_7ma"].notna().all())

    def test_incremental_day_with_warmup_history_keeps_split_era(self) -> None:
        warmup_dates = pd.date_range("2026-01-01", periods=2, freq="D")
        product_dates = pd.date_range("2026-08-09", periods=8, freq="D")
        daily = pd.DataFrame(
            {
                "date": list(warmup_dates) + list(product_dates),
                "raw_ratio": [0.010, 0.010] + [0.001] * 8,
                "acts_ratio": [0.005, 0.005] + [0.0005] * 8,
                "threats_ratio": [0.005, 0.005] + [0.0005] * 8,
            }
        )
        self.assertTrue(should_split_era(daily, GPR_WARMUP_START.isoformat()))
        result = normalize_index(
            daily,
            GPR_WARMUP_START.isoformat(),
            product_dates[-1].strftime("%Y-%m-%d"),
        )
        india = result[result["date"] >= pd.Timestamp(INDIA_GPR_INDEX_START)]
        self.assertGreaterEqual(float(india["gpr_index"].mean()), 50.0)
        self.assertTrue(india["gpr_7ma"].notna().all())

    def test_corridor_hit_days_use_prior_warmup_rows(self) -> None:
        warmup = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
                "corridor": ["strait_of_hormuz"] * 2,
                "gpr_sum": [10.0, 10.0],
                "corridor_hit_count": [1, 1],
                "total_articles": [1000, 1000],
                "positive_articles": [50, 50],
                "matched_positive_articles": [1, 1],
                "raw_ratio": [0.010, 0.010],
            }
        )
        product = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-08-09", "2026-08-10"]),
                "corridor": ["strait_of_hormuz"] * 2,
                "gpr_sum": [1.0, 1.0],
                "corridor_hit_count": [1, 1],
                "total_articles": [100, 100],
                "positive_articles": [5, 5],
                "matched_positive_articles": [1, 1],
                "raw_ratio": [0.001, 0.001],
            }
        )
        rows = pd.concat([warmup, product], ignore_index=True)
        result = normalize_corridor_index(
            rows,
            GPR_WARMUP_START.isoformat(),
            "2026-08-10",
        )
        india = result[result["date"] >= pd.Timestamp(INDIA_GPR_INDEX_START)]
        self.assertEqual(india["score_status"].iloc[-1], "ok")
        self.assertGreaterEqual(float(india["corridor_risk_7ma"].iloc[-1]), 20.0)


class CorridorMergeHelpersTests(unittest.TestCase):
    def test_merge_prior_hits_keeps_warmup_rows(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            prior = pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-01-01"]),
                    "corridor": ["strait_of_hormuz"],
                    "gpr_score": [0.5],
                    "event_category": ["sanctions"],
                    "gpr_type": ["threat"],
                }
            )
            prior.to_parquet(out / "corridor_article_hits.parquet", index=False)
            new = pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-08-16"]),
                    "corridor": ["strait_of_hormuz"],
                    "gpr_score": [0.4],
                    "event_category": ["sanctions"],
                    "gpr_type": ["threat"],
                }
            )
            merged = _merge_prior_corridor_hits(
                new, out, pd.Timestamp(INDIA_GPR_INDEX_START)
            )
            self.assertEqual(len(merged), 2)
            self.assertEqual(
                set(pd.to_datetime(merged["date"]).dt.strftime("%Y-%m-%d")),
                {"2026-01-01", "2026-08-16"},
            )

    def test_merge_corridor_totals_keeps_prior_denominators(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            prior = pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-01-01"]),
                    "corridor": ["strait_of_hormuz"],
                    "total_articles": [1000],
                    "positive_articles": [50],
                    "matched_positive_articles": [1],
                    "raw_ratio": [0.01],
                }
            )
            prior.to_csv(out / "gpr_corridor_daily.csv", index=False)
            new_totals = pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-08-16"]),
                    "total_articles": [300],
                    "positive_articles": [8],
                    "matched_positive_articles": [2],
                }
            )
            merged = _merge_corridor_totals(
                new_totals, out, pd.Timestamp(INDIA_GPR_INDEX_START)
            )
            self.assertEqual(len(merged), 2)


class IncrementalHistoryTests(unittest.TestCase):
    def test_csv_history_rows_restore_ratio_fields(self) -> None:
        row = _ensure_ratio_fields(
            {
                "date": pd.Timestamp("2026-08-15"),
                "total_articles": 287,
                "gpr_sum": 2.5,
            }
        )
        self.assertAlmostEqual(row["raw_ratio"], 2.5 / 287, places=6)

    def test_incremental_merge_normalizes_product_rows(self) -> None:
        warmup_dates = pd.date_range("2026-01-01", periods=2, freq="D")
        product_dates = pd.date_range("2026-08-09", periods=7, freq="D")
        history = [
            _ensure_ratio_fields(
                {
                    "date": d,
                    "total_articles": 1000,
                    "gpr_sum": 10.0,
                    "raw_ratio": 0.01,
                    "acts_ratio": 0.005,
                    "threats_ratio": 0.005,
                }
            )
            for d in warmup_dates
        ]
        dirty = _ensure_ratio_fields(
            {
                "date": product_dates[-1],
                "total_articles": 287,
                "gpr_sum": 2.0,
                "raw_ratio": 2.0 / 287,
                "acts_ratio": 0.001,
                "threats_ratio": 0.001,
            }
        )
        product_history = [
            _ensure_ratio_fields(
                {
                    "date": d,
                    "total_articles": 300,
                    "gpr_sum": 1.0,
                    "raw_ratio": 1.0 / 300,
                    "acts_ratio": 0.0005,
                    "threats_ratio": 0.0005,
                }
            )
            for d in product_dates[:-1]
        ]
        daily_df = normalize_index(
            pd.DataFrame(history + product_history + [dirty]),
            GPR_WARMUP_START.isoformat(),
            product_dates[-1].strftime("%Y-%m-%d"),
        )
        india = daily_df[daily_df["date"] >= pd.Timestamp(INDIA_GPR_INDEX_START)]
        self.assertTrue(india["gpr_index"].notna().all())
        self.assertGreaterEqual(float(india["gpr_7ma"].iloc[-1]), 20.0)


if __name__ == "__main__":
    unittest.main()
