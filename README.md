# Morian · AI Equity Intelligence

Morian is an AI-assisted US equity research platform built around official SEC filings, deterministic financial metrics, explainable scoring, and optional n8n/Qdrant RAG workflows.

## Features

- Single-stock analysis, comparisons, and NASDAQ-100 screening
- Plain-English strengths, risks, and evidence coverage
- Deterministic quality, growth, valuation, financial-health, and momentum scores
- Custom per-company category and metric weights through Morian Score Lab
- Watchlists, historical charts, CSV export, and persistent screening jobs
- Optional OpenAI or local Ollama commentary
- SEC filing ingestion and retrieval workflows for n8n and Qdrant

## Local setup

Requirements: Python 3.11+ and internet access for SEC and market data.

```powershell
git clone https://github.com/bahadrlbtn/Morian.git
cd Morian
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Before making sustained SEC requests, replace the example `SEC_USER_AGENT` in `.env` with an application name and a valid contact email, as required by SEC fair-access guidance.

AI commentary is disabled by default. Keep `LLM_PROVIDER=none`, or configure either OpenAI or a local Ollama server.

## Docker Compose

Copy the environment template and set strong, unique values for the two required secrets:

```powershell
Copy-Item .env.example .env
# Edit POSTGRES_PASSWORD and N8N_ENCRYPTION_KEY in .env
docker compose config
docker compose up --build -d
```

For safety, the API, n8n, and Qdrant ports bind to `127.0.0.1` by default. Do not expose n8n or Qdrant directly to the internet. Use an authenticated HTTPS reverse proxy for any public deployment.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Documentation

- [API examples](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Deployment and security](docs/DEPLOYMENT.md)
- [Roadmap](docs/ROADMAP.md)
- [n8n workflow setup](n8n/README.md)

## Data and security

- Financial calculations are deterministic; the LLM does not create numeric facts.
- Missing values remain null and cannot artificially increase scores.
- Local `.env`, databases, caches, logs, and virtual environments are ignored by Git.
- The API is unauthenticated and intended for local use by default.
- This software provides research support, not investment advice.
