"""Pydantic v2 schemas for the text-to-SQL serving API."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    db_id: str = Field(..., description="ID of the target database")
    question: str = Field(..., max_length=1000, description="Natural language question")
    include_sample_rows: bool = Field(default=False, description="Whether to include sample rows in schema prompt")
    enable_consensus: bool = Field(default=True, description="Enable Execution-Guided Self-Correction with Majority Voting")
    n_samples: int = Field(default=5, ge=1, le=10, description="Number of candidate queries to generate for voting")


class QueryResponse(BaseModel):
    request_id: str
    db_id: str
    question: str
    sql: str
    allowed: bool
    reasons: List[str] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    retried: bool = False
    consensus_score: str = Field(default="1/1", description="Consensus voting agreement ratio (e.g. 4/5)")
    timings_ms: Dict[str, float] = Field(default_factory=dict)
    model_version: str = "Qwen2.5-Coder-3B-QLoRA"


class ValidateRequest(BaseModel):
    sql: str = Field(..., description="Raw SQL query string to validate")
    db_id: Optional[str] = Field(default=None, description="Optional target database ID")


class ValidateResponse(BaseModel):
    allowed: bool
    reasons: List[str] = Field(default_factory=list)
    rewritten_sql: str = ""


class FeedbackRequest(BaseModel):
    request_id: str
    rating: int = Field(..., ge=-1, le=1, description="Rating: 1 for thumbs up, -1 for thumbs down")
    comment: Optional[str] = None


class DatabaseInfo(BaseModel):
    db_id: str
    table_count: int
    tables: List[str]


class ModelInfoResponse(BaseModel):
    model_name: str
    version: str
    quantization: str
    headline_metrics: Dict[str, Any]
