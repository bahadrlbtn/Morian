from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import time
import threading
from typing import Any
import re
import httpx

from app.models import FinancialPeriod


SEC_BASE = "https://data.sec.gov"
TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
TICKER_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
# Audited exceptions where an active exchange symbol is temporarily absent from SEC ticker files.
# Keep deliberately small and verify against SEC submissions before adding entries.
CIK_OVERRIDES = {"AEP":{"ticker":"AEP","title":"American Electric Power Company, Inc.","cik_str":4904,"source":"SEC CIK 0000004904"}}

CONCEPTS: dict[str, list[str]] = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "stock_based_compensation": ["ShareBasedCompensation"],
    "dividends_paid": ["PaymentsOfDividends"],
    "assets": ["Assets"],
    "current_assets": ["AssetsCurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "inventory": ["InventoryNet"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "equity": ["StockholdersEquity"],
    "total_debt_reported": ["LongTermDebtAndFinanceLeaseObligations", "LongTermDebtAndCapitalLeaseObligations"],
    "debt_current": ["LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtCurrent", "ShortTermBorrowings"],
    "debt_noncurrent": ["LongTermDebtAndFinanceLeaseObligationsNoncurrent", "LongTermDebtNoncurrent"],
    "shares_outstanding": ["EntityCommonStockSharesOutstanding", "WeightedAverageNumberOfDilutedSharesOutstanding"],
    "interest_expense": ["InterestExpenseNonOperating", "InterestExpense"],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    "income_before_tax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
}

FLOW_METRICS = {"revenue","gross_profit","operating_income","net_income","eps_diluted","operating_cash_flow","capex","stock_based_compensation","dividends_paid","interest_expense","income_tax","income_before_tax"}


