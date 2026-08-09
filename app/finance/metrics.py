from __future__ import annotations

from app.finance.calculations import calculate_cagr, calculate_fcf, calculate_roic, growth_rate, safe_divide, linear_score
from app.models import FinancialPeriod, PriceSnapshot
from app.data.sec import FLOW_METRICS


def _v(period: FinancialPeriod | None, key: str) -> float | None:
    return period.values.get(key) if period else None


def build_ttm(quarterly: list[FinancialPeriod]) -> FinancialPeriod | None:
    periods=sorted(quarterly,key=lambda p:p.period_end)[-4:]
    if len(periods)<4: return None
    keys=set().union(*(p.values for p in periods)); values={}
    for key in keys:
        vals=[p.values.get(key) for p in periods]
        values[key]=(sum(vals) if all(v is not None for v in vals) else None) if key in FLOW_METRICS else periods[-1].values.get(key)
    return FinancialPeriod(ticker=periods[-1].ticker,period_end=periods[-1].period_end,period_type="ttm",fiscal_year=periods[-1].fiscal_year,filing_date=periods[-1].filing_date,form="TTM calculated",source="SEC CompanyFacts; deterministic TTM",values=values)


def calculate_metrics(
    annual: list[FinancialPeriod], price: PriceSnapshot | None = None, ttm: FinancialPeriod | None = None
) -> dict[str, float | None]:
    periods = sorted(annual, key=lambda p: p.period_end)
    latest_annual = periods[-1] if periods else None
    latest = ttm or latest_annual
    previous = periods[-2] if len(periods) > 1 else None
    three_back = periods[-4] if len(periods) >= 4 else None
    five_back = periods[-6] if len(periods) >= 6 else None

    revenue = _v(latest, "revenue")
    net_income = _v(latest, "net_income")
    operating_income = _v(latest, "operating_income")
    ocf = _v(latest, "operating_cash_flow")
    capex = _v(latest, "capex")
    fcf = calculate_fcf(ocf, capex)
    debt = _v(latest, "total_debt")
    cash = _v(latest, "cash")
    equity = _v(latest, "equity")
    shares = _v(latest, "shares_outstanding")
    eps = _v(latest, "eps_diluted")
    market_cap = price.market_cap if price else None
    enterprise_value = price.enterprise_value if price else None
    ebitda = _v(latest, "ebitda")
    tax_rate = safe_divide(_v(latest, "income_tax"), _v(latest, "income_before_tax"))

    historical_pes=[]
    if price and price.history:
        for period in periods[-6:-1]:
            eps_value=_v(period,"eps_diluted")
            candidates=[x for x in price.history if str(x["date"])<=str(period.period_end)]
            historical_price=float(candidates[-1]["close"]) if candidates else None
            pe=safe_divide(historical_price,eps_value)
            if pe is not None and pe>0: historical_pes.append(pe)
    historical_pe_median=sorted(historical_pes)[len(historical_pes)//2] if historical_pes else None
    current_pe=safe_divide(price.price if price else None, eps)
    historical_pe_discount=(safe_divide(current_pe,historical_pe_median)-1) if current_pe is not None and historical_pe_median else None
    historical_valuation_score=linear_score(historical_pe_discount,.50,-.30) if historical_pe_discount is not None else None
    previous_fcf=calculate_fcf(_v(previous,"operating_cash_flow"),_v(previous,"capex"))
    three_fcf=calculate_fcf(_v(three_back,"operating_cash_flow"),_v(three_back,"capex"))
    five_fcf=calculate_fcf(_v(five_back,"operating_cash_flow"),_v(five_back,"capex"))
    dividend_yield=safe_divide(abs(_v(latest,"dividends_paid")) if _v(latest,"dividends_paid") is not None else None,market_cap)
    shares_growth=growth_rate(shares,_v(previous,"shares_outstanding"))
    buyback_yield=-shares_growth if shares_growth is not None else None
    previous_revenue=_v(previous,"revenue")
    current_gross_margin=safe_divide(_v(latest,"gross_profit"),revenue)
    previous_gross_margin=safe_divide(_v(previous,"gross_profit"),previous_revenue)
    current_operating_margin=safe_divide(operating_income,revenue)
    previous_operating_margin=safe_divide(_v(previous,"operating_income"),previous_revenue)
    previous_tax=safe_divide(_v(previous,"income_tax"),_v(previous,"income_before_tax"))
    previous_roic=calculate_roic(_v(previous,"operating_income"),previous_tax,_v(previous,"total_debt"),_v(previous,"equity"),_v(previous,"cash"))
    current_roic=calculate_roic(operating_income,tax_rate,debt,equity,cash)
    negative_fcf_years=0
    for period in reversed(periods):
        period_fcf=calculate_fcf(_v(period,"operating_cash_flow"),_v(period,"capex"))
        if period_fcf is not None and period_fcf<0: negative_fcf_years+=1
        else: break
    metrics: dict[str, float | None] = {
        "revenue": revenue,
        "net_income": net_income,
        "operating_income": operating_income,
        "operating_cash_flow": ocf,
        "free_cash_flow": fcf,
        "market_cap": market_cap,
        "pe": current_pe,
        "ps": safe_divide(market_cap, revenue),
        "pb": safe_divide(market_cap, equity),
        "ev_ebitda": safe_divide(enterprise_value, ebitda),
        "ev_ebit": safe_divide(enterprise_value, operating_income),
        "price_fcf": safe_divide(market_cap, fcf),
        "fcf_yield": safe_divide(fcf, market_cap),
        "earnings_yield": safe_divide(net_income, market_cap),
        "revenue_growth_yoy": growth_rate(revenue, _v(previous, "revenue")),
        "revenue_cagr_3y": calculate_cagr(_v(three_back, "revenue"), revenue, 3),
        "revenue_cagr_5y": calculate_cagr(_v(five_back, "revenue"), revenue, 5),
        "eps_growth_yoy": growth_rate(eps, _v(previous, "eps_diluted")),
        "eps_cagr_3y": calculate_cagr(_v(three_back, "eps_diluted"), eps, 3),
        "eps_cagr_5y": calculate_cagr(_v(five_back, "eps_diluted"), eps, 5),
        "fcf_growth_yoy": growth_rate(fcf, previous_fcf),
        "fcf_cagr_3y": calculate_cagr(three_fcf,fcf,3),
        "fcf_cagr_5y": calculate_cagr(five_fcf,fcf,5),
        "operating_income_growth": growth_rate(operating_income, _v(previous, "operating_income")),
        "operating_income_cagr_3y": calculate_cagr(_v(three_back,"operating_income"),operating_income,3),
        "operating_income_cagr_5y": calculate_cagr(_v(five_back,"operating_income"),operating_income,5),
        "gross_margin": current_gross_margin,
        "gross_margin_change": None if current_gross_margin is None or previous_gross_margin is None else current_gross_margin-previous_gross_margin,
        "operating_margin": current_operating_margin,
        "operating_margin_change": None if current_operating_margin is None or previous_operating_margin is None else current_operating_margin-previous_operating_margin,
        "net_margin": safe_divide(net_income, revenue),
        "fcf_margin": safe_divide(fcf, revenue),
        "roe": safe_divide(net_income, equity),
        "roa": safe_divide(net_income, _v(latest, "assets")),
        "roic": current_roic,
        "roic_change": None if current_roic is None or previous_roic is None else current_roic-previous_roic,
        "debt_equity": safe_divide(debt, equity),
        "net_debt_ebitda": safe_divide(None if debt is None or cash is None else debt - cash, ebitda),
        "current_ratio": safe_divide(_v(latest, "current_assets"), _v(latest, "current_liabilities")),
        "quick_ratio": safe_divide(None if _v(latest, "current_assets") is None or _v(latest, "inventory") is None else _v(latest, "current_assets") - _v(latest, "inventory"), _v(latest, "current_liabilities")),
        "interest_coverage": safe_divide(operating_income, _v(latest, "interest_expense")),
        "cash_total_debt": safe_divide(cash, debt),
        "debt_growth": growth_rate(debt, _v(previous, "total_debt")),
        "fcf_net_income": safe_divide(fcf, net_income),
        "capex_revenue": safe_divide(abs(capex) if capex is not None else None, revenue),
        "sbc_revenue": safe_divide(_v(latest, "stock_based_compensation"), revenue),
        "shares_growth": shares_growth,
        "buyback_yield": buyback_yield,
        "dividend_yield": dividend_yield,
        "dividend_growth": growth_rate(abs(_v(latest,"dividends_paid")) if _v(latest,"dividends_paid") is not None else None,abs(_v(previous,"dividends_paid")) if _v(previous,"dividends_paid") is not None else None),
        "total_shareholder_yield": dividend_yield+buyback_yield if dividend_yield is not None and buyback_yield is not None else None,
        "historical_pe_median":historical_pe_median,
        "historical_pe_discount":historical_pe_discount,
        "historical_valuation_score":historical_valuation_score,
        "negative_fcf_years":float(negative_fcf_years),
    }
    if price:
        metrics.update(price.returns)
        metrics.update(price.moving_averages)
        metrics["distance_from_52w_high"] = price.distance_from_52w_high
    return metrics
