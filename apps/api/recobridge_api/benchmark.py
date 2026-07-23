"""Benchmark a versioned serving bundle through the FastAPI request path."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from .app import create_app
from .config import Settings
from .engine import RecommendationEngine
from .store import MemoryEventStore


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def benchmark(
    bundle_path: Path,
    *,
    requests: int = 1000,
    warmup_requests: int = 50,
    threshold_ms: float = 200.0,
) -> dict[str, Any]:
    bundle_path = bundle_path.resolve()
    engine = RecommendationEngine(str(bundle_path))
    if not engine.ready:
        raise RuntimeError(engine.error or "Serving bundle failed to load")
    users = sorted(engine.user_affinities)[:100]
    if not users:
        raise RuntimeError("Serving bundle has no known users for the performance profile")

    token = "release-benchmark-token"
    app = create_app(
        settings=Settings(api_token=token, database_url="memory://"),
        engine=engine,
        store=MemoryEventStore(),
    )
    payloads = [
        {
            "user_id": user,
            "session_id": f"benchmark-{index}",
            "context": {"page_type": "home", "device_type": "desktop"},
            "top_k": 12,
            "strategy": "hybrid",
        }
        for index, user in enumerate(users)
    ]
    headers = {"Authorization": f"Bearer {token}"}
    latencies: list[float] = []
    logging.disable(logging.INFO)
    try:
        with TestClient(app) as client:
            for index in range(warmup_requests):
                response = client.post(
                    "/v1/recommendations", json=payloads[index % len(payloads)], headers=headers
                )
                response.raise_for_status()
            for index in range(requests):
                started = time.perf_counter()
                response = client.post(
                    "/v1/recommendations", json=payloads[index % len(payloads)], headers=headers
                )
                elapsed_ms = (time.perf_counter() - started) * 1000
                response.raise_for_status()
                latencies.append(elapsed_ms)
    finally:
        logging.disable(logging.NOTSET)

    p50 = _percentile(latencies, 0.50)
    p95 = _percentile(latencies, 0.95)
    p99 = _percentile(latencies, 0.99)
    return {
        "schema_version": "recobridge-api-performance-v1",
        "profile": {
            "transport": "FastAPI TestClient ASGI request path",
            "requests": requests,
            "warmup_requests": warmup_requests,
            "known_users": len(users),
            "top_k": 12,
            "strategy_requested": "hybrid",
            "database": "memory (recommendation path is database-independent)",
        },
        "bundle_path": str(bundle_path),
        "bundle_sha256": _sha256(bundle_path),
        "model_version": engine.model_version,
        "feature_version": engine.feature_version,
        "strategy_version": engine.strategy_version,
        "latency_ms": {
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "maximum": float(max(latencies)),
        },
        "gate": {
            "threshold_p95_ms": threshold_ms,
            "passed": p95 <= threshold_ms,
        },
        "created_at": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--warmup-requests", type=int, default=50)
    parser.add_argument("--threshold-ms", type=float, default=200.0)
    args = parser.parse_args(argv)
    if args.requests < 100:
        parser.error("--requests must be at least 100")
    report = benchmark(
        args.bundle_path,
        requests=args.requests,
        warmup_requests=args.warmup_requests,
        threshold_ms=args.threshold_ms,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
