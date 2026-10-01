"""FastAPI Application for Guarded Text-to-SQL Serving."""

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from src.t2s.serving.audit import default_audit_logger
from src.t2s.serving.auth import verify_api_key
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

service = Text2SQLService(backend_name="mock")


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["System"])
def readiness_check() -> Dict[str, str]:
    return {"status": "ready", "backend": "active"}


@app.get("/metrics", tags=["System"])
def metrics() -> Response:
    from src.t2s.serving.metrics import get_prometheus_metrics
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
def query_text2sql(
    req: QueryRequest,
    request: Request,
    api_key: str = Depends(verify_api_key),
) -> QueryResponse:
    default_rate_limiter.check_rate_limit(api_key or "anonymous")

    try:
        res = service.process_query(
            db_id=req.db_id,
            question=req.question,
            include_sample_rows=req.include_sample_rows,
            enable_consensus=req.enable_consensus,
            n_samples=req.n_samples,
        )

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {e}")


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
    metrics_path = Path("reports/metrics_finetuned_C.json")
    headline = {}
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            headline = json.load(f)

    return ModelInfoResponse(
        model_name="Qwen2.5-Coder-3B-Instruct",
        version="1.0-QLoRA",
        quantization="GGUF Q4_K_M",
        headline_metrics=headline,
    )
