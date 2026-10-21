"""FastAPI Application for Guarded Text-to-SQL Serving."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
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

cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


backend_name = os.getenv("MODEL_BACKEND", "mock")
model_path = os.getenv("MODEL_PATH", "models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf")

# DB_DIR: point the server at a directory of .sqlite files (local use)
# e.g. DB_DIR=/home/user/my_databases uvicorn src.t2s.serving.app:app ...
db_dir = os.getenv("DB_DIR", "data/raw/spider/database")

# HF Space support: download GGUF from HF Hub if specified via env
hf_repo = os.getenv("HF_REPO_ID")
gguf_file = os.getenv("GGUF_FILENAME")
if hf_repo and gguf_file and not Path(model_path).exists():
    try:
        from huggingface_hub import hf_hub_download

        print(f"Downloading {gguf_file} from {hf_repo}...")
        downloaded = hf_hub_download(repo_id=hf_repo, filename=gguf_file)
        model_path = downloaded
    except Exception as e:
        print(f"Warning: Failed to download GGUF from Hugging Face Hub: {e}")

service = Text2SQLService(backend_name=backend_name, model_path=model_path, db_base_dir=db_dir)
print(f"[startup] backend={backend_name}  db_dir={db_dir}")

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
@app.get("/healthz", tags=["System"])
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


@app.get("/v1/databases/{db_id}/info", tags=["Databases"])
def get_database_info(db_id: str) -> Dict[str, Any]:
    """Return detailed info for a database: tables + row count per table + size."""
    import sqlite3 as _sqlite3
    db_path = service.db_registry.get_db_path(db_id)
    if not db_path:
        raise HTTPException(status_code=404, detail=f"Database '{db_id}' not found.")
    try:
        conn = _sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables_raw = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]
        tables = []
        for tbl in tables_raw:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{tbl}"')  # noqa: S608
                row_count = cursor.fetchone()[0]
            except Exception:
                row_count = -1
            tables.append({"name": tbl, "row_count": row_count})
        conn.close()
        size_bytes = db_path.stat().st_size
        return {
            "db_id": db_id,
            "table_count": len(tables),
            "tables": tables,
            "size_bytes": size_bytes,
            "size_human": f"{size_bytes / 1024:.1f} KB" if size_bytes < 1_048_576 else f"{size_bytes / 1_048_576:.1f} MB",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/databases/{db_id}/schema", tags=["Databases"])
def get_database_schema(db_id: str, include_samples: bool = False) -> Dict[str, Any]:
    try:
        ddl = service.db_registry.get_schema_ddl(db_id, include_sample_rows=include_samples)
        return {"db_id": db_id, "schema_ddl": ddl}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# Upload dir: db/uploads/ is persistent across restarts (unlike /tmp).
# Falls back to /tmp on read-only filesystems (e.g. some HF Spaces).
try:
    _UPLOAD_DIR = Path("db/uploads")
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (_UPLOAD_DIR / ".gitkeep").touch(exist_ok=True)
except OSError:
    _UPLOAD_DIR = Path("/tmp/t2s_uploads")
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Pre-register so previously-uploaded DBs appear immediately on restart
service.db_registry.register_upload_dir(str(_UPLOAD_DIR))


@app.post("/v1/databases/upload", tags=["Databases"])
async def upload_database(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Accept a user-provided .sqlite file and register it for querying.

    Constraints enforced:
    - File must end in .sqlite or .db
    - File size capped at 50 MB
    - db_id sanitised to alphanumeric + underscore only
    - Runs in the same read-only sandbox as built-in databases
    """
    MAX_BYTES = 50 * 1024 * 1024  # 50 MB
    fname = file.filename or ""
    if not (fname.endswith(".sqlite") or fname.endswith(".db")):
        raise HTTPException(status_code=400, detail="Only .sqlite or .db files are accepted.")

    # Sanitise db_id from filename
    import re
    stem = Path(fname).stem
    db_id_base = re.sub(r"[^a-zA-Z0-9_]", "_", stem)[:60] or "uploaded_db"

    # Auto-rename if db_id already exists (avoid overwriting)
    db_id = db_id_base
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    counter = 1
    while (_UPLOAD_DIR / f"{db_id}.sqlite").exists():
        db_id = f"{db_id_base}_v{counter}"
        counter += 1
        if counter > 99:
            raise HTTPException(status_code=409, detail=f"Too many versions of '{db_id_base}'. Delete old ones first.")

    dest = (_UPLOAD_DIR / f"{db_id}.sqlite").resolve()

    # Validate SQLite magic bytes before writing
    _SQLITE_MAGIC = b"SQLite format 3\x00"

    # Stream & size-check
    total = 0
    first_chunk = None
    with open(dest, "wb") as f:
        while chunk := await file.read(65536):
            if first_chunk is None:
                first_chunk = chunk
            total += len(chunk)
            if total > MAX_BYTES:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")
            f.write(chunk)

    # Verify it's a real SQLite file
    if first_chunk is None or not first_chunk[:16].startswith(_SQLITE_MAGIC[:15]):
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="File is not a valid SQLite3 database.")

    # Register upload dir in registry so the db is immediately queryable
    service.db_registry.register_upload_dir(str(_UPLOAD_DIR))

    info = service.db_registry.get_db_info_from_path(str(dest), db_id)
    return {
        "db_id": db_id,
        "table_count": info.get("table_count", 0),
        "tables": info.get("tables", []),
        "size_bytes": total,
        "renamed": db_id != db_id_base,  # tell client if name was auto-renamed
    }


@app.delete("/v1/databases/{db_id}", tags=["Databases"])
def delete_database(db_id: str) -> Dict[str, Any]:
    """Delete a user-uploaded database. Built-in Spider databases cannot be deleted."""
    import re
    if not re.match(r"^[a-zA-Z0-9_]+$", db_id):
        raise HTTPException(status_code=400, detail="Invalid db_id format.")

    # Only allow deleting from the uploads dir — never spider databases
    candidate = (_UPLOAD_DIR / f"{db_id}.sqlite").resolve()
    if not candidate.exists() or _UPLOAD_DIR.resolve() not in candidate.parents:
        raise HTTPException(
            status_code=404,
            detail=f"'{db_id}' not found in uploads or is a built-in database (cannot delete).",
        )

    candidate.unlink()
    return {"deleted": db_id, "status": "ok"}


@app.post("/v1/query", response_model=QueryResponse, tags=["Inference"])
async def query_text2sql(
    req: QueryRequest,
    request: Request,
    api_key: str = Depends(verify_api_key),
) -> QueryResponse:
    global CURRENT_QUEUE_WAITERS

    # 1. Global / per-user rate limit check (returns 429)
    # Note on Proxies: If behind a reverse proxy without trusted proxy headers, client IP may be proxy IP.
    # We prioritize API key, then leftmost X-Forwarded-For IP, falling back to direct client host or 'global'.
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    rate_limit_key = api_key or client_ip or "global"
    default_rate_limiter.check_rate_limit(rate_limit_key)

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
