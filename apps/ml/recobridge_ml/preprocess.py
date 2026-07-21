"""Out-of-core preprocessing for the Synerise Parquet dataset.

The module deliberately uses DuckDB scans instead of loading Parquet files into
Pandas.  It creates a deterministic buyer cohort, a canonical event table, a
clean catalog, time splits, and machine-readable data-quality evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb


SEED = 42
SESSION_GAP_MINUTES = 30
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
PROFILE_SIZES = {"smoke": 1_000, "release": 20_000}
EVENT_FILES = {
    "ADD_TO_CART": ("add_to_cart.parquet", "sku"),
    "PAGE_VISIT": ("page_visit.parquet", "url"),
    "BUY": ("product_buy.parquet", "sku"),
    "REMOVE_FROM_CART": ("remove_from_cart.parquet", "sku"),
    "SEARCH": ("search_query.parquet", "query"),
}
EXPECTED_COLUMNS = {
    "add_to_cart.parquet": {"client_id": "BIGINT", "timestamp": "VARCHAR", "sku": "BIGINT"},
    "page_visit.parquet": {"client_id": "BIGINT", "timestamp": "VARCHAR", "url": "BIGINT"},
    "product_buy.parquet": {"client_id": "BIGINT", "timestamp": "VARCHAR", "sku": "BIGINT"},
    "remove_from_cart.parquet": {"client_id": "BIGINT", "timestamp": "VARCHAR", "sku": "BIGINT"},
    "search_query.parquet": {"client_id": "BIGINT", "timestamp": "VARCHAR", "query": "VARCHAR"},
    "product_properties.parquet": {
        "sku": "BIGINT",
        "category": "BIGINT",
        "price": "BIGINT",
        "name": "VARCHAR",
    },
}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    output_dir: Path
    profile: str
    seed: int = SEED
    session_gap_minutes: int = SESSION_GAP_MINUTES

    @property
    def cohort_size(self) -> int:
        return PROFILE_SIZES[self.profile]


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        # SQL TIMESTAMP has no tzinfo. The Synerise contract declares it UTC;
        # interpreting it in the workstation timezone would shift reports.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Path):
        return str(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, default=_json_value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_commit(repo_root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _connect(output_dir: Path) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute("SET TimeZone = 'UTC'")
    connection.execute("SET preserve_insertion_order = false")
    connection.execute(f"SET threads = {max(1, min(8, os.cpu_count() or 1))}")
    temp_dir = output_dir / ".duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    connection.execute(f"SET temp_directory = '{_sql_path(temp_dir)}'")
    return connection


def _validate_inputs(connection: duckdb.DuckDBPyConnection, data_dir: Path) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"schema_version": "1.0.0", "files": {}}
    errors: list[str] = []

    for filename, expected in EXPECTED_COLUMNS.items():
        path = data_dir / filename
        if not path.is_file():
            errors.append(f"Missing source file: {path}")
            continue
        rows = connection.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{_sql_path(path)}')"
        ).fetchall()
        actual = {row[0]: row[1] for row in rows}
        mismatches = {
            column: {"expected": dtype, "actual": actual.get(column)}
            for column, dtype in expected.items()
            if actual.get(column) != dtype
        }
        if mismatches:
            errors.append(f"Schema mismatch in {filename}: {mismatches}")
        snapshot["files"][filename] = {
            "bytes": path.stat().st_size,
            "columns": [{"name": row[0], "physical_type": row[1], "nullable": row[2] == "YES"} for row in rows],
            "schema_valid": not mismatches,
        }

    if errors:
        raise ValueError("\n".join(errors))
    return snapshot


def _source_profile(
    connection: duckdb.DuckDBPyConnection, data_dir: Path, snapshot: dict[str, Any]
) -> dict[str, Any]:
    profile: dict[str, Any] = {}
    for event_type, (filename, entity_column) in EVENT_FILES.items():
        path = data_dir / filename
        entity_null = f"{entity_column} IS NULL"
        result = connection.execute(
            f"""
            SELECT
                count(*) AS row_count,
                count(*) FILTER (WHERE client_id IS NULL) AS null_client_id,
                count(*) FILTER (WHERE timestamp IS NULL) AS null_timestamp,
                count(*) FILTER (WHERE {entity_null}) AS null_entity,
                count(*) FILTER (
                    WHERE timestamp IS NOT NULL
                      AND try_strptime(timestamp, '{TIMESTAMP_FORMAT}') IS NULL
                ) AS invalid_timestamp,
                min(try_strptime(timestamp, '{TIMESTAMP_FORMAT}')) AS min_timestamp,
                max(try_strptime(timestamp, '{TIMESTAMP_FORMAT}')) AS max_timestamp
            FROM read_parquet('{_sql_path(path)}')
            """
        ).fetchone()
        fields = [column[0] for column in connection.description]
        values = dict(zip(fields, result, strict=True))
        profile[filename] = values
        snapshot["files"][filename].update(
            row_count=values["row_count"],
            min_timestamp=values["min_timestamp"],
            max_timestamp=values["max_timestamp"],
        )

        if event_type == "SEARCH":
            vector = connection.execute(
                f"""
                SELECT min(vector_length), max(vector_length), mode(vector_length),
                       count(*) FILTER (WHERE vector_length = 0)
                FROM (
                    SELECT len(regexp_extract_all(query, '[0-9]+')) AS vector_length
                    FROM read_parquet('{_sql_path(path)}')
                    WHERE query IS NOT NULL
                )
                """
            ).fetchone()
            values["vector_length"] = {
                "min": vector[0], "max": vector[1], "mode": vector[2], "empty_rows": vector[3]
            }
            if vector[0] != vector[1] or vector[3] != 0:
                raise ValueError(f"Vector dimension drift detected in {filename}: {values['vector_length']}")

    product_path = data_dir / "product_properties.parquet"
    product = connection.execute(
        f"""
        SELECT count(*) AS row_count,
               count(*) FILTER (WHERE sku IS NULL) AS null_sku,
               count(*) FILTER (WHERE category IS NULL) AS null_category,
               count(*) FILTER (WHERE price IS NULL) AS null_price,
               count(*) FILTER (WHERE name IS NULL) AS null_name,
               count(*) - count(DISTINCT sku) AS duplicate_sku
        FROM read_parquet('{_sql_path(product_path)}')
        """
    ).fetchone()
    product_fields = [column[0] for column in connection.description]
    product_values = dict(zip(product_fields, product, strict=True))
    vector = connection.execute(
        f"""
        SELECT min(vector_length), max(vector_length), mode(vector_length),
               count(*) FILTER (WHERE vector_length = 0)
        FROM (
            SELECT len(regexp_extract_all(name, '[0-9]+')) AS vector_length
            FROM read_parquet('{_sql_path(product_path)}')
            WHERE name IS NOT NULL
        )
        """
    ).fetchone()
    product_values["vector_length"] = {
        "min": vector[0], "max": vector[1], "mode": vector[2], "empty_rows": vector[3]
    }
    if vector[0] != vector[1] or vector[3] != 0:
        raise ValueError(
            "Vector dimension drift detected in product_properties.parquet: "
            f"{product_values['vector_length']}"
        )
    profile["product_properties.parquet"] = product_values
    snapshot["files"]["product_properties.parquet"]["row_count"] = product_values["row_count"]
    return profile


def _create_cohort(connection: duckdb.DuckDBPyConnection, settings: Settings) -> None:
    buy_path = settings.data_dir / "product_buy.parquet"
    connection.execute(
        f"""
        CREATE TEMP TABLE cohort AS
        SELECT client_id
        FROM (
            SELECT DISTINCT client_id
            FROM read_parquet('{_sql_path(buy_path)}')
            WHERE client_id IS NOT NULL
        )
        ORDER BY md5(CAST(client_id AS VARCHAR) || ':{settings.seed}'), client_id
        LIMIT {settings.cohort_size}
        """
    )
    actual = connection.execute("SELECT count(*) FROM cohort").fetchone()[0]
    if actual != settings.cohort_size:
        raise ValueError(f"Requested {settings.cohort_size} buyers, found only {actual}")
    connection.execute(
        f"COPY (SELECT * FROM cohort ORDER BY client_id) TO '{_sql_path(settings.output_dir / 'cohort.parquet')}' "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def _create_catalog(connection: duckdb.DuckDBPyConnection, settings: Settings) -> dict[str, int]:
    source = settings.data_dir / "product_properties.parquet"
    expected_dim = connection.execute(
        f"""
        SELECT mode(len(regexp_extract_all(name, '[0-9]+')))
        FROM read_parquet('{_sql_path(source)}') WHERE name IS NOT NULL
        """
    ).fetchone()[0]
    connection.execute(
        f"""
        CREATE TEMP TABLE catalog AS
        SELECT sku AS product_id,
               category AS category_id,
               price AS price_bucket,
               CAST(regexp_extract_all(name, '[0-9]+') AS UTINYINT[]) AS embedding_codes
        FROM read_parquet('{_sql_path(source)}')
        WHERE sku IS NOT NULL AND category IS NOT NULL AND price IS NOT NULL
          AND len(regexp_extract_all(name, '[0-9]+')) = {int(expected_dim)}
        QUALIFY row_number() OVER (PARTITION BY sku ORDER BY category, price, name) = 1
        """
    )
    connection.execute(
        f"COPY (SELECT * FROM catalog ORDER BY product_id) TO '{_sql_path(settings.output_dir / 'catalog.parquet')}' "
        "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
    valid = connection.execute("SELECT count(*) FROM catalog").fetchone()[0]
    raw = connection.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(source)}')").fetchone()[0]
    return {"raw_rows": raw, "valid_unique_rows": valid, "embedding_dimension": expected_dim}


def _event_select(data_dir: Path, event_type: str, filename: str, entity_column: str) -> str:
    path = _sql_path(data_dir / filename)
    timestamp = f"try_strptime(timestamp, '{TIMESTAMP_FORMAT}')"
    if event_type in {"ADD_TO_CART", "BUY", "REMOVE_FROM_CART"}:
        product_id, url_id, vector = "sku", "NULL::BIGINT", "NULL::UTINYINT[]"
        payload = "CAST(sku AS VARCHAR)"
    elif event_type == "PAGE_VISIT":
        product_id, url_id, vector = "NULL::BIGINT", "url", "NULL::UTINYINT[]"
        payload = "CAST(url AS VARCHAR)"
    else:
        product_id, url_id = "NULL::BIGINT", "NULL::BIGINT"
        vector = "CAST(regexp_extract_all(query, '[0-9]+') AS UTINYINT[])"
        payload = "query"
    return f"""
        SELECT md5('{event_type}|' || CAST(client_id AS VARCHAR) || '|' || timestamp || '|' || {payload}) AS event_id,
               {timestamp} AT TIME ZONE 'UTC' AS event_time,
               '{event_type}' AS event_type,
               CAST(client_id AS VARCHAR) AS user_id,
               {product_id} AS product_id,
               {url_id} AS url_id,
               {vector} AS search_vector,
               'synerise_recsys_2025' AS source_dataset,
               '{filename}' AS source_partition
        FROM read_parquet('{path}') AS events
        SEMI JOIN cohort USING (client_id)
        WHERE client_id IS NOT NULL AND timestamp IS NOT NULL
          AND {entity_column} IS NOT NULL AND {timestamp} IS NOT NULL
    """


def _quarantine_select(data_dir: Path, event_type: str, filename: str, entity_column: str) -> str:
    path = _sql_path(data_dir / filename)
    timestamp = f"try_strptime(timestamp, '{TIMESTAMP_FORMAT}')"
    return f"""
        SELECT '{event_type}' AS event_type, client_id, timestamp AS timestamp_raw,
               CAST({entity_column} AS VARCHAR) AS entity_raw,
               CASE
                   WHEN client_id IS NULL THEN 'null_client_id'
                   WHEN timestamp IS NULL THEN 'null_timestamp'
                   WHEN {entity_column} IS NULL THEN 'null_{entity_column}'
                   WHEN {timestamp} IS NULL THEN 'invalid_timestamp'
               END AS reason,
               '{filename}' AS source_partition
        FROM read_parquet('{path}') AS events
        SEMI JOIN cohort USING (client_id)
        WHERE client_id IS NULL OR timestamp IS NULL OR {entity_column} IS NULL OR {timestamp} IS NULL
    """


def _create_events(
    connection: duckdb.DuckDBPyConnection,
    settings: Settings,
    ingested_at: datetime,
) -> dict[str, Any]:
    unions = [
        _event_select(settings.data_dir, event_type, filename, entity)
        for event_type, (filename, entity) in EVENT_FILES.items()
    ]
    connection.execute("CREATE TEMP TABLE canonical_raw AS " + " UNION ALL ".join(unions))
    connection.execute(
        """
        CREATE TEMP TABLE canonical_dedup AS
        SELECT * FROM canonical_raw
        QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY source_partition) = 1
        """
    )

    quarantine_unions = [
        _quarantine_select(settings.data_dir, event_type, filename, entity)
        for event_type, (filename, entity) in EVENT_FILES.items()
    ]
    connection.execute("CREATE TEMP TABLE quarantine AS " + " UNION ALL ".join(quarantine_unions))
    connection.execute(
        f"COPY (SELECT * FROM quarantine) TO '{_sql_path(settings.output_dir / 'quarantined_events.parquet')}' "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )

    horizon = connection.execute("SELECT min(event_time), max(event_time) FROM canonical_dedup").fetchone()
    if horizon[0] is None or horizon[1] is None:
        raise ValueError("The selected cohort has no valid events")
    connection.execute(
        f"""
        CREATE TEMP TABLE canonical_events AS
        WITH previous_event AS (
            SELECT *, lag(event_time) OVER (
                PARTITION BY user_id ORDER BY event_time, event_id
            ) AS previous_event_time
            FROM canonical_dedup
        ), boundaries AS (
            SELECT *, CASE
                WHEN previous_event_time IS NULL
                  OR event_time - previous_event_time > INTERVAL '{settings.session_gap_minutes} minutes'
                THEN 1 ELSE 0 END AS starts_session
            FROM previous_event
        ), numbered AS (
            SELECT *, sum(starts_session) OVER (
                PARTITION BY user_id ORDER BY event_time, event_id ROWS UNBOUNDED PRECEDING
            ) AS session_number
            FROM boundaries
        )
        SELECT n.event_id, n.event_time, n.event_type, n.user_id,
               n.product_id, n.url_id, n.search_vector,
               md5(n.user_id || '|' || CAST(n.session_number AS VARCHAR)) AS session_id,
               c.category_id, c.price_bucket,
               CASE WHEN n.product_id IS NULL THEN NULL ELSE c.product_id IS NOT NULL END AS is_catalog_match,
               CASE
                   WHEN n.event_time >= TIMESTAMPTZ '{horizon[1].isoformat()}' - INTERVAL '14 days' THEN 'test'
                   WHEN n.event_time >= TIMESTAMPTZ '{horizon[1].isoformat()}' - INTERVAL '28 days' THEN 'validation'
                   ELSE 'train'
               END AS split,
               n.source_dataset, n.source_partition,
               TIMESTAMPTZ '{ingested_at.isoformat()}' AS ingested_at
        FROM numbered n
        LEFT JOIN catalog c USING (product_id)
        """
    )
    destination = settings.output_dir / "canonical_events.parquet"
    connection.execute(
        f"COPY (SELECT * FROM canonical_events ORDER BY user_id, event_time, event_id) "
        f"TO '{_sql_path(destination)}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )

    raw_rows = connection.execute("SELECT count(*) FROM canonical_raw").fetchone()[0]
    dedup_rows = connection.execute("SELECT count(*) FROM canonical_dedup").fetchone()[0]
    quarantine_rows = connection.execute("SELECT count(*) FROM quarantine").fetchone()[0]
    unmatched = connection.execute(
        "SELECT count(*) FROM canonical_events WHERE product_id IS NOT NULL AND NOT is_catalog_match"
    ).fetchone()[0]
    by_type = dict(connection.execute(
        "SELECT event_type, count(*) FROM canonical_events GROUP BY event_type ORDER BY event_type"
    ).fetchall())
    by_split = dict(connection.execute(
        "SELECT split, count(*) FROM canonical_events GROUP BY split ORDER BY split"
    ).fetchall())
    return {
        "valid_rows_before_dedup": raw_rows,
        "canonical_rows": dedup_rows,
        "duplicates_removed": raw_rows - dedup_rows,
        "quarantined_rows": quarantine_rows,
        "unmatched_item_events": unmatched,
        "event_rows": by_type,
        "split_rows": by_split,
        "min_event_time": horizon[0],
        "max_event_time": horizon[1],
    }


def _validate_curated(
    connection: duckdb.DuckDBPyConnection,
    settings: Settings,
    embedding_dimension: int,
) -> dict[str, dict[str, Any]]:
    """Run release-blocking invariants against the curated tables."""
    checks: dict[str, dict[str, Any]] = {}

    cohort = connection.execute(
        "SELECT count(*), count(DISTINCT client_id) FROM cohort"
    ).fetchone()
    checks["cohort_size_and_uniqueness"] = {
        "passed": cohort == (settings.cohort_size, settings.cohort_size),
        "row_count": cohort[0],
        "distinct_users": cohort[1],
        "expected": settings.cohort_size,
    }

    catalog = connection.execute(
        """
        SELECT count(*), count(DISTINCT product_id),
               count(*) FILTER (WHERE product_id IS NULL OR category_id IS NULL OR price_bucket IS NULL),
               min(len(embedding_codes)), max(len(embedding_codes))
        FROM catalog
        """
    ).fetchone()
    checks["catalog_contract"] = {
        "passed": (
            catalog[0] == catalog[1]
            and catalog[2] == 0
            and catalog[3] == embedding_dimension
            and catalog[4] == embedding_dimension
        ),
        "row_count": catalog[0],
        "distinct_products": catalog[1],
        "required_null_rows": catalog[2],
        "vector_length_min": catalog[3],
        "vector_length_max": catalog[4],
    }

    events = connection.execute(
        """
        SELECT count(*), count(DISTINCT event_id),
               count(*) FILTER (
                   WHERE event_id IS NULL OR event_time IS NULL OR event_type IS NULL OR user_id IS NULL
               ),
               count(*) FILTER (WHERE split NOT IN ('train', 'validation', 'test'))
        FROM canonical_events
        """
    ).fetchone()
    checks["canonical_event_contract"] = {
        "passed": events[0] == events[1] and events[2] == 0 and events[3] == 0,
        "row_count": events[0],
        "distinct_event_ids": events[1],
        "required_null_rows": events[2],
        "invalid_split_rows": events[3],
    }

    users_outside = connection.execute(
        """
        SELECT count(*) FROM canonical_events e
        ANTI JOIN cohort c ON e.user_id = CAST(c.client_id AS VARCHAR)
        """
    ).fetchone()[0]
    checks["events_belong_to_cohort"] = {
        "passed": users_outside == 0,
        "rows_outside_cohort": users_outside,
    }

    session_violations = connection.execute(
        f"""
        SELECT count(*) FROM (
            SELECT event_time - lag(event_time) OVER (
                PARTITION BY user_id, session_id ORDER BY event_time, event_id
            ) AS gap
            FROM canonical_events
        ) WHERE gap > INTERVAL '{settings.session_gap_minutes} minutes'
        """
    ).fetchone()[0]
    checks["session_gap"] = {
        "passed": session_violations == 0,
        "gap_minutes": settings.session_gap_minutes,
        "violations": session_violations,
    }

    failed = [name for name, result in checks.items() if not result["passed"]]
    if failed:
        raise RuntimeError(f"Curated-data validation failed: {', '.join(failed)}")
    return checks


def run(settings: Settings, overwrite: bool = False) -> dict[str, Any]:
    settings = Settings(
        data_dir=settings.data_dir.resolve(),
        output_dir=settings.output_dir.resolve(),
        profile=settings.profile,
        seed=settings.seed,
        session_gap_minutes=settings.session_gap_minutes,
    )
    if settings.output_dir.exists() and any(settings.output_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory is not empty: {settings.output_dir}; pass --overwrite")
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    repo_root = Path(__file__).resolve().parents[3]
    connection = _connect(settings.output_dir)
    try:
        snapshot = _validate_inputs(connection, settings.data_dir)
        source_quality = _source_profile(connection, settings.data_dir, snapshot)
        for filename in snapshot["files"]:
            snapshot["files"][filename]["sha256"] = _sha256(settings.data_dir / filename)
        _write_json(settings.output_dir / "schema_snapshot.json", snapshot)

        _create_cohort(connection, settings)
        catalog_stats = _create_catalog(connection, settings)
        event_stats = _create_events(connection, settings, started)
        validation_checks = _validate_curated(
            connection, settings, int(catalog_stats["embedding_dimension"])
        )
    finally:
        connection.close()

    completed = datetime.now(timezone.utc)
    sampling_manifest = {
        "profile": settings.profile,
        "seed": settings.seed,
        "cohort_size": settings.cohort_size,
        "eligibility": "client_id has at least one product_buy",
        "selection_rule": f"ORDER BY md5(client_id || ':{settings.seed}'), client_id LIMIT {settings.cohort_size}",
        "cohort_sha256": _sha256(settings.output_dir / "cohort.parquet"),
    }
    split_manifest = {
        "strategy": "time_based",
        "timezone": "UTC",
        "train_end_exclusive": event_stats["max_event_time"] - timedelta(days=28),
        "validation_start_inclusive": event_stats["max_event_time"] - timedelta(days=28),
        "test_start_inclusive": event_stats["max_event_time"] - timedelta(days=14),
        "test_end_inclusive": event_stats["max_event_time"],
        "validation_days": 14,
        "test_days": 14,
        "horizon": {"min": event_stats["min_event_time"], "max": event_stats["max_event_time"]},
        "row_counts": event_stats["split_rows"],
    }
    quality_report = {
        "status": "pass" if event_stats["quarantined_rows"] == 0 else "pass_with_quarantine",
        "scope": {"source_profile": "all source rows", "curated_profile": settings.profile},
        "source": source_quality,
        "catalog": catalog_stats,
        "events": event_stats,
        "validation_checks": validation_checks,
        "notes": [
            "Source-wide duplicate-event counts are not materialized; exact deduplication is applied to the selected cohort.",
            "Unmatched item events remain in canonical_events with is_catalog_match=false and are not silently dropped.",
            "Raw timestamps are interpreted as UTC according to the project data contract.",
        ],
    }
    _write_json(settings.output_dir / "sampling_manifest.json", sampling_manifest)
    _write_json(settings.output_dir / "split_manifest.json", split_manifest)
    _write_json(settings.output_dir / "data_quality_report.json", quality_report)

    artifacts = {}
    for path in sorted(settings.output_dir.glob("*")):
        if path.is_file() and path.name != "data_manifest.json":
            artifacts[path.name] = {"bytes": path.stat().st_size, "sha256": _sha256(path)}
    manifest = {
        "data_version": "synerise-smoke-v1" if settings.profile == "smoke" else "synerise-release-v1",
        "pipeline_version": "0.1.0",
        "profile": settings.profile,
        "git_commit": _git_commit(repo_root),
        "started_at": started,
        "completed_at": completed,
        "duration_seconds": round((completed - started).total_seconds(), 3),
        "artifacts": artifacts,
    }
    _write_json(settings.output_dir / "data_manifest.json", manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    ml_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILE_SIZES), default="smoke")
    parser.add_argument("--data-dir", type=Path, default=ml_root / "synerise_dataset")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--session-gap-minutes", type=int, default=SESSION_GAP_MINUTES)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ml_root = Path(__file__).resolve().parents[1]
    output_dir = args.output_dir or ml_root / "artifacts" / "data" / args.profile
    settings = Settings(
        data_dir=args.data_dir,
        output_dir=output_dir,
        profile=args.profile,
        seed=args.seed,
        session_gap_minutes=args.session_gap_minutes,
    )
    manifest = run(settings, overwrite=args.overwrite)
    print(json.dumps(manifest, default=_json_value, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
