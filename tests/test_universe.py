import unittest
from app.data.universe import UniverseClient


class UniverseTests(unittest.TestCase):
    def test_parse_nasdaq100(self):
        payload={"data":{"date":"Aug 6, 2026","data":{"rows":[{"symbol":" AAPL ","companyName":"Apple Inc.\nCommon Stock","marketCap":"4,500,000"}]}}}
        result=UniverseClient.parse_nasdaq100(payload)
        self.assertEqual(result["members"][0]["ticker"],"AAPL")
        self.assertEqual(result["members"][0]["market_cap"],4500000)
        self.assertNotIn("\n",result["members"][0]["company_name"])

    def test_empty_response_is_rejected(self):
        with self.assertRaises(ValueError): UniverseClient.parse_nasdaq100({"data":{}})


if __name__ == "__main__": unittest.main()
