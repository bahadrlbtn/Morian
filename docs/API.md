# API examples

Interactive OpenAPI documentation is available at `/docs`.

## Analysis and comparison

`GET /api/stocks/MSFT`

```json
POST /api/compare
{"tickers":["GOOGL","META","MSFT","AMZN"]}
```

## Screening

```json
POST /api/screen
{"tickers":["AAPL","MSFT","GOOGL"],"strategy":"quality_growth","filters":[]}
```

```json
POST /api/screen
{"universe":"nasdaq100","strategy":"quality_growth","limit":20}
```

The first large-universe run can take time because SEC requests are rate-limited and cached.

```json
POST /api/screen
{
  "tickers":["AAPL","MSFT","GOOGL"],
  "filters":[
    {"metric":"revenue_cagr_5y","operator":">","value":0.10},
    {"metric":"roic","operator":">","value":0.15},
    {"metric":"free_cash_flow","operator":">","value":0}
  ]
}
```

Persistent jobs use `POST /api/jobs/screen` and `GET /api/jobs/{job_id}`.

## Score Lab

`GET /api/scoring/config` returns profiles and metric weights.

```json
POST /api/stocks/MSFT/rescore
{
  "profile":"custom",
  "category_weights":{"quality":35,"growth":30,"valuation":15,"financial_health":15,"momentum":5}
}
```

Custom scores are session-only and do not overwrite the canonical stored score.

## Other endpoints

- `POST /api/stocks/MSFT/commentary`: optional grounded AI commentary
- `POST /api/watchlists`: create a watchlist
- `POST /api/watchlists/{id}/items`: add a ticker
- `POST /api/query`: route numeric or filing questions
- `GET /api/export/comparison.csv?tickers=MSFT,AAPL,GOOGL`: export CSV
