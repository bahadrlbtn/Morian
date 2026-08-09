import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.data.database import Database
from app.finance.metrics import build_ttm
from app.finance.quality import data_quality_report
from app.models import FinancialPeriod
from app.rag import classify_query
from app.finance.thesis import build_decision_support
from app.models import ScoreResult


def quarter(month: int, revenue: float, debt: float = 10) -> FinancialPeriod:
    return FinancialPeriod(ticker="TEST",period_end=date(2025,month,28),period_type="quarterly",values={"revenue":revenue,"operating_cash_flow":revenue/5,"capex":revenue/20,"total_debt":debt,"assets":100,"equity":50,"cash":20,"shares_outstanding":10})


class PipelineTests(unittest.TestCase):
    def test_ttm_sums_flows_and_keeps_latest_balance(self):
        ttm=build_ttm([quarter(3,10,13),quarter(6,20,12),quarter(9,30,11),quarter(12,40,10)])
        self.assertEqual(ttm.values["revenue"],100)
        self.assertEqual(ttm.values["total_debt"],10)
        self.assertEqual(ttm.period_type,"ttm")

    def test_ttm_does_not_replace_missing_flow_with_latest_quarter(self):
        periods=[quarter(3,10),quarter(6,20),quarter(9,30),quarter(12,40)]
        periods[0].values["revenue"]=None
        self.assertIsNone(build_ttm(periods).values["revenue"])

    def test_quality_report_exposes_missing_values(self):
        report=data_quality_report([], [quarter(3,10)], None)
        self.assertEqual(report["status"],"PARTIAL")
        self.assertIn("Fewer than four discrete quarters; TTM unavailable",report["warnings"])

    def test_query_router(self):
        self.assertEqual(classify_query("MSFT revenue CAGR and ROIC nedir?"),"structured")
        self.assertEqual(classify_query("Yönetimin açıkladığı temel riskler nelerdir?"),"filing_rag")

    def test_persistent_job_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/"jobs.db")
            job=db.create_job("job-1","screen",{"tickers":["AAPL"]},1)
            self.assertEqual(job["status"],"QUEUED")
            db.update_job("job-1",status="RUNNING",progress=1)
            db.update_job("job-1",status="COMPLETED",result={"results":[]})
            finished=db.get_job("job-1")
            self.assertEqual(finished["status"],"COMPLETED")
            self.assertEqual(finished["result"],{"results":[]})

    def test_decision_support_uses_numeric_evidence(self):
        scores={"quality":ScoreResult(score=80,coverage=1,components={})}
        result=build_decision_support({"roic":.22,"revenue_cagr_5y":.14,"free_cash_flow":100,"operating_margin":.25},scores,75,.9,[])
        self.assertEqual(result["label"],"STRONG_RESEARCH_CANDIDATE")
        self.assertTrue(any(x["code"]=="HIGH_ROIC" for x in result["why_consider"]))
        self.assertIn("not investment advice",result["disclaimer"])
        self.assertIn("simple_label",result)
        self.assertTrue(any(x["title"]=="Profitability" for x in result["simple_metrics"]))


if __name__ == "__main__": unittest.main()
