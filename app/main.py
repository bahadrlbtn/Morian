from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
import json
import uuid
import csv
import io
import time
import logging
import re
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.services import AnalysisService
from app.ai import generate_commentary
from app.rag import RagService, classify_query
from app.config import settings
from app.finance.scoring import DEFAULT_COMPONENT_WEIGHTS, calculate_quality_score, calculate_growth_score, calculate_valuation_score, calculate_health_score, calculate_momentum_score, calculate_stock_score
from app.finance.thesis import build_decision_support


app = FastAPI(title="Morian", version="2.0.0", description="AI-assisted, deterministic US equity research platform")
app.add_middleware(GZipMiddleware,minimum_size=1000)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=list(settings.allowed_hosts))
app.add_middleware(CORSMiddleware,allow_origins=list(settings.cors_origins),allow_credentials=False,allow_methods=["GET","POST","DELETE"],allow_headers=["Content-Type","X-Request-ID"])
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
service = AnalysisService()
rag = RagService(service.sec, service.db)
logger=logging.getLogger("morian")
_request_windows: dict[str, deque[float]]=defaultdict(deque)


@app.middleware("http")
async def production_headers(request: Request, call_next):
    request_id=request.headers.get("X-Request-ID") or str(uuid.uuid4())
    started=time.perf_counter()
    if request.url.path.startswith("/api/") and request.url.path not in {"/api/health","/api/ready"}:
        key=request.client.host if request.client else "unknown"
        now=time.monotonic();window=_request_windows[key]
        while window and window[0]<now-60:window.popleft()
        if len(window)>=180:
            return JSONResponse({"detail":"Rate limit exceeded"},status_code=429,headers={"Retry-After":"60","X-Request-ID":request_id})
        window.append(now)
    response=await call_next(request)
    response.headers["X-Request-ID"]=request_id
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"]="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'"
    response.headers["Server-Timing"]=f"app;dur={(time.perf_counter()-started)*1000:.1f}"
    logger.info("request method=%s path=%s status=%s request_id=%s",request.method,request.url.path,response.status_code,request_id)
    return response


class CompareRequest(BaseModel):
    tickers: list[str] = Field(min_length=1, max_length=110)
    @field_validator("tickers")
    @classmethod
    def clean(cls, value: list[str]) -> list[str]: return list(dict.fromkeys(x.strip().upper() for x in value if x.strip()))


class Filter(BaseModel):
    metric: str
    operator: Literal[">", ">=", "<", "<=", "=="]
    value: float


class ScreenRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list, max_length=110)
    universe: Literal["nasdaq100"] | None = None
    limit: int | None = Field(default=None, ge=1, le=110)
    strategy: Literal["quality", "growth", "value", "quality_growth", "garp", "cash_flow_compounders"] | None = None
    filters: list[Filter] = Field(default_factory=list)


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class WatchlistItem(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    @field_validator("ticker")
    @classmethod
    def valid_ticker(cls,value: str) -> str:
        value=value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,9}",value): raise ValueError("Invalid ticker format")
        return value


class QueryRequest(BaseModel):
    ticker: str = Field(min_length=1,max_length=10)
    question: str = Field(min_length=3,max_length=2000)
    @field_validator("ticker")
    @classmethod
    def valid_query_ticker(cls,value: str) -> str: return WatchlistItem.valid_ticker(value)


class RescoreRequest(BaseModel):
    profile: Literal["balanced","quality","growth","value","defensive","custom"] = "balanced"
    category_weights: dict[str,float] | None = None
    metric_weights: dict[str,dict[str,float]] = Field(default_factory=dict)
    @field_validator("category_weights")
    @classmethod
    def validate_categories(cls,value):
        if value is None:return value
        allowed={"quality","growth","valuation","financial_health","momentum"}
        if set(value)-allowed or any(v<0 for v in value.values()) or sum(value.values())<=0: raise ValueError("Invalid category weights")
        return value
    @field_validator("metric_weights")
    @classmethod
    def validate_metrics(cls,value):
        for category,weights in value.items():
            if category not in DEFAULT_COMPONENT_WEIGHTS or set(weights)-set(DEFAULT_COMPONENT_WEIGHTS[category]) or any(v<0 for v in weights.values()) or (weights and sum(weights.values())<=0): raise ValueError("Invalid metric weights")
        return value


