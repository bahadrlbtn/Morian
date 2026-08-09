# n8n workflow setup

1. Import the five JSON files with **Import from File**.
2. Set `STOCK_API_URL` (normally `http://api:8000` in Docker).
3. Configure your own Google Drive, Qdrant, embedding, and chat credentials in n8n. No credentials are included in this repository.
4. Supply `file_id`, `ticker`, `company`, `filing_type`, `filing_date`, `fiscal_year`, and `source` to filing-ingestion workflows.
5. Run a manual test before activating any webhook or schedule.

`sec-filing-auto-ingestion.json` and `filing-rag-query.json` provide the webhook paths used by the backend filing-ingestion and query routes. Numeric questions go to the deterministic backend; filing questions can use the retrieval workflow.
