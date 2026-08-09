import tempfile
import unittest
from pathlib import Path

from app.data.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")

    def tearDown(self): self.tmp.cleanup()

    def test_watchlist_lifecycle(self):
        created = self.db.create_watchlist("Core")
        self.db.add_watchlist_item(created["id"], "msft")
        self.db.add_watchlist_item(created["id"], "MSFT")
        self.assertEqual(self.db.watchlist(created["id"])["tickers"], ["MSFT"])
        self.assertEqual(self.db.list_watchlists()[0]["item_count"], 1)
        self.assertTrue(self.db.remove_watchlist_item(created["id"], "msft"))
        self.assertFalse(self.db.remove_watchlist_item(created["id"], "msft"))

    def test_missing_watchlist_rejected(self):
        with self.assertRaises(KeyError): self.db.add_watchlist_item(999, "AAPL")


if __name__ == "__main__": unittest.main()
