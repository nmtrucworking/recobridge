"""Promote a verified serving bundle or its governed baseline fallback."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_bundle(candidate_dir: Path) -> None:
    checksum_path = candidate_dir / "checksum.sha256"
    if not checksum_path.is_file():
        raise FileNotFoundError(f"Missing checksum manifest: {checksum_path}")
    failures: list[str] = []
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        artifact = candidate_dir / name
        if not artifact.is_file() or _sha256(artifact) != expected:
            failures.append(name)
    if failures:
        raise ValueError(f"Bundle checksum verification failed: {', '.join(failures)}")


def promote(candidate_dir: Path, performance_report_path: Path) -> dict[str, Any]:
    candidate_dir = candidate_dir.resolve()
    performance_report_path = performance_report_path.resolve()
    output_root = candidate_dir.parent
    if output_root not in candidate_dir.parents:
        raise ValueError("Candidate directory must remain under its model output root")
    _verify_bundle(candidate_dir)

    manifest = _read_json(candidate_dir / "manifest.json")
    metrics = _read_json(candidate_dir / "metrics.json")
    decision = _read_json(candidate_dir / "release_decision.json")
    serving_bundle_path = candidate_dir / "serving_bundle.json"
    serving_bundle = _read_json(serving_bundle_path)
    performance = _read_json(performance_report_path)
    if manifest.get("profile") != "release":
        raise ValueError("Only a release-profile artifact can be promoted")
    if performance.get("bundle_sha256") != _sha256(serving_bundle_path):
        raise ValueError("Performance report does not match the serving bundle checksum")
    if not performance.get("gate", {}).get("passed"):
        raise ValueError("API p95 performance gate did not pass")
    if performance.get("model_version") != serving_bundle.get("model_version"):
        raise ValueError("Performance report model version does not match the serving bundle")

    ranker_promoted = bool(metrics.get("promotion_eligible"))
    if ranker_promoted:
        raise ValueError(
            "This serving bundle contains the baseline fallback, not online XGBoost inference"
        )
    failed_gates = [
        key for key, value in metrics.get("promotion_gate", {}).items() if value is False
    ]
    if not failed_gates:
        raise ValueError("Baseline fallback requires a documented failed ranker gate")

    production_path = output_root / "production.json"
    previous_path = output_root / "production.previous.json"
    if production_path.exists():
        shutil.copy2(production_path, previous_path)
    alias = {
        "schema_version": "recobridge-production-alias-v1",
        "status": "production",
        "mode": "baseline_fallback",
        "model_version": serving_bundle["model_version"],
        "candidate_model_version": manifest["model_version"],
        "path": f"{candidate_dir.name}/serving_bundle.json",
        "bundle_sha256": _sha256(serving_bundle_path),
        "default_strategy": decision["default_strategy"],
        "ranker_promoted": False,
        "ranker_failed_gates": failed_gates,
        "api_performance": {
            "report": str(performance_report_path),
            "p95_ms": performance["latency_ms"]["p95"],
            "threshold_ms": performance["gate"]["threshold_p95_ms"],
        },
        "rollback_alias": previous_path.name if previous_path.exists() else None,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    _write_json(production_path, alias)
    return alias


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("performance_report", type=Path)
    args = parser.parse_args(argv)
    alias = promote(args.candidate_dir, args.performance_report)
    print(json.dumps(alias, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
