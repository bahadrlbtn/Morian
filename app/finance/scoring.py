from __future__ import annotations

from app.config import ScoreWeights
from app.finance.calculations import clamp, linear_score, weighted_average
from app.models import RedFlag, ScoreResult


DEFAULT_COMPONENT_WEIGHTS = {
    "quality":{"revenue_consistency":15,"earnings_consistency":15,"roic":20,"margins":15,"free_cash_flow":15,"balance_sheet":10,"share_dilution":10},
    "growth":{"revenue_5y":25,"revenue_3y":20,"eps_5y":20,"eps_3y":15,"fcf_growth":10,"operating_income":10},
    "valuation":{"fcf_yield":25,"earnings_yield":15,"ev_ebitda":20,"pe":15,"growth_quality":15,"historical_discount":10},
    "financial_health":{"net_debt_ebitda":25,"debt_equity":15,"current_ratio":15,"interest_coverage":15,"cash_debt":15,"fcf":15},
    "momentum":{"return_1m":5,"return_3m":15,"return_6m":20,"return_12m":25,"above_ma50":10,"above_ma200":15,"near_high":10},
}


def _result(components: dict[str, float | None], weights: dict[str, float]) -> ScoreResult:
    score, coverage = weighted_average(components, weights)
    # Sparse evidence must not produce an apparently authoritative category score.
    if coverage < .40:
        score = None
    return ScoreResult(score=score, coverage=coverage, components=components)


def calculate_quality_score(m: dict[str, float | None], weights: dict[str,float] | None = None) -> ScoreResult:
    components = {
        "revenue_consistency": linear_score(m.get("revenue_cagr_5y"), 0, .12),
        "earnings_consistency": linear_score(m.get("eps_cagr_5y"), 0, .15),
        "roic": linear_score(m.get("roic"), .05, .25),
        "margins": linear_score(m.get("operating_margin"), .05, .30),
        "free_cash_flow": linear_score(m.get("fcf_margin"), 0, .20),
        "balance_sheet": linear_score(m.get("net_debt_ebitda"), 4, 0),
        "share_dilution": linear_score(m.get("shares_growth"), .08, -.02),
    }
    return _result(components, weights or DEFAULT_COMPONENT_WEIGHTS["quality"])


def calculate_growth_score(m: dict[str, float | None], weights: dict[str,float] | None = None) -> ScoreResult:
    components = {
        "revenue_5y": linear_score(m.get("revenue_cagr_5y"), 0, .20),
        "revenue_3y": linear_score(m.get("revenue_cagr_3y"), 0, .25),
        "eps_5y": linear_score(m.get("eps_cagr_5y"), 0, .25),
        "eps_3y": linear_score(m.get("eps_cagr_3y"), 0, .30),
        "fcf_growth": linear_score(m.get("fcf_cagr_3y") if m.get("fcf_cagr_3y") is not None else m.get("fcf_growth_yoy"), -.10, .25),
        "operating_income": linear_score(m.get("operating_income_cagr_3y") if m.get("operating_income_cagr_3y") is not None else m.get("operating_income_growth"), 0, .20),
    }
    return _result(components, weights or DEFAULT_COMPONENT_WEIGHTS["growth"])


def calculate_valuation_score(m: dict[str, float | None], weights: dict[str,float] | None = None) -> ScoreResult:
    quality_adjustment = clamp(((m.get("roic") or 0) + (m.get("revenue_cagr_5y") or 0)) * 100)
    components = {
        "fcf_yield": linear_score(m.get("fcf_yield"), 0, .08),
        "earnings_yield": linear_score(m.get("earnings_yield"), 0, .08),
        "ev_ebitda": linear_score(m.get("ev_ebitda"), 30, 8),
        "pe": linear_score(m.get("pe"), 40, 12),
        "growth_quality": quality_adjustment if m.get("roic") is not None or m.get("revenue_cagr_5y") is not None else None,
        "historical_discount": m.get("historical_valuation_score"),
    }
    return _result(components, weights or DEFAULT_COMPONENT_WEIGHTS["valuation"])


