from __future__ import annotations
import re

from app.config import settings
from app.data.database import Database
from app.data.market import YahooChartClient
from app.data.sec import SecClient
from app.data.universe import UniverseClient
from app.finance.metrics import calculate_metrics, build_ttm
from app.finance.quality import data_quality_report
from app.finance.thesis import build_decision_support
from app.finance.scoring import calculate_growth_score, calculate_health_score, calculate_momentum_score, calculate_quality_score, calculate_stock_score, calculate_valuation_score, detect_red_flags
from app.models import StockAnalysis


class AnalysisService:
    def __init__(self):
        self.sec = SecClient(settings.sec_user_agent, ttl=settings.cache_ttl_seconds, timeout=settings.http_timeout_seconds)
        self.market = YahooChartClient(timeout=settings.http_timeout_seconds)
        self.db = Database(settings.database_path)
        self.universes = UniverseClient(ttl=86400, timeout=settings.http_timeout_seconds)

    def analyze(self, ticker: str) -> StockAnalysis:
        ticker = ticker.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,9}",ticker):
            raise ValueError("Invalid ticker format")
        company, annual, quarterly = self.sec.fetch_financials(ticker)
        ttm = build_ttm(quarterly)
        latest = (ttm or annual[-1]).values if ttm or annual else {}
        try:
            price = self.market.fetch(ticker, latest.get("shares_outstanding"), latest.get("total_debt"), latest.get("cash"))
        except (httpx.HTTPError, KeyError, IndexError):
            price = None
        metrics = calculate_metrics(annual, price, ttm)
        scores = {
            "quality": calculate_quality_score(metrics), "growth": calculate_growth_score(metrics),
            "valuation": calculate_valuation_score(metrics), "financial_health": calculate_health_score(metrics),
            "momentum": calculate_momentum_score(metrics),
        }
        final, coverage = calculate_stock_score(scores, settings.score_weights)
        flags=detect_red_flags(metrics)
        result = StockAnalysis(ticker=ticker,company_name=company,metrics=metrics,scores=scores,final_score=final,score_coverage=coverage,red_flags=flags,price=price,annual_financials=annual,quarterly_financials=quarterly,ttm_financials=ttm,data_quality=data_quality_report(annual,quarterly,ttm),decision_support=build_decision_support(metrics,scores,final,coverage,flags),provenance={"fundamentals":"SEC CompanyFacts","price":"Yahoo Finance chart endpoint","method":"deterministic"})
        self.db.save_analysis(result)
        return result


# Kept at module level for simple dependency injection in tests.
import httpx