class SecClient:
    _rate_lock = threading.Lock()
    _last_request = 0.0
    def __init__(self, user_agent: str, cache_dir: Path = Path("data/cache/sec"), ttl: int = 21600, timeout: float = 30):
        self.headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.timeout = timeout

    def _get_json(self, url: str, cache_key: str) -> Any:
        cache = self.cache_dir / f"{cache_key}.json"
        if cache.exists() and time.time() - cache.stat().st_mtime < self.ttl:
            return json.loads(cache.read_text(encoding="utf-8"))
        last_error=None
        for attempt in range(4):
            try:
                with self._rate_lock:
                    delay=max(0,.12-(time.monotonic()-self._last_request))
                    if delay: time.sleep(delay)
                    type(self)._last_request=time.monotonic()
                with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                    response = client.get(url)
                    if response.status_code in {429,500,502,503,504}: raise httpx.HTTPStatusError("retryable SEC response",request=response.request,response=response)
                    response.raise_for_status();data=response.json()
                break
            except (httpx.HTTPError,ValueError) as exc:
                last_error=exc
                if attempt==3: raise
                time.sleep(2**attempt)
        cache.write_text(json.dumps(data), encoding="utf-8")
        return data

    def ticker_map(self) -> dict[str, dict[str, Any]]:
        raw = self._get_json(TICKER_URL, "company_tickers")
        result={item["ticker"].upper(): item for item in raw.values()}
        exchange=self._get_json(TICKER_EXCHANGE_URL,"company_tickers_exchange")
        fields=exchange.get("fields",[])
        for values in exchange.get("data",[]):
            item=dict(zip(fields,values));ticker=str(item.get("ticker") or "").upper()
            if ticker and ticker not in result:
                result[ticker]={"ticker":ticker,"title":item.get("name"),"cik_str":item.get("cik"),"exchange":item.get("exchange")}
        for ticker,item in CIK_OVERRIDES.items(): result.setdefault(ticker,item)
        return result

    def company_facts(self, ticker: str) -> tuple[dict[str, Any], dict[str, Any]]:
        company = self.ticker_map().get(ticker.upper())
        if not company:
            raise ValueError(f"Unknown SEC ticker: {ticker}")
        cik = str(company["cik_str"]).zfill(10)
        facts = self._get_json(f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json", f"companyfacts_{cik}")
        return company, facts

    def filings(self, ticker: str, forms: tuple[str, ...] = ("10-K","10-Q"), limit: int = 20) -> list[dict[str, Any]]:
        company=self.ticker_map().get(ticker.upper())
        if not company: raise ValueError(f"Unknown SEC ticker: {ticker}")
        cik=str(company["cik_str"]).zfill(10)
        submission=self._get_json(f"{SEC_BASE}/submissions/CIK{cik}.json",f"submissions_{cik}")
        recent=submission.get("filings",{}).get("recent",{})
        rows=[]
        for i,form in enumerate(recent.get("form",[])):
            if form not in forms: continue
            accession=recent["accessionNumber"][i]
            primary=recent["primaryDocument"][i]
            accession_path=accession.replace("-","")
            url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{primary}"
            rows.append({"ticker":ticker.upper(),"company":company.get("title"),"cik":cik,"accession_number":accession,"filing_type":form,"filing_date":recent["filingDate"][i],"report_date":recent.get("reportDate",[None]*len(recent["form"]))[i],"primary_document":primary,"source_url":url})
            if len(rows)>=limit: break
        return rows

    def filing_text(self, source_url: str) -> str:
        with httpx.Client(headers=self.headers,timeout=self.timeout,follow_redirects=True) as client:
            response=client.get(source_url);response.raise_for_status()
        # n8n/document loaders can further clean it; removing tags here bounds transport size.
        text=re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>"," ",response.text,flags=re.I)
        text=re.sub(r"<[^>]+>"," ",text)
        return re.sub(r"\s+"," ",text).strip()

    @staticmethod
    def _concept_rows(facts: dict[str, Any], aliases: list[str]) -> list[dict[str, Any]]:
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        for alias in aliases:
            concept = us_gaap.get(alias)
            if concept:
                units = concept.get("units", {})
                for preferred in ("USD", "USD/shares", "shares"):
                    if preferred in units:
                        return units[preferred]
                if units:
                    return next(iter(units.values()))
        return []

    def normalize(self, ticker: str, facts: dict[str, Any], years: int = 10, quarters: int = 12) -> tuple[list[FinancialPeriod], list[FinancialPeriod]]:
        buckets: dict[tuple[str, str], dict[str, Any]] = {}
        for metric, aliases in CONCEPTS.items():
            for row in self._concept_rows(facts, aliases):
                form = row.get("form")
                if form not in {"10-K", "10-K/A", "10-Q", "10-Q/A"} or not row.get("end"):
                    continue
                duration = (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days if row.get("start") else None
                if form.startswith("10-K") and row.get("fp") == "FY":
                    # 10-K filings also repeat prior quarterly facts. Only full-year durations
                    # may populate annual flow metrics; instant balance facts have no start.
                    if metric in FLOW_METRICS and (duration is None or not 270 <= duration <= 400):
                        continue
                    period_type = "annual"
                elif form.startswith("10-Q"):
                    frame = str(row.get("frame") or "")
                    # SEC frames identify discrete quarters. Instant balance-sheet facts have no start.
                    if row.get("start") and not re.search(r"CY\d{4}Q[1-3]$", frame) and (duration is None or not 70 <= duration <= 120):
                        continue
                    period_type = "quarterly"
                else:
                    continue
                key = (period_type, row["end"])
                bucket = buckets.setdefault(key, {"values": {}, "row": row})
                old = bucket["row"]
                if row.get("filed", "") >= old.get("filed", ""):
                    bucket["row"] = row
                    bucket["values"][metric] = row.get("val")
                elif metric not in bucket["values"]:
                    bucket["values"][metric] = row.get("val")

        def build(kind: str, limit: int) -> list[FinancialPeriod]:
            selected = sorted((v for (k, _), v in buckets.items() if k == kind), key=lambda x: x["row"]["end"])[-limit:]
            periods = []
            for x in selected:
                values = x["values"]
                reported = values.pop("total_debt_reported", None)
                current, noncurrent = values.pop("debt_current", None), values.pop("debt_noncurrent", None)
                values["total_debt"] = reported if reported is not None else (
                    current + noncurrent if current is not None and noncurrent is not None else current if current is not None else noncurrent
                )
                if kind=="annual" and not any(values.get(metric) is not None for metric in FLOW_METRICS):
                    continue
                periods.append(FinancialPeriod(
                    ticker=ticker.upper(), period_end=date.fromisoformat(x["row"]["end"]), period_type=kind,
                    fiscal_year=date.fromisoformat(x["row"]["end"]).year, filing_date=date.fromisoformat(x["row"]["filed"]) if x["row"].get("filed") else None,
                    form=x["row"].get("form"), values=values
                ))
            return periods
        annual, quarterly = build("annual", years), build("quarterly", quarters + 4)
        # 10-K reports the full year rather than Q4; derive Q4 flow values when Q1-Q3 are available.
        for year in annual:
            qs = [q for q in quarterly if q.period_end < year.period_end and (year.period_end-q.period_end).days < 330][-3:]
            if len(qs) < 3: continue
            existing=next((q for q in quarterly if q.period_end==year.period_end),None)
            values = existing.values if existing else dict(year.values)
            for metric in FLOW_METRICS:
                annual_value = year.values.get(metric)
                q_values = [q.values.get(metric) for q in qs[-3:]]
                values[metric] = annual_value - sum(q_values) if annual_value is not None and all(v is not None for v in q_values) else None
            if existing:
                existing.form="10-K derived Q4";existing.source="SEC CompanyFacts; Q4 derived";existing.filing_date=year.filing_date
            else:
                quarterly.append(FinancialPeriod(ticker=ticker.upper(),period_end=year.period_end,period_type="quarterly",fiscal_year=year.fiscal_year,filing_date=year.filing_date,form="10-K derived Q4",source="SEC CompanyFacts; Q4 derived",values=values))
        quarterly = sorted(quarterly,key=lambda p:p.period_end)[-quarters:]
        return annual, quarterly

    def fetch_financials(self, ticker: str) -> tuple[str, list[FinancialPeriod], list[FinancialPeriod]]:
        company, facts = self.company_facts(ticker)
        annual, quarterly = self.normalize(ticker, facts)
        return company.get("title", ticker), annual, quarterly