def calculate_health_score(m: dict[str, float | None], weights: dict[str,float] | None = None) -> ScoreResult:
    components = {
        "net_debt_ebitda": linear_score(m.get("net_debt_ebitda"), 5, 0),
        "debt_equity": linear_score(m.get("debt_equity"), 2, .2),
        "current_ratio": linear_score(m.get("current_ratio"), .7, 2),
        "interest_coverage": linear_score(m.get("interest_coverage"), 1, 12),
        "cash_debt": linear_score(m.get("cash_total_debt"), .1, 1),
        "fcf": linear_score(m.get("fcf_margin"), -.05, .15),
    }
    return _result(components, weights or DEFAULT_COMPONENT_WEIGHTS["financial_health"])


def calculate_momentum_score(m: dict[str, float | None], weights: dict[str,float] | None = None) -> ScoreResult:
    components = {
        "return_1m": linear_score(m.get("return_1m"), -.15, .15),
        "return_3m": linear_score(m.get("return_3m"), -.25, .30),
        "return_6m": linear_score(m.get("return_6m"), -.35, .50),
        "return_12m": linear_score(m.get("return_12m"), -.40, .70),
        "above_ma50": linear_score(m.get("price_vs_ma50"), -.15, .15),
        "above_ma200": linear_score(m.get("price_vs_ma200"), -.25, .30),
        "near_high": linear_score(m.get("distance_from_52w_high"), -.50, 0),
    }
    return _result(components, weights or DEFAULT_COMPONENT_WEIGHTS["momentum"])


def calculate_stock_score(scores: dict[str, ScoreResult], weights: ScoreWeights | dict[str,float]) -> tuple[float | None, float]:
    values = {k: v.score for k, v in scores.items()}
    category_weights=weights if isinstance(weights,dict) else vars(weights)
    score, _ = weighted_average(values, category_weights)
    coverage=sum(category_weights[k]*scores[k].coverage for k in category_weights)
    coverage=round(coverage/sum(category_weights.values()),4)
    # Below 60% weighted evidence, ranking the company would reward missing data.
    return (score if coverage >= .60 else None), coverage


def detect_red_flags(m: dict[str, float | None]) -> list[RedFlag]:
    rules = [
        ("REVENUE_DECLINE", "revenue_growth_yoy", lambda x: x < 0, "MEDIUM", "Revenue is declining year over year"),
        ("EPS_DECLINE", "eps_growth_yoy", lambda x: x < 0, "MEDIUM", "EPS is declining year over year"),
        ("NEGATIVE_FCF", "free_cash_flow", lambda x: x < 0, "HIGH", "Free cash flow is negative"),
        ("PERSISTENT_NEGATIVE_FCF", "negative_fcf_years", lambda x: x >= 3, "HIGH", "Free cash flow has been negative for at least three consecutive annual periods"),
        ("RAPID_DEBT_GROWTH", "debt_growth", lambda x: x > .25, "HIGH", "Debt increased by more than 25%"),
        ("SHARE_DILUTION", "shares_growth", lambda x: x > .05, "MEDIUM", "Share dilution exceeds 5%"),
        ("HIGH_SBC", "sbc_revenue", lambda x: x > .15, "MEDIUM", "Stock-based compensation exceeds 15% of revenue"),
        ("GROSS_MARGIN_DECLINE", "gross_margin_change", lambda x: x < -.03, "MEDIUM", "Gross margin declined by more than 3 percentage points"),
        ("OPERATING_MARGIN_DECLINE", "operating_margin_change", lambda x: x < -.03, "MEDIUM", "Operating margin declined by more than 3 percentage points"),
        ("ROIC_DECLINE", "roic_change", lambda x: x < -.05, "MEDIUM", "ROIC declined by more than 5 percentage points"),
        ("HIGH_NET_DEBT", "net_debt_ebitda", lambda x: x > 4, "HIGH", "Net debt / EBITDA exceeds 4x"),
        ("WEAK_INTEREST_COVERAGE", "interest_coverage", lambda x: x < 2, "HIGH", "Interest coverage is below 2x"),
        ("HISTORICALLY_EXPENSIVE", "historical_pe_discount", lambda x: x > .40, "MEDIUM", "P/E is more than 40% above its five-year historical median"),
    ]
    flags = []
    for code, key, predicate, severity, message in rules:
        value = m.get(key)
        if value is not None and predicate(value):
            flags.append(RedFlag(code=code, severity=severity, message=message, evidence={key: value}))
    return flags
