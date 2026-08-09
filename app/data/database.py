from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from typing import Iterator

from app.models import StockAnalysis


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS companies (ticker TEXT PRIMARY KEY, name TEXT, cik TEXT, sector TEXT, industry TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS financial_statements (id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, period_end TEXT NOT NULL, period_type TEXT NOT NULL, fiscal_year INTEGER, filing_date TEXT, form TEXT, source TEXT NOT NULL, values_json TEXT NOT NULL, UNIQUE(ticker,period_end,period_type));
CREATE TABLE IF NOT EXISTS financial_metrics (ticker TEXT NOT NULL, as_of TEXT NOT NULL, metric TEXT NOT NULL, value REAL, source TEXT, period TEXT, filing_date TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(ticker,as_of,metric));
CREATE TABLE IF NOT EXISTS prices (ticker TEXT NOT NULL, as_of TEXT NOT NULL, price REAL, market_cap REAL, source TEXT, payload_json TEXT NOT NULL, PRIMARY KEY(ticker,as_of));
CREATE TABLE IF NOT EXISTS scores (ticker TEXT NOT NULL, as_of TEXT NOT NULL, score_type TEXT NOT NULL, score REAL, coverage REAL NOT NULL, components_json TEXT NOT NULL, PRIMARY KEY(ticker,as_of,score_type));
CREATE TABLE IF NOT EXISTS analysis (ticker TEXT NOT NULL, as_of TEXT NOT NULL, provider TEXT, model TEXT, input_hash TEXT, content TEXT, PRIMARY KEY(ticker,as_of));
CREATE TABLE IF NOT EXISTS filings (accession_number TEXT PRIMARY KEY, ticker TEXT NOT NULL, filing_type TEXT, filing_date TEXT, fiscal_year INTEGER, source_url TEXT, qdrant_collection TEXT, indexed_at TEXT);
CREATE TABLE IF NOT EXISTS watchlists (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS watchlist_items (watchlist_id INTEGER NOT NULL, ticker TEXT NOT NULL, added_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(watchlist_id,ticker), FOREIGN KEY(watchlist_id) REFERENCES watchlists(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, job_type TEXT NOT NULL, status TEXT NOT NULL, progress INTEGER DEFAULT 0, total INTEGER DEFAULT 0, request_json TEXT NOT NULL, result_json TEXT, error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, started_at TEXT, finished_at TEXT);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con: con.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        finally: con.close()

    def save_analysis(self, a: StockAnalysis) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO companies(ticker,name) VALUES(?,?) ON CONFLICT(ticker) DO UPDATE SET name=excluded.name,updated_at=CURRENT_TIMESTAMP", (a.ticker,a.company_name))
            # Normalization rules can evolve; replace the ticker snapshot so stale periods
            # cannot survive an upsert and contaminate CAGR/TTM calculations.
            con.execute("DELETE FROM financial_statements WHERE ticker=?",(a.ticker,))
            con.execute("DELETE FROM financial_metrics WHERE ticker=?",(a.ticker,))
            con.execute("DELETE FROM scores WHERE ticker=?",(a.ticker,))
            periods=a.annual_financials+a.quarterly_financials+([a.ttm_financials] if a.ttm_financials else [])
            for p in periods:
                con.execute("INSERT INTO financial_statements(ticker,period_end,period_type,fiscal_year,filing_date,form,source,values_json) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(ticker,period_end,period_type) DO UPDATE SET filing_date=excluded.filing_date,values_json=excluded.values_json", (p.ticker,str(p.period_end),p.period_type,p.fiscal_year,str(p.filing_date) if p.filing_date else None,p.form,p.source,json.dumps(p.values)))
            as_of = str(a.annual_financials[-1].period_end) if a.annual_financials else a.price.as_of.date().isoformat() if a.price else "unknown"
            for metric,value in a.metrics.items():
                con.execute("INSERT OR REPLACE INTO financial_metrics(ticker,as_of,metric,value,source,period,filing_date) VALUES(?,?,?,?,?,?,?)",(a.ticker,as_of,metric,value,"calculated","latest",str(a.annual_financials[-1].filing_date) if a.annual_financials and a.annual_financials[-1].filing_date else None))
            for name, score in a.scores.items():
                con.execute("INSERT OR REPLACE INTO scores(ticker,as_of,score_type,score,coverage,components_json) VALUES(?,?,?,?,?,?)",(a.ticker,as_of,name,score.score,score.coverage,json.dumps(score.components)))
            con.execute("INSERT OR REPLACE INTO scores(ticker,as_of,score_type,score,coverage,components_json) VALUES(?,?,?,?,?,?)",(a.ticker,as_of,"composite",a.final_score,a.score_coverage,json.dumps({name:score.score for name,score in a.scores.items()})))

    def list_watchlists(self) -> list[dict]:
        with self.connect() as con:
            rows = con.execute("SELECT w.id,w.name,COUNT(i.ticker) item_count FROM watchlists w LEFT JOIN watchlist_items i ON i.watchlist_id=w.id GROUP BY w.id ORDER BY w.name").fetchall()
            return [dict(row) for row in rows]

    def create_watchlist(self, name: str) -> dict:
        with self.connect() as con:
            cursor = con.execute("INSERT INTO watchlists(name) VALUES(?)", (name.strip(),))
            return {"id": cursor.lastrowid, "name": name.strip(), "item_count": 0}

    def watchlist(self, watchlist_id: int) -> dict | None:
        with self.connect() as con:
            row = con.execute("SELECT id,name FROM watchlists WHERE id=?", (watchlist_id,)).fetchone()
            if not row: return None
            tickers = [x[0] for x in con.execute("SELECT ticker FROM watchlist_items WHERE watchlist_id=? ORDER BY added_at DESC", (watchlist_id,))]
            return {"id": row["id"], "name": row["name"], "tickers": tickers}

    def add_watchlist_item(self, watchlist_id: int, ticker: str) -> None:
        with self.connect() as con:
            if not con.execute("SELECT 1 FROM watchlists WHERE id=?", (watchlist_id,)).fetchone(): raise KeyError(watchlist_id)
            con.execute("INSERT OR IGNORE INTO watchlist_items(watchlist_id,ticker) VALUES(?,?)", (watchlist_id,ticker.upper()))

    def remove_watchlist_item(self, watchlist_id: int, ticker: str) -> bool:
        with self.connect() as con:
            cursor = con.execute("DELETE FROM watchlist_items WHERE watchlist_id=? AND ticker=?", (watchlist_id,ticker.upper()))
            return cursor.rowcount > 0

    def save_commentary(self, ticker: str, as_of: str, provider: str, model: str, input_hash: str, content: str) -> None:
        with self.connect() as con:
            con.execute("INSERT OR REPLACE INTO analysis(ticker,as_of,provider,model,input_hash,content) VALUES(?,?,?,?,?,?)",(ticker,as_of,provider,model,input_hash,content))

    def save_filing(self, filing: dict, collection: str | None = None) -> None:
        with self.connect() as con:
            con.execute("INSERT OR REPLACE INTO filings(accession_number,ticker,filing_type,filing_date,fiscal_year,source_url,qdrant_collection,indexed_at) VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",(filing["accession_number"],filing["ticker"],filing["filing_type"],filing["filing_date"],int(str(filing.get("report_date") or filing["filing_date"])[:4]),filing["source_url"],collection))

    def create_job(self, job_id: str, job_type: str, request: dict, total: int) -> dict:
        with self.connect() as con:
            con.execute("INSERT INTO jobs(id,job_type,status,total,request_json) VALUES(?,?,'QUEUED',?,?)",(job_id,job_type,total,json.dumps(request)))
        return self.get_job(job_id)

    def update_job(self, job_id: str, *, status: str | None = None, progress: int | None = None, result: dict | None = None, error: str | None = None) -> None:
        fields=[];values=[]
        if status is not None:
            fields.append("status=?");values.append(status)
            if status=="RUNNING": fields.append("started_at=CURRENT_TIMESTAMP")
            if status in {"COMPLETED","FAILED"}: fields.append("finished_at=CURRENT_TIMESTAMP")
        if progress is not None: fields.append("progress=?");values.append(progress)
        if result is not None: fields.append("result_json=?");values.append(json.dumps(result))
        if error is not None: fields.append("error=?");values.append(error)
        if not fields:return
        with self.connect() as con: con.execute(f"UPDATE jobs SET {','.join(fields)} WHERE id=?",(*values,job_id))

    def get_job(self, job_id: str) -> dict | None:
        with self.connect() as con:
            row=con.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
            if not row:return None
            result=dict(row)
            for key in ("request_json","result_json"):
                result[key[:-5]]=json.loads(result.pop(key)) if result[key] else None
            return result
