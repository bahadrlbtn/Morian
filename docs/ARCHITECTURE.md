# Morian architecture

## System boundaries

Morian separates numeric research from document retrieval:

- FastAPI handles structured data, deterministic calculations, scoring, screening, jobs, watchlists, and exports.
- SQLite stores application data for a single-instance deployment.
- n8n orchestrates optional filing ingestion and AI commentary.
- Qdrant stores filing text for retrieval; it is never the source of numeric financial facts.
- An optional LLM receives calculated JSON or retrieved filing context and must not invent numbers.

## Data sources

- SEC CompanyFacts for annual and quarterly GAAP facts
- SEC submissions and archives for 10-K and 10-Q filings
- Yahoo Finance chart endpoint as a replaceable price-history fallback
- Nasdaq data for the NASDAQ-100 universe

SEC access uses an identified User-Agent, rate limiting, retry/backoff, timeouts, and disk caching.

## Calculation pipeline

1. Normalize annual and discrete quarterly SEC facts.
2. Build TTM values only when four valid quarters are available.
3. Fetch price history independently.
4. Calculate metrics with explicit null handling.
5. Score quality, growth, valuation, financial health, and momentum.
6. Produce a final score only when weighted evidence coverage reaches 60%.
7. Generate deterministic strengths and cautions from the same evidence.

Missing components are excluded and reduce coverage. They are never converted to zero.

## Application structure

- `app/data`: SEC, market, universe, and database adapters
- `app/finance`: calculations, metrics, scoring, quality, and decision support
- `app/services.py`: analysis orchestration
- `app/main.py`: HTTP API and operational middleware
- `app/static`: responsive single-page interface
- `n8n`: importable workflows without embedded credentials

## Deployment boundary

Default local and Docker configurations bind user-facing ports to localhost. A public deployment requires an authenticated HTTPS reverse proxy, exact host/CORS configuration, managed secrets, and private n8n/Qdrant services. SQLite is intended for one API instance; horizontal scaling requires a PostgreSQL-backed application data adapter.
