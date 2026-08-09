# Deployment and security

## Local development

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Set `SEC_USER_AGENT` to an application name and a valid contact email before sustained SEC access.

## Docker Compose

```powershell
Copy-Item .env.example .env
# Set strong POSTGRES_PASSWORD and N8N_ENCRYPTION_KEY values.
docker compose config
docker compose up --build -d
```

Compose fails closed when either required secret is empty. The API (`8000`), n8n (`5678`), and Qdrant (`6333`) bind only to localhost.

## Public deployment

- Keep n8n and Qdrant private.
- Put the API behind an authenticated TLS reverse proxy.
- Set `APP_ENV=production`.
- Set `ALLOWED_HOSTS` to the public domain.
- Set `CORS_ORIGINS` to the exact HTTPS frontend origin.
- Store secrets in a managed secret store, not in source control.
- Back up the `stock_data`, `postgres_data`, `qdrant_data`, and `n8n_data` volumes.
- SQLite is suitable for a single API instance; use a PostgreSQL adapter before scaling the API horizontally.

## Acceptance checklist

1. `GET /api/health` returns `ok`.
2. `GET /api/ready` reports a healthy database and static assets.
3. A comparison of two to four tickers completes.
4. A NASDAQ-100 job reports progress and completes.
5. Stock details show evidence coverage and charts.
6. CSV export downloads successfully.
7. `LLM_PROVIDER=none` leaves deterministic analysis fully functional.
