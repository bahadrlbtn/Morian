from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any
import httpx


NASDAQ_100_URL = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"


class UniverseClient:
    """Fetches official index membership and keeps a daily local snapshot."""

    def __init__(self, cache_dir: Path = Path("data/cache/universes"), ttl: int = 86400, timeout: float = 30):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.timeout = timeout

    @staticmethod
    def parse_nasdaq100(payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.get("data") or {}
        rows = ((data.get("data") or {}).get("rows") or [])
        members = []
        for row in rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol: continue
            raw_cap = str(row.get("marketCap") or "").replace(",", "").replace("$", "")
            try: market_cap = float(raw_cap)
            except ValueError: market_cap = None
            members.append({"ticker":symbol,"company_name":str(row.get("companyName") or "").replace("\n"," ").strip(),"market_cap":market_cap})
        if not members: raise ValueError("Nasdaq response did not contain constituents")
        return {"key":"nasdaq100","name":"NASDAQ-100","as_of":data.get("date"),"source":NASDAQ_100_URL,"members":members}

    def nasdaq100(self, force_refresh: bool = False) -> dict[str, Any]:
        cache = self.cache_dir / "nasdaq100.json"
        if not force_refresh and cache.exists() and time.time() - cache.stat().st_mtime < self.ttl:
            return json.loads(cache.read_text(encoding="utf-8"))
        headers={"User-Agent":"Mozilla/5.0 (compatible; Morian/2.0)","Accept":"application/json, text/plain, */*","Origin":"https://www.nasdaq.com","Referer":"https://www.nasdaq.com/"}
        with httpx.Client(timeout=self.timeout,headers=headers,follow_redirects=True) as client:
            response=client.get(NASDAQ_100_URL);response.raise_for_status()
        result=self.parse_nasdaq100(response.json())
        result["fetched_at"]=datetime.now(timezone.utc).isoformat()
        cache.write_text(json.dumps(result),encoding="utf-8")
        return result

    def get(self, key: str, force_refresh: bool = False) -> dict[str, Any]:
        if key.lower() == "nasdaq100": return self.nasdaq100(force_refresh)
        raise ValueError(f"Unknown universe: {key}")
