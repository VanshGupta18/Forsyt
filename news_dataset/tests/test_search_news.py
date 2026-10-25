import unittest

from news_dataset.db import build_news_search_sql


class BuildNewsSearchSqlTest(unittest.TestCase):
    def test_clamps_days_and_passes_params(self):
        self.assertEqual(build_news_search_sql("iran oil", 500)[1], ("iran oil", 90, 8))
        self.assertEqual(build_news_search_sql("x", 0, 3)[1], ("x", 1, 3))

    def test_query_is_parameterised_or_fts(self):
        sql, _ = build_news_search_sql("'; drop table articles;--")
        self.assertNotIn("drop table", sql)
        self.assertIn("plainto_tsquery('english', %s)", sql)
        self.assertIn("' | '", sql)


if __name__ == "__main__":
    unittest.main()
