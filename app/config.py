from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass(frozen=True)
class ScoreWeights:
    quality: float = 0.30
    growth: float = 0.25
    valuation: float = 0.20
    financial_health: float = 0.15
    momentum: float = 0.10

    def validate(self) -> None:
        if abs(sum(vars(self).values()) - 1.0) > 1e-9:
            raise ValueError("Composite score weights must sum to 1.0")


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path(os.getenv("DATABASE_PATH", "data/stocks.db"))
    sec_user_agent: str = os.getenv("SEC_USER_AGENT", "StockResearch contact@example.com")
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "21600"))
    http_timeout_seconds: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
    llm_provider: str = os.getenv("LLM_PROVIDER", "none").lower()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    n8n_base_url: str = os.getenv("N8N_BASE_URL", "http://localhost:5678")
    n8n_rag_webhook_path: str = os.getenv("N8N_RAG_WEBHOOK_PATH", "/webhook/stock-rag")
    n8n_ingest_webhook_path: str = os.getenv("N8N_INGEST_WEBHOOK_PATH", "/webhook/sec-filing-ingest")
    environment: str = os.getenv("APP_ENV", "development")
    allowed_hosts: tuple[str, ...] = tuple(x.strip() for x in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if x.strip())
    cors_origins: tuple[str, ...] = tuple(x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if x.strip())
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)


settings = Settings()
settings.score_weights.validate()
