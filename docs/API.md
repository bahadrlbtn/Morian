# API örnekleri

Tek hisse: `GET /api/stocks/MSFT`

Karşılaştırma:

```json
POST /api/compare
{"tickers":["GOOGL","META","MSFT","AMZN"]}
```

Hazır strateji:

```json
POST /api/screen
{"tickers":["AAPL","MSFT","GOOGL"],"strategy":"quality_growth","filters":[]}
```

NASDAQ-100 otomatik tarama (ilk çalıştırma SEC istekleri nedeniyle uzun sürebilir):

```json
POST /api/screen
{"universe":"nasdaq100","strategy":"quality_growth","limit":20}
```

Özel filtre:

```json
POST /api/screen
{
  "tickers":["AAPL","MSFT","GOOGL"],
  "filters":[
    {"metric":"market_cap","operator":">","value":10000000000},
    {"metric":"revenue_cagr_5y","operator":">","value":0.10},
    {"metric":"roic","operator":">","value":0.15},
    {"metric":"free_cash_flow","operator":">","value":0},
    {"metric":"debt_equity","operator":"<","value":1},
    {"metric":"fcf_yield","operator":">","value":0.03}
  ]
}
```

AI yorum (yalnızca hesaplanmış JSON üzerinden): `POST /api/stocks/MSFT/commentary`

Watchlist:

```json
POST /api/watchlists
{"name":"Core Compounders"}

POST /api/watchlists/1/items
{"ticker":"MSFT"}
```

Kalıcı evren taraması:

```json
POST /api/jobs/screen
{"universe":"nasdaq100","strategy":"garp"}

GET /api/jobs/{job_id}
```

Birleşik soru router'ı:

```json
POST /api/query
{"ticker":"MSFT","question":"Son 10-K raporundaki temel riskler neler?"}
```

CSV: `GET /api/export/comparison.csv?tickers=MSFT,AAPL,GOOGL`

## Morian Score Lab

Varsayılan profiller ve alt metrik ağırlıkları: `GET /api/scoring/config`

Şirketi özel ağırlıklarla yeniden puanlama:

```json
POST /api/stocks/MSFT/rescore
{
  "profile":"custom",
  "category_weights":{
    "quality":35,
    "growth":30,
    "valuation":15,
    "financial_health":15,
    "momentum":5
  },
  "metric_weights":{
    "quality":{"roic":35,"margins":20,"free_cash_flow":20,"revenue_consistency":10,"earnings_consistency":5,"balance_sheet":5,"share_dilution":5},
    "valuation":{"fcf_yield":40,"historical_discount":25,"earnings_yield":15,"ev_ebitda":10,"pe":5,"growth_quality":5}
  }
}
```

Özel skor oturumluk döner ve kanonik veritabanı skorunu değiştirmez. Yanıtta `decision_support.why_consider` ve `decision_support.why_avoid`, yalnızca hesaplanmış metrik ve risk kurallarından türetilmiş kanıtları içerir.
