"""Export one governed product/user dataset for both ML and API serving.

The ML side keeps the complete catalog, cohort and canonical interactions in
Parquet.  The API side receives the bounded serving bundle produced by the
trainer.  A manifest proves that API product/user identifiers are subsets of
the complete ML dataset and records schemas, row counts and checksums.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


SCHEMA_VERSION = "recobridge-product-user-dataset-v1"
REQUIRED_DATA_FILES = ("catalog.parquet", "cohort.parquet", "canonical_events.parquet")
REQUIRED_BUNDLE_FIELDS = {
    "model_version",
    "feature_version",
    "strategy_version",
    "products",
}


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _read_bundle(path: Path) -> tuple[Path, dict[str, Any]]:
    source = path.resolve()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("schema_version") == "recobridge-production-alias-v1":
        root = source.parent
        resolved = (root / str(raw["path"])).resolve()
        if root != resolved.parent and root not in resolved.parents:
            raise ValueError("Serving alias resolves outside its model root")
        expected = str(raw.get("bundle_sha256", ""))
        actual = _sha256(resolved)
        if not expected or expected != actual:
            raise ValueError("Serving alias checksum does not match its bundle")
        source = resolved
        raw = json.loads(source.read_text(encoding="utf-8"))

    missing = REQUIRED_BUNDLE_FIELDS.difference(raw)
    if missing:
        raise ValueError(f"Serving bundle is missing fields: {', '.join(sorted(missing))}")
    if not isinstance(raw["products"], list) or not raw["products"]:
        raise ValueError("Serving bundle products must be a non-empty list")
    return source, raw


def _describe(connection: duckdb.DuckDBPyConnection, path: Path) -> list[dict[str, Any]]:
    rows = connection.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{_sql_path(path)}')"
    ).fetchall()
    return [
        {"name": row[0], "type": row[1], "nullable": row[2] == "YES"}
        for row in rows
    ]


def _validate_inputs(data_dir: Path) -> None:
    missing = [name for name in REQUIRED_DATA_FILES if not (data_dir / name).is_file()]
    if missing:
        raise ValueError(f"Curated ML dataset is missing: {', '.join(missing)}")


def _register_bundle_frames(
    connection: duckdb.DuckDBPyConnection, bundle: dict[str, Any]
) -> tuple[int, int]:
    products: list[dict[str, Any]] = []
    seen_products: set[str] = set()
    for item in bundle["products"]:
        product_id = str(item["product_id"])
        if product_id in seen_products:
            raise ValueError(f"Duplicate API product_id: {product_id}")
        seen_products.add(product_id)
        tags = [str(tag) for tag in item.get("tags", [])]
        price_bucket = item.get("price_bucket")
        if price_bucket is None:
            price_bucket = next(
                (
                    int(tag.split(":", 1)[1])
                    for tag in tags
                    if tag.startswith("price:") and tag.split(":", 1)[1].isdigit()
                ),
                None,
            )
        products.append(
            {
                "product_id_api": product_id,
                "category_id_api": str(item["category"]),
                "price_bucket_api": price_bucket,
                "popularity": float(item["popularity"]),
                "tags": tags,
            }
        )

    affinities = bundle.get("user_affinities", {})
    recently_bought = bundle.get("recently_bought", {})
    user_ids = sorted({str(user_id) for user_id in affinities} | {str(user_id) for user_id in recently_bought})
    users = [
        {
            "user_id": user_id,
            "category_affinities_json": json.dumps(
                {
                    str(category): float(weight)
                    for category, weight in affinities.get(user_id, {}).items()
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            "recently_bought": [str(product_id) for product_id in recently_bought.get(user_id, [])],
            "api_personalized": bool(affinities.get(user_id)),
        }
        for user_id in user_ids
    ]

    product_frame = pd.DataFrame(products)
    user_frame = pd.DataFrame(
        users,
        columns=[
            "user_id",
            "category_affinities_json",
            "recently_bought",
            "api_personalized",
        ],
    )
    connection.register("api_product_frame", product_frame)
    connection.register("api_user_frame", user_frame)
    connection.execute("CREATE TEMP TABLE api_products AS SELECT * FROM api_product_frame")
    connection.execute("CREATE TEMP TABLE api_users AS SELECT * FROM api_user_frame")
    return len(products), len(users)


def export_dataset(
    data_dir: Path,
    serving_bundle: Path,
    output_dir: Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create the complete, cross-compatible dataset and return its manifest."""

    data_dir = data_dir.resolve()
    output_dir = output_dir.resolve()
    _validate_inputs(data_dir)
    resolved_bundle, bundle = _read_bundle(serving_bundle)

    if output_dir.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {output_dir}; pass --overwrite to replace it")
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f".{output_dir.name}-", dir=output_dir.parent) as temp_name:
        temp = Path(temp_name)
        connection = duckdb.connect()
        connection.execute("SET TimeZone = 'UTC'")
        connection.execute("SET preserve_insertion_order = false")
        try:
            api_product_count, api_user_count = _register_bundle_frames(connection, bundle)
            catalog = data_dir / "catalog.parquet"
            cohort = data_dir / "cohort.parquet"
            events = data_dir / "canonical_events.parquet"

            connection.execute(
                f"""
                CREATE TEMP TABLE complete_products AS
                SELECT
                    c.product_id,
                    CAST(c.product_id AS VARCHAR) AS product_id_api,
                    c.category_id,
                    CAST(c.category_id AS VARCHAR) AS category_id_api,
                    c.price_bucket,
                    c.embedding_codes,
                    a.product_id_api IS NOT NULL AS is_serving_candidate,
                    COALESCE(a.popularity, 0.0) AS popularity,
                    COALESCE(a.tags, []::VARCHAR[]) AS tags
                FROM read_parquet('{_sql_path(catalog)}') c
                LEFT JOIN api_products a
                    ON CAST(c.product_id AS VARCHAR) = a.product_id_api
                """
            )
            connection.execute(
                f"""
                CREATE TEMP TABLE event_stats AS
                SELECT
                    user_id,
                    min(event_time) AS first_seen_at,
                    max(event_time) AS last_seen_at,
                    count(*) AS total_events,
                    count(*) FILTER (WHERE product_id IS NOT NULL) AS item_events,
                    count(*) FILTER (WHERE event_type = 'BUY') AS buy_count,
                    count(*) FILTER (WHERE event_type = 'ADD_TO_CART') AS add_to_cart_count,
                    count(*) FILTER (WHERE event_type = 'REMOVE_FROM_CART') AS remove_from_cart_count,
                    count(*) FILTER (WHERE event_type = 'PAGE_VISIT') AS page_visit_count,
                    count(*) FILTER (WHERE event_type = 'SEARCH') AS search_count,
                    count(DISTINCT product_id) FILTER (WHERE product_id IS NOT NULL) AS unique_products,
                    count(DISTINCT category_id) FILTER (WHERE category_id IS NOT NULL) AS unique_categories,
                    avg(price_bucket) FILTER (WHERE product_id IS NOT NULL) AS mean_price_bucket
                FROM read_parquet('{_sql_path(events)}')
                GROUP BY user_id
                """
            )
            connection.execute(
                f"""
                CREATE TEMP TABLE favorite_categories AS
                SELECT user_id, category_id AS favorite_category_id,
                       category_events AS favorite_category_events
                FROM (
                    SELECT
                        user_id,
                        category_id,
                        count(*) AS category_events,
                        row_number() OVER (
                            PARTITION BY user_id
                            ORDER BY count(*) DESC, category_id
                        ) AS category_rank
                    FROM read_parquet('{_sql_path(events)}')
                    WHERE category_id IS NOT NULL
                    GROUP BY user_id, category_id
                )
                WHERE category_rank = 1
                """
            )
            connection.execute(
                f"""
                CREATE TEMP TABLE complete_users AS
                SELECT
                    CAST(c.client_id AS VARCHAR) AS user_id,
                    s.first_seen_at,
                    s.last_seen_at,
                    COALESCE(s.total_events, 0) AS total_events,
                    COALESCE(s.item_events, 0) AS item_events,
                    COALESCE(s.buy_count, 0) AS buy_count,
                    COALESCE(s.add_to_cart_count, 0) AS add_to_cart_count,
                    COALESCE(s.remove_from_cart_count, 0) AS remove_from_cart_count,
                    COALESCE(s.page_visit_count, 0) AS page_visit_count,
                    COALESCE(s.search_count, 0) AS search_count,
                    COALESCE(s.unique_products, 0) AS unique_products,
                    COALESCE(s.unique_categories, 0) AS unique_categories,
                    s.mean_price_bucket,
                    f.favorite_category_id,
                    COALESCE(f.favorite_category_events, 0) AS favorite_category_events,
                    COALESCE(a.category_affinities_json, '{{}}') AS category_affinities_json,
                    COALESCE(a.recently_bought, []::VARCHAR[]) AS recently_bought,
                    COALESCE(a.api_personalized, false) AS api_personalized
                FROM read_parquet('{_sql_path(cohort)}') c
                LEFT JOIN event_stats s ON CAST(c.client_id AS VARCHAR) = s.user_id
                LEFT JOIN favorite_categories f ON CAST(c.client_id AS VARCHAR) = f.user_id
                LEFT JOIN api_users a ON CAST(c.client_id AS VARCHAR) = a.user_id
                """
            )

            checks = {
                "catalog_duplicate_product_ids": connection.execute(
                    "SELECT count(*) - count(DISTINCT product_id) FROM complete_products"
                ).fetchone()[0],
                "cohort_duplicate_user_ids": connection.execute(
                    "SELECT count(*) - count(DISTINCT user_id) FROM complete_users"
                ).fetchone()[0],
                "api_products_missing_from_catalog": connection.execute(
                    """
                    SELECT count(*) FROM api_products a
                    ANTI JOIN complete_products p ON a.product_id_api = p.product_id_api
                    """
                ).fetchone()[0],
                "api_users_missing_from_cohort": connection.execute(
                    """
                    SELECT count(*) FROM api_users a
                    ANTI JOIN complete_users u USING (user_id)
                    """
                ).fetchone()[0],
                "interaction_users_missing_from_cohort": connection.execute(
                    f"""
                    SELECT count(DISTINCT e.user_id)
                    FROM read_parquet('{_sql_path(events)}') e
                    ANTI JOIN complete_users u USING (user_id)
                    """
                ).fetchone()[0],
                "matched_item_events_missing_from_catalog": connection.execute(
                    f"""
                    SELECT count(*)
                    FROM read_parquet('{_sql_path(events)}') e
                    ANTI JOIN complete_products p ON e.product_id = p.product_id
                    WHERE e.product_id IS NOT NULL AND e.is_catalog_match
                    """
                ).fetchone()[0],
            }
            failed = {name: value for name, value in checks.items() if value != 0}
            if failed:
                details = ", ".join(f"{name}={value}" for name, value in failed.items())
                raise ValueError(f"Cross-dataset integrity validation failed: {details}")

            products_path = temp / "products.parquet"
            users_path = temp / "users.parquet"
            interactions_path = temp / "interactions.parquet"
            bundle_path = temp / "api_bundle.json"
            connection.execute(
                f"COPY (SELECT * FROM complete_products ORDER BY product_id) "
                f"TO '{_sql_path(products_path)}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            connection.execute(
                f"COPY (SELECT * FROM complete_users ORDER BY user_id) "
                f"TO '{_sql_path(users_path)}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            connection.execute(
                f"COPY (SELECT * FROM read_parquet('{_sql_path(events)}') "
                f"ORDER BY user_id, event_time, event_id) "
                f"TO '{_sql_path(interactions_path)}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            shutil.copyfile(resolved_bundle, bundle_path)

            counts = {
                "products": connection.execute("SELECT count(*) FROM complete_products").fetchone()[0],
                "serving_products": api_product_count,
                "users": connection.execute("SELECT count(*) FROM complete_users").fetchone()[0],
                "serving_users": api_user_count,
                "personalized_users": connection.execute(
                    "SELECT count(*) FROM complete_users WHERE api_personalized"
                ).fetchone()[0],
                "interactions": connection.execute(
                    f"SELECT count(*) FROM read_parquet('{_sql_path(events)}')"
                ).fetchone()[0],
            }
            files = {}
            for name, path in {
                "products": products_path,
                "users": users_path,
                "interactions": interactions_path,
                "api_bundle": bundle_path,
            }.items():
                files[name] = {
                    "path": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                if path.suffix == ".parquet":
                    files[name]["schema"] = _describe(connection, path)

            manifest = {
                "schema_version": SCHEMA_VERSION,
                "created_at": datetime.now(UTC),
                "source": {
                    "curated_data_dir": str(data_dir),
                    "serving_bundle": str(resolved_bundle),
                },
                "model": {
                    "model_version": str(bundle["model_version"]),
                    "feature_version": str(bundle["feature_version"]),
                    "strategy_version": str(bundle["strategy_version"]),
                    "default_strategy": bundle.get("default_strategy"),
                    "ranker_promoted": bool(bundle.get("ranker_promoted", False)),
                },
                "counts": counts,
                "integrity_checks": checks,
                "files": files,
                "compatibility": {
                    "api": "Load api_bundle.json with RECOBRIDGE_MODEL_BUNDLE_PATH",
                    "ml": "Read products.parquet, users.parquet and interactions.parquet with DuckDB/Pandas",
                    "identifier_mapping": {
                        "products.product_id": "ML BIGINT identifier",
                        "products.product_id_api": "API string identifier",
                        "users.user_id": "pseudonymous API/ML string identifier",
                    },
                },
                "privacy": {
                    "contains_direct_pii": False,
                    "user_identifier": "pseudonymous source client_id encoded as string",
                },
            }
            manifest_path = temp / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True, default=_json_default) + "\n",
                encoding="utf-8",
            )

            if output_dir.exists():
                shutil.rmtree(output_dir)
            shutil.move(str(temp), str(output_dir))
            return manifest
        finally:
            connection.close()


def main(argv: list[str] | None = None) -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "release"), default="release")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--serving-bundle", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    data_dir = args.data_dir or root / "apps" / "ml" / "artifacts" / "data" / args.profile
    serving_bundle = args.serving_bundle
    if serving_bundle is None:
        if args.profile != "release":
            parser.error("--serving-bundle is required for non-release profiles")
        serving_bundle = (
            root / "apps" / "ml" / "artifacts" / "models" / "release" / "production.json"
        )
    output_dir = (
        args.output_dir
        or root / "apps" / "ml" / "artifacts" / "datasets" / args.profile
    )
    manifest = export_dataset(
        data_dir,
        serving_bundle,
        output_dir,
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {
                "output": str(output_dir.resolve()),
                "schema_version": manifest["schema_version"],
                "counts": manifest["counts"],
                "model_version": manifest["model"]["model_version"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