PRESETS: dict[str, list[Filter]] = {
    "quality": [Filter(metric="roic",operator=">",value=.15),Filter(metric="free_cash_flow",operator=">",value=0)],
    "growth": [Filter(metric="revenue_cagr_5y",operator=">",value=.10),Filter(metric="eps_cagr_3y",operator=">",value=.10)],
    "value": [Filter(metric="fcf_yield",operator=">",value=.03),Filter(metric="earnings_yield",operator=">",value=.03)],
    "quality_growth": [Filter(metric="roic",operator=">",value=.15),Filter(metric="revenue_cagr_5y",operator=">",value=.10)],
    "garp": [Filter(metric="revenue_cagr_5y",operator=">",value=.08),Filter(metric="pe",operator="<",value=30)],
    "cash_flow_compounders": [Filter(metric="fcf_margin",operator=">",value=.10),Filter(metric="fcf_growth_yoy",operator=">",value=0)],
}

SCORE_PROFILES={
    "balanced":{"quality":30,"growth":25,"valuation":20,"financial_health":15,"momentum":10},
    "quality":{"quality":45,"growth":15,"valuation":15,"financial_health":20,"momentum":5},
    "growth":{"quality":20,"growth":45,"valuation":10,"financial_health":10,"momentum":15},
    "value":{"quality":20,"growth":10,"valuation":45,"financial_health":20,"momentum":5},
    "defensive":{"quality":35,"growth":10,"valuation":15,"financial_health":35,"momentum":5},
}


def _matches(metrics: dict[str, float | None], filters: list[Filter]) -> bool:
    operations = {">":lambda a,b:a>b,">=":lambda a,b:a>=b,"<":lambda a,b:a<b,"<=":lambda a,b:a<=b,"==":lambda a,b:a==b}
    return all(metrics.get(f.metric) is not None and operations[f.operator](metrics[f.metric], f.value) for f in filters)


@app.get("/")
def index() -> FileResponse: return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]: return {"status":"ok","service":"morian","version":"2.0.0","environment":settings.environment,"calculation_mode":"deterministic"}


@app.get("/api/ready")
def ready():
    try:
        with service.db.connect() as con: con.execute("SELECT 1").fetchone()
        return {"status":"ready","database":"ok","static_assets":static_dir.exists()}
    except Exception as exc: raise HTTPException(503,f"Readiness check failed: {exc}") from exc


@app.get("/api/config")
def public_config(): return {"name":"Morian","version":"2.0.0","ai_enabled":settings.llm_provider in {"openai","ollama"},"ai_provider":settings.llm_provider if settings.llm_provider in {"openai","ollama"} else None,"universes":["nasdaq100"]}


@app.get("/api/scoring/config")
def scoring_config(): return {"profiles":SCORE_PROFILES,"default_component_weights":DEFAULT_COMPONENT_WEIGHTS,"coverage_rules":{"category_minimum":.40,"final_minimum":.60}}


@app.get("/api/dashboard")
def dashboard():
    with service.db.connect() as con:
        counts={"companies":con.execute("SELECT COUNT(*) FROM companies").fetchone()[0],"statements":con.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0],"metrics":con.execute("SELECT COUNT(*) FROM financial_metrics").fetchone()[0],"watchlists":con.execute("SELECT COUNT(*) FROM watchlists").fetchone()[0]}
        leaders=[dict(row) for row in con.execute("SELECT ticker,ROUND(score,1) score,ROUND(coverage*100,0) coverage FROM scores WHERE score_type='composite' AND score IS NOT NULL ORDER BY score DESC LIMIT 5")]
        job=con.execute("SELECT status,progress,total,created_at,finished_at FROM jobs ORDER BY created_at DESC LIMIT 1").fetchone()
    return {"counts":counts,"leaders":leaders,"latest_job":dict(job) if job else None,"data_sources":{"fundamentals":"SEC CompanyFacts","prices":"Yahoo chart fallback","universe":"Nasdaq"}}


