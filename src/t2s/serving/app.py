"""FastAPI Application for Guarded Text-to-SQL Serving."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.t2s.config import AppConfig
from src.t2s.serving.audit import default_audit_logger
from src.t2s.serving.auth import verify_api_key
from src.t2s.serving.metrics import (
    BLOCKED_COUNT,
    LATENCY_HISTOGRAM,
    QUEUE_DEPTH,
    REQUEST_COUNT,
    RETRY_COUNT,
    get_prometheus_metrics,
)
from src.t2s.serving.ratelimit import default_rate_limiter
from src.t2s.serving.schemas import (
    FeedbackRequest,
    ModelInfoResponse,
    QueryRequest,
    QueryResponse,
    ValidateRequest,
    ValidateResponse,
)
from src.t2s.serving.service import Text2SQLService

app_cfg = AppConfig.load()
serving_cfg = app_cfg.serving

app = FastAPI(
    title="Guarded Text-to-SQL API",
    description="Serving fine-tuned QLoRA text-to-SQL LLM behind SQL safety guardrails.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

backend_name = os.getenv("MODEL_BACKEND", "mock")
model_path = os.getenv("MODEL_PATH", "models/qlora_adapter")
service = Text2SQLService(backend_name=backend_name, model_path=model_path)

# Concurrency semaphore & bounded queue control
CONCURRENCY_SEMAPHORE = asyncio.Semaphore(serving_cfg.max_concurrent_generations)
CURRENT_QUEUE_WAITERS = 0


@app.middleware("http")
async def payload_size_limit_middleware(request: Request, call_next):
    # Enforce request payload size limit (default 64 KB)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > serving_cfg.max_request_bytes:
        return Response(
            content=json.dumps(
                {
                    "detail": f"Request payload exceeds max limit of {serving_cfg.max_request_bytes} bytes"
                }
            ),
            status_code=413,
            media_type="application/json",
        )
    return await call_next(request)


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["System"])
def readiness_check() -> Dict[str, Any]:
    is_ready = service is not None and getattr(service, "backend", None) is not None
    if not is_ready:
        raise HTTPException(
            status_code=503,
            detail="Model is still initializing / downloading weights. Please retry shortly.",
        )
    return {
        "status": "ready",
        "backend": backend_name,
        "model_loaded": True,
        "concurrency_limit": serving_cfg.max_concurrent_generations,
    }


@app.get("/metrics", tags=["System"])
def metrics(request: Request, api_key: str = Depends(verify_api_key)) -> Response:
    profile = os.getenv("APP_PROFILE", "dev").lower()
    if profile == "demo":
        # In demo profile, metrics are disabled to prevent leakage
        raise HTTPException(status_code=403, detail="Metrics endpoint disabled in demo profile")

    if serving_cfg.enable_metrics_auth:
        # Require admin or valid API key when auth enabled
        if not api_key:
            raise HTTPException(status_code=401, detail="Authentication required for /metrics")

    return Response(content=get_prometheus_metrics(), media_type="text/plain")


@app.get("/v1/databases", tags=["Databases"])
def list_databases() -> Dict[str, Any]:
    dbs = service.db_registry.list_databases()
    return {"total": len(dbs), "databases": dbs}


@app.get("/v1/databases/{db_id}/schema", tags=["Databases"])
def get_database_schema(db_id: str, include_samples: bool = False) -> Dict[str, Any]:
    try:
        ddl = service.db_registry.get_schema_ddl(db_id, include_sample_rows=include_samples)
        return {"db_id": db_id, "schema_ddl": ddl}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/v1/query", response_model=QueryResponse, tags=["Inference"])
async def query_text2sql(
    req: QueryRequest,
    request: Request,
    api_key: str = Depends(verify_api_key),
) -> QueryResponse:
    global CURRENT_QUEUE_WAITERS

    # 1. Global / per-user rate limit check (returns 429)
    default_rate_limiter.check_rate_limit(api_key or "anonymous")

    # 2. Check request queue depth limit (reject with 503 if overloaded)
    if CURRENT_QUEUE_WAITERS >= serving_cfg.max_queue_depth:
        REQUEST_COUNT.labels(endpoint="/v1/query", status="overloaded_503").inc()
        raise HTTPException(
            status_code=503,
            detail="Server is at peak capacity. Concurrency queue full, please retry shortly.",
        )

    CURRENT_QUEUE_WAITERS += 1
    QUEUE_DEPTH.set(CURRENT_QUEUE_WAITERS)

    try:
        # Acquire concurrency semaphore with timeout
        async with CONCURRENCY_SEMAPHORE:
            CURRENT_QUEUE_WAITERS -= 1
            QUEUE_DEPTH.set(CURRENT_QUEUE_WAITERS)

            # Enforce max execution timeout (default 30.0s)
            try:
                res = await asyncio.wait_for(
                    asyncio.to_thread(
                        service.process_query,
                        db_id=req.db_id,
                        question=req.question,
                        include_sample_rows=req.include_sample_rows,
                        enable_consensus=req.enable_consensus,
                        n_samples=min(req.n_samples, 5),
                    ),
                    timeout=serving_cfg.request_timeout_seconds,
                )
            except asyncio.TimeoutError:
                REQUEST_COUNT.labels(endpoint="/v1/query", status="timeout_504").inc()
                raise HTTPException(
                    status_code=504,
                    detail=f"Query generation timed out after {serving_cfg.request_timeout_seconds} seconds",
                )

        total_sec = res["timings_ms"].get("total_ms", 0.0) / 1000.0
        LATENCY_HISTOGRAM.labels(stage="total").observe(total_sec)

        status_label = "success" if res["allowed"] else "blocked"
        REQUEST_COUNT.labels(endpoint="/v1/query", status=status_label).inc()

        if not res["allowed"]:
            # Sanitized reason classification (no internal policy rule leaking)
            reason_cat = res["reasons"][0][:50] if res["reasons"] else "unknown"
            BLOCKED_COUNT.labels(reason_category=reason_cat).inc()

        if res.get("retried"):
            RETRY_COUNT.inc()

        default_audit_logger.log_query(
            request_id=res["request_id"],
            api_key=api_key or "anonymous",
            db_id=res["db_id"],
            question=res["question"],
            generated_sql=res["sql"],
            allowed=res["allowed"],
            reasons=res["reasons"],
            row_count=res["row_count"],
            retried=res["retried"],
            execution_time_ms=res["timings_ms"].get("total_ms", 0.0),
        )

        return QueryResponse(**res)
    except HTTPException:
        raise
    except Exception as e:
        REQUEST_COUNT.labels(endpoint="/v1/query", status="error").inc()
        raise HTTPException(status_code=500, detail=f"Query processing failed: {e}")
    finally:
        QUEUE_DEPTH.set(CURRENT_QUEUE_WAITERS)


@app.post("/v1/sql/validate", response_model=ValidateResponse, tags=["Safety"])
def validate_sql(req: ValidateRequest) -> ValidateResponse:
    verdict = service.validator.validate(req.sql)
    return ValidateResponse(
        allowed=verdict.allowed,
        reasons=verdict.reasons,
        rewritten_sql=verdict.rewritten_sql,
    )


@app.post("/v1/feedback", tags=["Feedback"])
def submit_feedback(req: FeedbackRequest) -> Dict[str, str]:
    default_audit_logger.log_feedback(
        request_id=req.request_id,
        rating=req.rating,
        comment=req.comment,
    )
    return {"status": "feedback_recorded"}


@app.get("/v1/model/info", response_model=ModelInfoResponse, tags=["Model Info"])
def get_model_info() -> ModelInfoResponse:
    metrics_path = Path("results/eval_spider_latest.json")
    headline = {}
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Expose Config D (or C) authoritative verified numbers
            headline = data.get("configs", {}).get("D", {})
    elif Path("reports/metrics_finetuned_C.json").exists():
        with open("reports/metrics_finetuned_C.json", "r", encoding="utf-8") as f:
            headline = json.load(f)

    return ModelInfoResponse(
        model_name="Qwen2.5-Coder-3B-Instruct",
        version="1.0-QLoRA",
        quantization="GGUF Q4_K_M",
        headline_metrics=headline,
    )


# Serve built React frontend if dist directory exists (single-container deployment)
frontend_dist = Path("frontend/dist")
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
