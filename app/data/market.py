from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
import httpx

from app.finance.calculations import safe_divide
from app.models import PriceSnapshot


class YahooChartClient:
    """Unauthenticated chart endpoint fallback; no scraping and no hard dependency on yfinance."""
    def __init__(self, cache_dir: Path = Path("data/cache/market"), ttl: int = 3600, timeout: float = 30):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.timeout = timeout

    def fetch(self, ticker: str, shares: float | None = None, debt: float | None = None, cash: float | None = None) -> PriceSnapshot:
        cache = self.cache_dir / f"{ticker.upper()}.json"
        if cache.exists() and time.time() - cache.stat().st_mtime < self.ttl:
            raw = json.loads(cache.read_text(encoding="utf-8"))
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}?range=5y&interval=1d&events=div%2Csplits"
            with httpx.Client(timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"}) as client:
                response = client.get(url)
                response.raise_for_status()
                raw = response.json()
            cache.write_text(json.dumps(raw), encoding="utf-8")
        result = raw["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        closes = result.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
        series = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
        if not series:
            return PriceSnapshot(ticker=ticker.upper())
        price = series[-1][1]
        def ret(days: int) -> float | None:
            if len(series) <= days: return None
            return safe_divide(price, series[-days-1][1]) - 1
        def avg(days: int) -> float | None:
            vals = [x[1] for x in series[-days:]]
            return sum(vals) / len(vals) if len(vals) >= min(days, 20) else None
        ma50, ma200 = avg(50), avg(200)
        high = max(x[1] for x in series[-252:])
        # Weekly samples keep the response compact while preserving chart/valuation history.
        history=[{"date":datetime.fromtimestamp(t,tz=timezone.utc).date().isoformat(),"close":c} for i,(t,c) in enumerate(series) if i%5==0 or i==len(series)-1]
        market_cap = price * shares if shares is not None else None
        ev = market_cap + debt - cash if market_cap is not None and debt is not None and cash is not None else None
        return PriceSnapshot(
            ticker=ticker.upper(), price=price, market_cap=market_cap, enterprise_value=ev,
            returns={"return_1m":ret(21), "return_3m":ret(63), "return_6m":ret(126), "return_12m":ret(252)},
            moving_averages={"ma50":ma50,"ma200":ma200,"price_vs_ma50":safe_divide(price, ma50) - 1 if ma50 else None,"price_vs_ma200":safe_divide(price, ma200) - 1 if ma200 else None},
            distance_from_52w_high=safe_divide(price, high) - 1,
            as_of=datetime.fromtimestamp(series[-1][0], tz=timezone.utc),
            history=history,
        )
