"""Focused tests for corridor aggregation, validation, and CLI wiring."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from gpr_index import main as gpr_main
from gpr_index.scripts.corridor_index import (
    HIT_COLUMNS,
    aggregate_corridor_day,
    corridor_article_hits,
    normalize_corridor_index,
)
from gpr_index.scripts.download_gkg import select_time_slots
from gpr_index.scripts.validate_corridors import (
    check_match_coverage,
    check_parent_leakage,
    check_slot_sampling,
)
from news_dataset.nlp.locations import extract_locations


def scored_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "V2Locations": [
                "4#Strait of Hormuz#MU##26.5667#56.25#0",
                "4#Petrapole#IN#IN28#23.05#88.83#0",
                "1#India#IN#IN#20#77#0",
                "",
            ],
            "gpr_score": [0.5, 0.4, 0.8, 0.1],
            "event_category": ["sanctions", "other", "other", "none"],
            "gpr_type": ["threat", "act", "act", "none"],
        }
    )


class CorridorAggregationTests(unittest.TestCase):
    def test_hits_are_slim_and_positive_only(self) -> None:
        hits = corridor_article_hits(scored_fixture(), pd.Timestamp("2025-01-01"))
        self.assertEqual(hits.columns.tolist(), HIT_COLUMNS)
        self.assertEqual(
            set(hits["corridor"]),
            {"strait_of_hormuz", "india_bangladesh_petrapole"},
        )

    def test_aggregation_keeps_parent_denominator(self) -> None:
        daily = aggregate_corridor_day(
            scored_fixture(), pd.Timestamp("2025-01-01"), total_articles=10
        )
        hormuz = daily.loc[daily["corridor"] == "strait_of_hormuz"].iloc[0]
        self.assertEqual(len(daily), 12)
        self.assertAlmostEqual(hormuz["raw_ratio"], 0.05)
        self.assertEqual(hormuz["matched_positive_articles"], 2)

    def test_normalization_keeps_threat_and_exposure_layers(self) -> None:
        rows = pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
                "corridor": ["strait_of_hormuz", "strait_of_hormuz"],
                "gpr_sum": [1.0, 2.0],
                "corridor_hit_count": [1, 2],
                "total_articles": [100, 100],
                "positive_articles": [10, 10],
                "matched_positive_articles": [1, 2],
                "raw_ratio": [0.01, 0.02],
            }
        )
        result = normalize_corridor_index(rows, "2025-01-01", "2025-01-02")
        self.assertTrue((result["threat_index"] <= 100).all())
        self.assertTrue((result["corridor_risk"] <= 100).all())
        self.assertTrue((result["corridor_risk"] == result["energy_risk"]).all())
        self.assertIn("corridor_risk_7ma", result.columns)
        self.assertEqual(result["score_status"].iloc[-1], "ok")

    def test_zero_hit_day_yields_zero_risk(self) -> None:
        rows = pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
                "corridor": ["taiwan_south_china_sea"] * 3,
                "gpr_sum": [0.5, 0.0, 0.0],
                "corridor_hit_count": [1, 0, 0],
                "total_articles": [100, 100, 100],
                "positive_articles": [5, 5, 5],
                "matched_positive_articles": [1, 0, 0],
                "raw_ratio": [0.005, 0.0, 0.0],
            }
        )
        result = normalize_corridor_index(rows, "2025-01-01", "2025-01-03")
        quiet = result.loc[result["date"] == pd.Timestamp("2025-01-03")].iloc[0]
        self.assertEqual(quiet["corridor_risk"], 0.0)

    def test_seven_day_ma_smooths_single_day_spike(self) -> None:
        dates = pd.date_range("2025-01-01", periods=7)
        raw = [0.005, 0.005, 0.0, 0.0, 0.0, 0.02, 0.0]
        hits = [1, 1, 0, 0, 0, 2, 0]
        rows = pd.DataFrame(
            {
                "date": dates,
                "corridor": ["strait_of_malacca"] * 7,
                "gpr_sum": [v * 100 for v in raw],
                "corridor_hit_count": hits,
                "total_articles": [100] * 7,
                "positive_articles": [10] * 7,
                "matched_positive_articles": hits,
                "raw_ratio": raw,
            }
        )
        result = normalize_corridor_index(rows, "2025-01-01", "2025-01-07")
        spike_day = result.loc[result["date"] == dates[5]].iloc[0]
        self.assertGreater(spike_day["corridor_risk"], 0.0)
        self.assertLess(spike_day["corridor_risk_7ma"], spike_day["corridor_risk"] + 1e-6)

    def test_insufficient_history_before_min_hit_days(self) -> None:
        rows = pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-01-01"]),
                "corridor": ["taiwan_south_china_sea"],
                "gpr_sum": [0.5],
                "corridor_hit_count": [1],
                "total_articles": [100],
                "positive_articles": [5],
                "matched_positive_articles": [1],
                "raw_ratio": [0.005],
            }
        )
        result = normalize_corridor_index(rows, "2025-01-01", "2025-01-01")
        self.assertEqual(result["score_status"].iloc[0], "insufficient_history")
        self.assertEqual(result["corridor_risk"].iloc[0], 0.0)


class CorridorValidationTests(unittest.TestCase):
    def test_coverage_uses_unique_daily_match_counts(self) -> None:
        frame = pd.DataFrame(
            {
                "date": ["2025-01-01"] * 2,
                "positive_articles": [10, 10],
                "matched_positive_articles": [3, 3],
            }
        )
        self.assertAlmostEqual(check_match_coverage(frame).iloc[0]["coverage"], 0.3)

    def test_parent_leakage_flags_near_copy(self) -> None:
        dates = pd.date_range("2025-01-01", periods=4)
        corridors = pd.DataFrame(
            {
                "date": dates,
                "corridor": ["strait_of_hormuz"] * 4,
                "threat_index": [1.0, 2.0, 3.0, 4.0],
            }
        )
        parent = pd.DataFrame({"date": dates, "gpr_index": [2.0, 4.0, 6.0, 8.0]})
        self.assertEqual(check_parent_leakage(corridors, parent).iloc[0]["pass"], "NO")

    def test_slot_sampling_reports_ratio_bias(self) -> None:
        full = pd.DataFrame(
            {
                "date": ["2025-01-01", "2025-01-02"],
                "corridor": ["strait_of_hormuz"] * 2,
                "raw_ratio": [0.10, 0.20],
            }
        )
        sampled = full.copy()
        sampled["raw_ratio"] *= 1.05
        report = check_slot_sampling(full, sampled)
        self.assertAlmostEqual(report.iloc[0]["relative_bias"], 0.05)
        self.assertEqual(report.iloc[0]["pass"], "YES")


class CorridorCliAndParityTests(unittest.TestCase):
    def test_news_extractor_emits_shared_place_block(self) -> None:
        locations = extract_locations("Hormuz Strait disrupted", "")
        self.assertIn("4#Strait of Hormuz#MU##26.5667#56.25#0", locations)

    def test_every_fourth_slot_selection(self) -> None:
        slots = select_time_slots(4)
        self.assertEqual(len(slots), 24)
        self.assertEqual(slots[:2], ("0000", "0100"))

    def test_main_dispatches_corridor_command(self) -> None:
        module = Mock()
        argv = ["main.py", "corridor", "--resume"]
        with (
            patch.object(sys, "argv", argv),
            patch("importlib.import_module", return_value=module) as importer,
        ):
            gpr_main.main()
        importer.assert_called_once_with("scripts.corridor_index")
        module.main.assert_called_once_with()

    def test_news_path_parity_flags_silent_drops(self) -> None:
        gdelt = pd.Series(
            [
                "4#Strait of Hormuz#MU##26.5667#56.25#0",
                "4#Petrapole#IN#IN28#23.05#88.83#0",
                "4#Red Sea#EG##20#38#0",
            ]
        )
        news = pd.Series(
            [
                "4#Strait of Hormuz#MU##26.5667#56.25#0",
                "4#Petrapole#IN#IN28#23.05#88.83#0",
                "",
            ]
        )
        report = check_news_path_parity_from_series(gdelt, news)
        hormuz = report.loc[report["corridor"] == "strait_of_hormuz"].iloc[0]
        red_sea = report.loc[report["corridor"] == "red_sea_suez"].iloc[0]
        self.assertEqual(hormuz["pass"], "YES")
        self.assertEqual(red_sea["pass"], "NO")


def check_news_path_parity_from_series(
    gdelt_locations: pd.Series,
    news_locations: pd.Series,
) -> pd.DataFrame:
    """Test helper mirroring validate_corridors parity without filesystem I/O."""
    from gpr_index.scripts.corridors import CORRIDORS, tag_corridors

    def rates(locations: pd.Series) -> dict[str, float]:
        tags = locations.map(tag_corridors)
        denominator = len(tags)
        return {
            corridor: float(tags.map(lambda values: corridor in values).sum() / denominator)
            if denominator
            else float("nan")
            for corridor in CORRIDORS
        }

    gdelt_rates = rates(gdelt_locations)
    news_rates = rates(news_locations)
    rows = []
    for corridor in CORRIDORS:
        gdelt_rate = gdelt_rates[corridor]
        news_rate = news_rates[corridor]
        ratio = news_rate / gdelt_rate if gdelt_rate > 0 else float("nan")
        rows.append(
            {
                "corridor": corridor,
                "gdelt_match_rate": gdelt_rate,
                "news_match_rate": news_rate,
                "news_to_gdelt_ratio": ratio,
                "pass": "N/A" if gdelt_rate == 0 else ("YES" if news_rate > 0 else "NO"),
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()
