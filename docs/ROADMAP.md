# Delivery roadmap

All planned core delivery stages are complete:

1. **Automated universe and batch screening:** NASDAQ-100 source, daily cache, limited screening, and persistent jobs.
2. **Financial-statement quality:** discrete-quarter handling, TTM construction, Q4 derivation, taxonomy fallbacks, and evidence-quality reporting.
3. **Valuation and shareholder metrics:** historical valuation, dividend growth, buyback yield, and shareholder yield.
4. **SEC filing ingestion and query routing:** EDGAR filing retrieval, Qdrant metadata, and structured-versus-document routing.
5. **Operations:** retry/backoff, SEC rate limiting, disk cache, Docker Compose, readiness checks, and production headers.
6. **Product completion:** watchlists, charts, CSV export, plain-English decisions, custom scoring, and automated tests.

Values that require unavailable or unreliable data remain null rather than being invented. Financial-company scoring remains a future calibration area because industrial-company ROIC and leverage rules can be misleading for banks and insurers.
