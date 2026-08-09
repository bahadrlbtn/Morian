import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app, service
from app.data.database import Database
from app.models import ScoreResult, StockAnalysis


def analysis(ticker: str, final: float) -> StockAnalysis:
    scores={k:ScoreResult(score=final,coverage=1,components={}) for k in ("quality","growth","valuation","financial_health","momentum")}
    return StockAnalysis(ticker=ticker,company_name=f"{ticker} Inc.",metrics={"roic":.2,"free_cash_flow":100,"revenue_cagr_5y":.12},scores=scores,final_score=final,score_coverage=1,red_flags=[],data_quality={"status":"GOOD"})


class ApiTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(app)

    def test_compare_ranks_and_csv_exports(self):
        fake=lambda ticker: analysis(ticker,90 if ticker=="MSFT" else 70)
        with patch.object(service,"analyze",side_effect=fake):
            response=self.client.post("/api/compare",json={"tickers":["AAPL","MSFT"]})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()["results"][0]["ticker"],"MSFT")
            csv_response=self.client.get("/api/export/comparison.csv?tickers=AAPL,MSFT")
            self.assertEqual(csv_response.status_code,200)
            self.assertIn("final_score",csv_response.text)

    def test_persistent_screen_job_completes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(service,"db",Database(Path(tmp)/"api.db")), patch.object(service,"analyze",side_effect=lambda ticker:analysis(ticker,80)):
            created=self.client.post("/api/jobs/screen",json={"tickers":["AAPL","MSFT"]})
            self.assertEqual(created.status_code,202)
            job=self.client.get(f"/api/jobs/{created.json()['id']}").json()
            self.assertEqual(job["status"],"COMPLETED")
            self.assertEqual(job["progress"],2)

    def test_morian_operational_endpoints_and_headers(self):
        config=self.client.get("/api/config")
        self.assertEqual(config.json()["name"],"Morian")
        self.assertIn("X-Request-ID",config.headers)
        self.assertEqual(config.headers["X-Frame-Options"],"DENY")
        self.assertEqual(self.client.get("/api/ready").json()["status"],"ready")
        dashboard=self.client.get("/api/dashboard")
        self.assertEqual(dashboard.status_code,200)
        self.assertIn("companies",dashboard.json()["counts"])

    def test_invalid_ticker_is_rejected(self):
        response=self.client.post("/api/watchlists/1/items",json={"ticker":"../bad"})
        self.assertEqual(response.status_code,422)

    def test_custom_rescore_does_not_persist_profile(self):
        with patch.object(service,"analyze",return_value=analysis("MSFT",70)):
            response=self.client.post("/api/stocks/MSFT/rescore",json={"profile":"custom","category_weights":{"quality":100,"growth":0,"valuation":0,"financial_health":0,"momentum":0}})
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()["persisted"])
        self.assertEqual(response.json()["applied_profile"]["category_weights"]["quality"],100)

    def test_scoring_config_exposes_metric_weights(self):
        data=self.client.get("/api/scoring/config").json()
        self.assertIn("balanced",data["profiles"])
        self.assertIn("roic",data["default_component_weights"]["quality"])

    def test_screen_returns_closest_matches_when_filters_are_too_strict(self):
        with patch.object(service,"analyze",side_effect=lambda ticker:analysis(ticker,80)):
            response=self.client.post("/api/screen",json={"tickers":["AAPL","MSFT"],"filters":[{"metric":"roic","operator":">","value":10}]})
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertTrue(data["screening"]["fallback"])
        self.assertEqual(len(data["results"]),2)
        self.assertIn("closest",data["screening"]["message"].lower())


if __name__ == "__main__": unittest.main()
