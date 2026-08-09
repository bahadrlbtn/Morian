from __future__ import annotations

from datetime import date
from app.models import FinancialPeriod


REQUIRED = ["revenue","operating_income","net_income","operating_cash_flow","capex","assets","equity","cash","total_debt","shares_outstanding"]


def data_quality_report(annual: list[FinancialPeriod], quarterly: list[FinancialPeriod], ttm: FinancialPeriod | None) -> dict:
    latest = ttm or (annual[-1] if annual else quarterly[-1] if quarterly else None)
    available = [key for key in REQUIRED if latest and latest.values.get(key) is not None]
    missing = [key for key in REQUIRED if key not in available]
    latest_end = latest.period_end if latest else None
    age_days = (date.today() - latest_end).days if latest_end else None
    warnings=[]
    if not annual: warnings.append("No annual SEC periods available")
    if len(quarterly)<4: warnings.append("Fewer than four discrete quarters; TTM unavailable")
    if age_days is not None and age_days>550: warnings.append("Latest financial period is stale")
    if missing: warnings.append(f"Missing required metrics: {', '.join(missing)}")
    return {"coverage":round(len(available)/len(REQUIRED),4),"available":available,"missing":missing,"annual_periods":len(annual),"quarterly_periods":len(quarterly),"latest_period":str(latest_end) if latest_end else None,"age_days":age_days,"warnings":warnings,"status":"GOOD" if len(available)>=8 and not warnings[:3] else "PARTIAL" if available else "INSUFFICIENT"}
