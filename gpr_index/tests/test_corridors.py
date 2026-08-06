"""Focused regression tests for the shared corridor location tagger."""

from __future__ import annotations

import unittest

import pandas as pd

from gpr_index.scripts.corridors import CORRIDOR_PLACES, CORRIDORS, tag_corridors
from news_dataset.nlp.locations import extract_locations


def representative_locations() -> pd.DataFrame:
    """Small hand-built fixture covering matches and India-wide leakage."""
    return pd.DataFrame(
        [
            {
                "case": "Hormuz",
                "V2Locations": "4#Strait of Hormuz#MU##26.5667#56.2500#0",
                "expected": ["strait_of_hormuz"],
            },
            {
                "case": "Ladakh",
                "V2Locations": "4#Ladakh#IN#IN30#34.1526#77.5771#0",
                "expected": ["india_china_lac"],
            },
            {
                "case": "Petrapole",
                "V2Locations": "4#Petrapole#IN#IN28#23.0500#88.8300#0",
                "expected": ["india_bangladesh_petrapole"],
            },
            {
                "case": "India-wide",
                "V2Locations": "1#India#IN#IN#20.0000#77.0000#1269750",
                "expected": [],
            },
        ]
    )


class CorridorTaggerTests(unittest.TestCase):
    def test_representative_locations(self) -> None:
        fixture = representative_locations()
        actual = fixture["V2Locations"].map(tag_corridors)
        self.assertEqual(
            actual.tolist(),
            fixture["expected"].tolist(),
            dict(zip(fixture["case"], actual)),
        )

    def test_maritime_bounds_absorb_unknown_coastal_name(self) -> None:
        locations = "4#Khasab###26.20#56.25#0"
        self.assertEqual(tag_corridors(locations), ["strait_of_hormuz"])

    def test_land_country_without_adm1_does_not_match(self) -> None:
        locations = "1#India#IN##20.0#77.0#0;1#China#CH##35.0#103.0#0"
        self.assertNotIn("india_china_lac", tag_corridors(locations))

    def test_public_registry_contract(self) -> None:
        self.assertEqual(len(CORRIDORS), 12)
        self.assertTrue(CORRIDOR_PLACES)
        for place in CORRIDOR_PLACES.values():
            self.assertTrue(place["aliases"])
            self.assertTrue(set(place["corridors"]) <= CORRIDORS.keys())

    def test_bare_hormuz_alias_matches(self) -> None:
        locations = extract_locations(
            "Attacks near Hormuz disrupt Suez traffic",
            "",
        )
        self.assertIn("strait_of_hormuz", tag_corridors(locations))

    def test_empty_and_malformed_input(self) -> None:
        self.assertEqual(tag_corridors(""), [])
        self.assertEqual(tag_corridors("not-a-location"), [])


if __name__ == "__main__":
    unittest.main()
