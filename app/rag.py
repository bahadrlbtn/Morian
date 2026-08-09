from __future__ import annotations

import re
from typing import Any
import httpx

from app.config import settings
from app.data.sec import SecClient
from app.data.database import Database


NUMERIC_TERMS={"score","margin","revenue","sales","eps","fcf","cash flow","debt","roic","roe","roa","p/e","valuation","growth","price","yield","cagr","compare","rank","screen"}


def classify_query(question: str) -> str:
    q=question.lower()
    return "structured" if any(term in q for term in NUMERIC_TERMS) or re.search(r"\d|%|oran|büyü|gelir|kâr|borç|puan|karşılaştır",q) else "filing_rag"


class RagService:
    def __init__(self, sec: SecClient, db: Database): self.sec,self.db=sec,db

    def ingest(self,ticker: str,limit: int=2) -> list[dict[str,Any]]:
        results=[]
        for filing in self.sec.filings(ticker,limit=limit):
            text=self.sec.filing_text(filing["source_url"])
            payload={"text":text,"metadata":{**filing,"fiscal_year":int(str(filing.get("report_date") or filing["filing_date"])[:4]),"source":filing["source_url"]}}
            url=settings.n8n_base_url.rstrip("/")+settings.n8n_ingest_webhook_path
            with httpx.Client(timeout=180) as client:
                response=client.post(url,json=payload);response.raise_for_status()
            collection=f"filings_{ticker.lower()}"
            self.db.save_filing(filing,collection)
            results.append({**filing,"qdrant_collection":collection,"characters":len(text)})
        return results

    def query(self,ticker: str,question: str) -> dict[str,Any]:
        url=settings.n8n_base_url.rstrip("/")+settings.n8n_rag_webhook_path
        with httpx.Client(timeout=120) as client:
            response=client.post(url,json={"ticker":ticker.upper(),"input":question,"collection":f"filings_{ticker.lower()}"});response.raise_for_status()
        try: answer=response.json()
        except ValueError: answer={"answer":response.text}
        return {"route":"filing_rag","ticker":ticker.upper(),"result":answer}