@app.get("/api/stocks/{ticker}")
def analyze(ticker: str):
    try: return service.analyze(ticker)
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc
    except Exception as exc: raise HTTPException(502, f"Upstream data error: {exc}") from exc


@app.post("/api/stocks/{ticker}/rescore")
def rescore(ticker: str,request: RescoreRequest):
    try:
        analysis=service.analyze(ticker);m=analysis.metrics
        metric=request.metric_weights
        scores={"quality":calculate_quality_score(m,metric.get("quality")),"growth":calculate_growth_score(m,metric.get("growth")),"valuation":calculate_valuation_score(m,metric.get("valuation")),"financial_health":calculate_health_score(m,metric.get("financial_health")),"momentum":calculate_momentum_score(m,metric.get("momentum"))}
        category=request.category_weights or SCORE_PROFILES.get(request.profile,SCORE_PROFILES["balanced"])
        final,coverage=calculate_stock_score(scores,category)
        support=build_decision_support(m,scores,final,coverage,analysis.red_flags)
        rescored=analysis.model_copy(update={"scores":scores,"final_score":final,"score_coverage":coverage,"decision_support":support})
        return {"analysis":rescored,"applied_profile":{"name":request.profile,"category_weights":category,"metric_weights":metric},"persisted":False}
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    except Exception as exc: raise HTTPException(502,f"Rescore error: {exc}") from exc


@app.post("/api/compare")
def compare(request: CompareRequest) -> dict[str, Any]:
    results, errors = [], []
    for ticker in request.tickers:
        try: results.append(service.analyze(ticker))
        except Exception as exc: errors.append({"ticker":ticker,"error":str(exc)})
    results.sort(key=lambda x: (x.final_score is not None,x.final_score or -1,x.score_coverage), reverse=True)
    return {"results":results,"errors":errors}


@app.post("/api/screen")
def screen(request: ScreenRequest) -> dict[str, Any]:
    tickers = request.tickers
    universe_meta = None
    if request.universe:
        universe_meta = service.universes.get(request.universe)
        tickers = [x["ticker"] for x in universe_meta["members"]]
    if request.limit: tickers = tickers[:request.limit]
    if not tickers: raise HTTPException(422, "tickers or universe is required")
    filters = PRESETS.get(request.strategy, []) + request.filters
    result = compare(CompareRequest(tickers=tickers))
    analyzed=result["results"]
    matches=[x for x in analyzed if _matches(x.metrics,filters)]
    match_details={x.ticker:{"passed":sum(1 for f in filters if x.metrics.get(f.metric) is not None and {">":lambda a,b:a>b,">=":lambda a,b:a>=b,"<":lambda a,b:a<b,"<=":lambda a,b:a<=b,"==":lambda a,b:a==b}[f.operator](x.metrics[f.metric],f.value)),"total":len(filters)} for x in analyzed}
    fallback=bool(filters and not matches)
    if fallback:
        matches=sorted(analyzed,key=lambda x:(match_details[x.ticker]["passed"],x.final_score or -1),reverse=True)[:20]
    result["results"] = matches
    result["filters"] = filters
    result["universe"] = universe_meta
    result["screening"]={"analyzed":len(analyzed),"strict_matches":0 if fallback else len(matches),"fallback":fallback,"message":"No company passed every rule. Showing the closest matches instead." if fallback else f"{len(matches)} companies passed all selected rules.","match_details":match_details}
    return result


