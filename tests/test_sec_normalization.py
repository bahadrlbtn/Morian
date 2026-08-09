import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from app.data.sec import SecClient


def concept(value):
    return {"units":{"USD":[{"val":value,"start":"2025-01-01","end":"2025-12-31","filed":"2026-02-01","form":"10-K","fp":"FY","fy":2025}]}}


class SecNormalizationTests(unittest.TestCase):
    def test_exchange_ticker_shape_maps_to_company_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=SecClient("Tests test@example.com",Path(tmp))
            base={"0":{"ticker":"AAPL","title":"Apple","cik_str":320193}}
            exchange={"fields":["cik","name","ticker","exchange"],"data":[[4904,"American Electric Power","AEP","Nasdaq"]]}
            with patch.object(client,"_get_json",side_effect=[base,exchange]):
                result=client.ticker_map()
            self.assertEqual(result["AEP"]["cik_str"],4904)
            self.assertEqual(result["AEP"]["title"],"American Electric Power")
    def test_debt_components_are_summed(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=SecClient("Tests test@example.com",Path(tmp))
            facts={"facts":{"us-gaap":{"LongTermDebtCurrent":concept(20),"LongTermDebtNoncurrent":concept(80),"Revenues":concept(500)}}}
            annual,_=client.normalize("TEST",facts)
            self.assertEqual(annual[0].values["total_debt"],100)
            self.assertEqual(annual[0].values["revenue"],500)

    def test_reported_total_debt_takes_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=SecClient("Tests test@example.com",Path(tmp))
            facts={"facts":{"us-gaap":{"LongTermDebtAndFinanceLeaseObligations":concept(105),"LongTermDebtCurrent":concept(20),"LongTermDebtNoncurrent":concept(80),"Revenues":concept(500)}}}
            annual,_=client.normalize("TEST",facts)
            self.assertEqual(annual[0].values["total_debt"],105)

    def test_comparative_quarter_inside_10k_is_not_annual(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=SecClient("Tests test@example.com",Path(tmp))
            facts={"facts":{"us-gaap":{"Revenues":{"units":{"USD":[
                {"val":25,"start":"2025-10-01","end":"2025-12-31","filed":"2026-02-01","form":"10-K","fp":"FY","fy":2026},
                {"val":100,"start":"2025-01-01","end":"2025-12-31","filed":"2026-02-01","form":"10-K","fp":"FY","fy":2026}
            ]}}}}}
            annual,_=client.normalize("TEST",facts)
            self.assertEqual(len(annual),1)
            self.assertEqual(annual[0].values["revenue"],100)
            self.assertEqual(annual[0].fiscal_year,2025)


if __name__ == "__main__": unittest.main()
