from __future__ import annotations

from typing import Any
from app.models import RedFlag, ScoreResult


def _pct(value: float) -> str: return f"{value*100:.1f}%"


def build_decision_support(metrics: dict[str,float|None], scores: dict[str,ScoreResult], final_score: float|None, coverage: float, flags: list[RedFlag]) -> dict[str,Any]:
    choose=[];avoid=[]
    roic=metrics.get("roic");growth=metrics.get("revenue_cagr_5y");fcf=metrics.get("free_cash_flow");fcf_yield=metrics.get("fcf_yield");margin=metrics.get("operating_margin");leverage=metrics.get("net_debt_ebitda");dilution=metrics.get("shares_growth");discount=metrics.get("historical_pe_discount")
    if roic is not None and roic>=.15: choose.append({"code":"HIGH_ROIC","title":"Earns strong returns on invested capital","evidence":f"Return on invested capital {_pct(roic)}"})
    if growth is not None and growth>=.10: choose.append({"code":"DURABLE_GROWTH","title":"Sales are growing strongly over the long term","evidence":f"Five-year annualized growth {_pct(growth)}"})
    if fcf is not None and fcf>0: choose.append({"code":"POSITIVE_FCF","title":"Core operations generate real cash","evidence":f"Free cash flow {fcf:,.0f}"})
    if fcf_yield is not None and fcf_yield>=.04: choose.append({"code":"FCF_YIELD","title":"Attractive cash-flow yield","evidence":f"FCF yield {_pct(fcf_yield)}"})
    if margin is not None and margin>=.20: choose.append({"code":"HIGH_MARGIN","title":"Strong operating economics","evidence":f"Operating margin {_pct(margin)}"})
    if leverage is not None and leverage<=1: choose.append({"code":"LOW_LEVERAGE","title":"Conservative leverage","evidence":f"Net debt / EBITDA {leverage:.2f}x"})
    if discount is not None and discount<=-.15: choose.append({"code":"HISTORICAL_DISCOUNT","title":"Below historical valuation","evidence":f"P/E vs 5Y median {_pct(discount)}"})
    for flag in flags:
        if flag.severity in {"HIGH","MEDIUM"}: avoid.append({"code":flag.code,"title":flag.message,"evidence":flag.evidence,"severity":flag.severity})
    if growth is not None and growth<0: avoid.append({"code":"NEGATIVE_LONG_GROWTH","title":"Five-year revenue trend is negative","evidence":f"Revenue CAGR 5Y {_pct(growth)}","severity":"HIGH"})
    if roic is not None and roic<.08: avoid.append({"code":"LOW_ROIC","title":"Weak capital efficiency","evidence":f"ROIC {_pct(roic)}","severity":"MEDIUM"})
    if dilution is not None and dilution>.03: avoid.append({"code":"DILUTION","title":"Share count is expanding","evidence":f"Shares growth {_pct(dilution)}","severity":"MEDIUM"})
    if discount is not None and discount>.30: avoid.append({"code":"VALUATION_PREMIUM","title":"Above historical valuation","evidence":f"P/E vs 5Y median +{_pct(discount)}","severity":"MEDIUM"})
    if coverage<.60: avoid.insert(0,{"code":"LOW_COVERAGE","title":"Evidence coverage is insufficient for ranking","evidence":f"Weighted coverage {_pct(coverage)}","severity":"HIGH"})
    label="INSUFFICIENT_DATA" if final_score is None else "STRONG_RESEARCH_CANDIDATE" if final_score>=70 else "MIXED" if final_score>=45 else "WEAK_RESEARCH_CANDIDATE"
    simple_label={"INSUFFICIENT_DATA":"Not enough reliable data","STRONG_RESEARCH_CANDIDATE":"Strong fundamentals","MIXED":"Mixed strengths and risks","WEAK_RESEARCH_CANDIDATE":"Needs careful review"}[label]
    def item(title: str,value: float|None,good: bool|None,text: str) -> dict[str,Any]: return {"title":title,"value":value,"status":"GOOD" if good is True else "CAUTION" if good is False else "UNKNOWN","explanation":text}
    growth_text="Sales have grown consistently and strongly over the last five years." if growth is not None and growth>=.10 else "Long-term sales growth is modest or weak." if growth is not None else "There is not enough history to assess the sales trend."
    margin_text="The company keeps a strong share of sales as operating profit." if margin is not None and margin>=.20 else "Operating profitability is moderate or low." if margin is not None else "Profitability data is incomplete."
    cash_text="Core operations produce positive cash after business investment." if fcf is not None and fcf>0 else "The company is currently spending more cash than it generates." if fcf is not None else "Cash-flow data is incomplete."
    debt_text="Debt looks manageable relative to operating earnings." if leverage is not None and leverage<=2 else "Debt looks high relative to operating earnings." if leverage is not None else "There is not enough data to assess debt safety."
    valuation_text="The stock trades below its own historical valuation range." if discount is not None and discount<=-.15 else "The stock trades above its own historical valuation range." if discount is not None and discount>=.20 else "Valuation is close to its historical range." if discount is not None else "A historical valuation comparison is unavailable."
    simple_metrics=[item("Sales growth",growth,growth>=.10 if growth is not None else None,growth_text),item("Profitability",margin,margin>=.15 if margin is not None else None,margin_text),item("Cash generation",fcf,fcf>0 if fcf is not None else None,cash_text),item("Debt safety",leverage,leverage<=2 if leverage is not None else None,debt_text),item("Price vs history",discount,discount<=.10 if discount is not None else None,valuation_text)]
    headline=f"{simple_label}. " + (f"Morian score is {final_score:.0f}/100 with {_pct(coverage)} evidence coverage." if final_score is not None else f"Only {_pct(coverage)} of the required evidence is available, so no reliable final score is shown.")
    return {"label":label,"simple_label":simple_label,"plain_summary":headline,"simple_metrics":simple_metrics,"why_consider":choose[:6],"why_avoid":avoid[:6],"summary":f"{len(choose)} supporting and {len(avoid)} cautionary evidence points; weighted coverage {_pct(coverage)}.","disclaimer":"Research support only; not investment advice."}