def _run_screen_job(job_id: str, request: ScreenRequest) -> None:
    service.db.update_job(job_id,status="RUNNING")
    try:
        tickers=request.tickers
        universe_meta=None
        if request.universe:
            universe_meta=service.universes.get(request.universe)
            tickers=[x["ticker"] for x in universe_meta["members"]]
        if request.limit: tickers=tickers[:request.limit]
        filters=PRESETS.get(request.strategy,[])+request.filters
        analyzed=[];errors=[]
        for index,ticker in enumerate(tickers,1):
            try:
                analyzed.append(service.analyze(ticker))
            except Exception as exc: errors.append({"ticker":ticker,"error":str(exc)})
            service.db.update_job(job_id,progress=index)
        results=[x for x in analyzed if _matches(x.metrics,filters)]
        match_details={x.ticker:{"passed":sum(1 for f in filters if x.metrics.get(f.metric) is not None and {">":lambda a,b:a>b,">=":lambda a,b:a>=b,"<":lambda a,b:a<b,"<=":lambda a,b:a<=b,"==":lambda a,b:a==b}[f.operator](x.metrics[f.metric],f.value)),"total":len(filters)} for x in analyzed}
        fallback=bool(filters and not results)
        if fallback:results=sorted(analyzed,key=lambda x:(match_details[x.ticker]["passed"],x.final_score or -1),reverse=True)[:20]
        else:results.sort(key=lambda x:(x.final_score is not None,x.final_score or -1,x.score_coverage),reverse=True)
        screening={"analyzed":len(analyzed),"strict_matches":0 if fallback else len(results),"fallback":fallback,"message":"No company passed every rule. Showing the closest matches instead." if fallback else f"{len(results)} companies passed all selected rules.","match_details":match_details}
        payload=jsonable_encoder({"results":results,"errors":errors,"filters":filters,"universe":universe_meta,"screening":screening})
        service.db.update_job(job_id,status="COMPLETED",result=payload)
    except Exception as exc:
        service.db.update_job(job_id,status="FAILED",error=str(exc))


@app.post("/api/jobs/screen",status_code=202)
def create_screen_job(request: ScreenRequest, background_tasks: BackgroundTasks):
    tickers=request.tickers
    if request.universe:
        try: tickers=[x["ticker"] for x in service.universes.get(request.universe)["members"]]
        except Exception as exc: raise HTTPException(502,f"Universe source error: {exc}") from exc
    if request.limit:tickers=tickers[:request.limit]
    if not tickers:raise HTTPException(422,"tickers or universe is required")
    normalized=request.model_copy(update={"tickers":tickers,"universe":None})
    job_id=str(uuid.uuid4())
    job=service.db.create_job(job_id,"screen",jsonable_encoder(normalized),len(tickers))
    background_tasks.add_task(_run_screen_job,job_id,normalized)
    return job


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job=service.db.get_job(job_id)
    if not job:raise HTTPException(404,"Job not found")
    return job


@app.get("/api/export/comparison.csv")
def export_comparison(tickers: str):
    symbols=list(dict.fromkeys(x.strip().upper() for x in tickers.split(",") if x.strip()))
    if not symbols or len(symbols)>110:raise HTTPException(422,"Provide 1-110 comma-separated tickers")
    result=compare(CompareRequest(tickers=symbols))
    fields=["ticker","company_name","price","market_cap","revenue_cagr_5y","eps_cagr_5y","fcf_cagr_5y","roic","operating_margin","pe","ev_ebitda","fcf_yield","quality_score","growth_score","valuation_score","health_score","momentum_score","final_score","score_coverage","data_quality"]
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader()
    for a in result["results"]:
        writer.writerow({"ticker":a.ticker,"company_name":a.company_name,"price":a.price.price if a.price else None,"market_cap":a.metrics.get("market_cap"),"revenue_cagr_5y":a.metrics.get("revenue_cagr_5y"),"eps_cagr_5y":a.metrics.get("eps_cagr_5y"),"fcf_cagr_5y":a.metrics.get("fcf_cagr_5y"),"roic":a.metrics.get("roic"),"operating_margin":a.metrics.get("operating_margin"),"pe":a.metrics.get("pe"),"ev_ebitda":a.metrics.get("ev_ebitda"),"fcf_yield":a.metrics.get("fcf_yield"),"quality_score":a.scores["quality"].score,"growth_score":a.scores["growth"].score,"valuation_score":a.scores["valuation"].score,"health_score":a.scores["financial_health"].score,"momentum_score":a.scores["momentum"].score,"final_score":a.final_score,"score_coverage":a.score_coverage,"data_quality":a.data_quality.get("status")})
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=stock-comparison.csv"})


