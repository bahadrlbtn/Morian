from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class DataPoint(BaseModel):
    value: float | None
    unit: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    filing_date: date | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    form: str | None = None
    source: str
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class FinancialPeriod(BaseModel):
    ticker: str
    period_end: date
    period_type: Literal["annual", "quarterly", "ttm"]
    fiscal_year: int | None = None
    filing_date: date | None = None
    form: str | None = None
    source: str = "SEC CompanyFacts"
    values: dict[str, float | None]


class PriceSnapshot(BaseModel):
    ticker: str
    price: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    returns: dict[str, float | None] = Field(default_factory=dict)
    moving_averages: dict[str, float | None] = Field(default_factory=dict)
    distance_from_52w_high: float | None = None
    as_of: datetime = Field(default_factory=datetime.utcnow)
    source: str = "Yahoo Finance chart"
    history: list[dict[str, float | str]] = Field(default_factory=list)


class RedFlag(BaseModel):
    code: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ScoreResult(BaseModel):
    score: float | None
    coverage: float
    components: dict[str, float | None]


class StockAnalysis(BaseModel):
    ticker: str
    company_name: str | None = None
    metrics: dict[str, float | None]
    scores: dict[str, ScoreResult]
    final_score: float | None
    score_coverage: float
    red_flags: list[RedFlag]
    price: PriceSnapshot | None = None
    annual_financials: list[FinancialPeriod] = Field(default_factory=list)
    quarterly_financials: list[FinancialPeriod] = Field(default_factory=list)
    ttm_financials: FinancialPeriod | None = None
    data_quality: dict[str, Any] = Field(default_factory=dict)
    decision_support: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
