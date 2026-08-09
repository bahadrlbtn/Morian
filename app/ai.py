from __future__ import annotations

import hashlib
import json
from typing import Any
import httpx

from app.config import settings
from app.models import StockAnalysis


SYSTEM_PROMPT = """You are an equity research writing assistant. Use ONLY the supplied calculated JSON.
Never calculate, estimate, infer, invent, update, or correct a financial number. If a value is null, say it is unavailable.
Return valid JSON with exactly these string fields: bull_case, bear_case, key_strengths, key_risks, valuation, growth,
financial_health, why_this_stock_ranks_here, disclaimer. Do not give buy/sell advice. The disclaimer must state that this is research, not investment advice."""


def _payload(analysis: StockAnalysis) -> dict[str, Any]:
    return {
        "ticker": analysis.ticker, "company_name": analysis.company_name,
        "metrics": analysis.metrics, "scores": {k:v.model_dump() for k,v in analysis.scores.items()},
        "final_score": analysis.final_score, "score_coverage": analysis.score_coverage,
        "red_flags": [x.model_dump() for x in analysis.red_flags], "provenance": analysis.provenance,
    }


def generate_commentary(analysis: StockAnalysis) -> tuple[dict[str, str], str, str, str]:
    data = _payload(analysis)
    serialized = json.dumps(data, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    if settings.llm_provider == "openai":
        if not settings.openai_api_key: raise RuntimeError("OPENAI_API_KEY is not configured")
        with httpx.Client(timeout=60) as client:
            response = client.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {settings.openai_api_key}"},json={"model":settings.openai_model,"input":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":serialized}],"text":{"format":{"type":"json_object"}}})
            response.raise_for_status(); raw=response.json(); text=raw.get("output_text")
            if not text:
                text="".join(c.get("text","") for o in raw.get("output",[]) for c in o.get("content",[]) if c.get("type")=="output_text")
        return json.loads(text), "openai", settings.openai_model, digest
    if settings.llm_provider == "ollama":
        with httpx.Client(timeout=120) as client:
            response=client.post(f"{settings.ollama_base_url.rstrip('/')}/api/chat",json={"model":settings.ollama_model,"stream":False,"format":"json","messages":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":serialized}]})
            response.raise_for_status(); text=response.json()["message"]["content"]
        return json.loads(text), "ollama", settings.ollama_model, digest
    raise RuntimeError("LLM_PROVIDER is 'none'; configure openai or ollama")