@app.get("/api/strategies")
def strategies(): return PRESETS


@app.get("/api/universes")
def universes(): return [{"key":"nasdaq100","name":"NASDAQ-100","source":"Nasdaq"}]


@app.get("/api/universes/{key}")
def universe(key: str, refresh: bool = False):
    try: return service.universes.get(key, refresh)
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc
    except Exception as exc: raise HTTPException(502, f"Universe source error: {exc}") from exc


@app.get("/api/filings/{ticker}")
def filings(ticker: str, limit: int = 20):
    try: return service.sec.filings(ticker,limit=min(max(limit,1),100))
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
    except Exception as exc: raise HTTPException(502,f"SEC filing error: {exc}") from exc


@app.post("/api/filings/{ticker}/ingest")
def ingest_filings(ticker: str, limit: int = 2):
    try: return {"indexed":rag.ingest(ticker,min(max(limit,1),10))}
    except Exception as exc: raise HTTPException(502,f"Filing ingestion error: {exc}") from exc


@app.post("/api/query")
def research_query(request: QueryRequest):
    route=classify_query(request.question)
    if route=="structured":
        try: return {"route":route,"ticker":request.ticker.upper(),"result":service.analyze(request.ticker)}
        except Exception as exc: raise HTTPException(502,f"Structured analysis error: {exc}") from exc
    try: return rag.query(request.ticker,request.question)
    except Exception as exc: raise HTTPException(502,f"RAG query error: {exc}") from exc


@app.post("/api/stocks/{ticker}/commentary")
def commentary(ticker: str):
    try:
        analysis = service.analyze(ticker)
        content, provider, model, digest = generate_commentary(analysis)
        required = {"bull_case","bear_case","key_strengths","key_risks","valuation","growth","financial_health","why_this_stock_ranks_here","disclaimer"}
        if not required.issubset(content): raise ValueError("LLM response does not satisfy the commentary contract")
        as_of = str(analysis.annual_financials[-1].period_end) if analysis.annual_financials else "latest"
        service.db.save_commentary(analysis.ticker,as_of,provider,model,digest,json.dumps(content))
        return {"ticker":analysis.ticker,"provider":provider,"model":model,"input_hash":digest,"commentary":content}
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
    except Exception as exc: raise HTTPException(502, f"Commentary error: {exc}") from exc


@app.get("/api/watchlists")
def list_watchlists(): return service.db.list_watchlists()


@app.post("/api/watchlists", status_code=201)
def create_watchlist(request: WatchlistCreate):
    try: return service.db.create_watchlist(request.name)
    except Exception as exc: raise HTTPException(409, "A watchlist with this name already exists") from exc


@app.get("/api/watchlists/{watchlist_id}")
def get_watchlist(watchlist_id: int):
    result = service.db.watchlist(watchlist_id)
    if not result: raise HTTPException(404, "Watchlist not found")
    return result


@app.post("/api/watchlists/{watchlist_id}/items", status_code=204)
def add_watchlist_item(watchlist_id: int, request: WatchlistItem):
    try: service.db.add_watchlist_item(watchlist_id, request.ticker.strip().upper())
    except KeyError as exc: raise HTTPException(404, "Watchlist not found") from exc


@app.delete("/api/watchlists/{watchlist_id}/items/{ticker}", status_code=204)
def remove_watchlist_item(watchlist_id: int, ticker: str):
    if not service.db.remove_watchlist_item(watchlist_id, ticker): raise HTTPException(404, "Watchlist item not found")
