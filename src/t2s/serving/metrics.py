"""Prometheus metrics wrapper for text-to-SQL service monitoring."""

from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "t2s_requests_total",
    "Total text-to-SQL API requests",
    ["endpoint", "status"],
)

LATENCY_HISTOGRAM = Histogram(
    "t2s_request_duration_seconds",
    "Request latency in seconds",
    ["stage"],
)

BLOCKED_COUNT = Counter(
    "t2s_blocked_queries_total",
    "Total queries blocked by safety validator",
    ["reason_category"],
)

RETRY_COUNT = Counter(
    "t2s_execution_retries_total",
    "Total execution-guided retries triggered",
)


def get_prometheus_metrics() -> bytes:
    return generate_latest()
