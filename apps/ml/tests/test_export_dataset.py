import hashlib
import json

import duckdb
import pytest

from recobridge_ml.export_dataset import export_dataset


def _write_fixture(tmp_path, *, bundle_product_id: str = "101"):
    data_dir = tmp_path / "curated"
    data_dir.mkdir()
    connection = duckdb.connect()
    connection.execute(
        f"""
        COPY (
            SELECT 101::BIGINT AS product_id, 7::BIGINT AS category_id,
                   3::BIGINT AS price_bucket, [1, 2]::UTINYINT[] AS embedding_codes
            UNION ALL
            SELECT 102, 8, 4, [3, 4]::UTINYINT[]
        ) TO '{(data_dir / "catalog.parquet").as_posix()}' (FORMAT PARQUET)
        """
    )
    connection.execute(
        f"""
        COPY (
            SELECT 1::BIGINT AS client_id
            UNION ALL SELECT 2
        ) TO '{(data_dir / "cohort.parquet").as_posix()}' (FORMAT PARQUET)
        """
    )
    connection.execute(
        f"""
        COPY (
            SELECT
                'event-1'::VARCHAR AS event_id,
                TIMESTAMPTZ '2026-01-01T00:00:00Z' AS event_time,
                'BUY'::VARCHAR AS event_type,
                '1'::VARCHAR AS user_id,
                101::BIGINT AS product_id,
                NULL::BIGINT AS url_id,
                NULL::UTINYINT[] AS search_vector,
                'session-1'::VARCHAR AS session_id,
                7::BIGINT AS category_id,
                3::BIGINT AS price_bucket,
                true::BOOLEAN AS is_catalog_match,
                'train'::VARCHAR AS split,
                'fixture'::VARCHAR AS source_dataset,
                'fixture'::VARCHAR AS source_partition,
                TIMESTAMPTZ '2026-01-02T00:00:00Z' AS ingested_at
            UNION ALL
            SELECT
                'event-2', TIMESTAMPTZ '2026-01-03T00:00:00Z', 'SEARCH', '2',
                NULL, NULL, [5, 6]::UTINYINT[], 'session-2', NULL, NULL, NULL,
                'train', 'fixture', 'fixture', TIMESTAMPTZ '2026-01-04T00:00:00Z'
        ) TO '{(data_dir / "canonical_events.parquet").as_posix()}' (FORMAT PARQUET)
        """
    )
    connection.close()

    bundle = {
        "schema_version": "recobridge-serving-bundle-v1",
        "model_version": "baseline-fixture-v1",
        "feature_version": "fixture-fv1",
        "strategy_version": "fixture-strategy-v1",
        "default_strategy": "category_popular",
        "ranker_promoted": False,
        "products": [
            {
                "product_id": bundle_product_id,
                "category": "7",
                "price_bucket": 3,
                "popularity": 1.0,
                "tags": ["category:7", "price:3"],
            }
        ],
        "user_affinities": {"1": {"7": 1.0}},
        "recently_bought": {"1": ["101"]},
        "rankings": {
            "recent_top": ["101"],
            "global_top": ["101"],
            "category_top": {"7": ["101"]},
        },
    }
    bundle_path = tmp_path / "serving_bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    alias_path = tmp_path / "production.json"
    alias_path.write_text(
        json.dumps(
            {
                "schema_version": "recobridge-production-alias-v1",
                "path": bundle_path.name,
                "bundle_sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    return data_dir, alias_path


def test_export_contains_complete_ml_tables_and_api_bundle(tmp_path):
    data_dir, alias = _write_fixture(tmp_path)
    output = tmp_path / "dataset"

    manifest = export_dataset(data_dir, alias, output)

    assert manifest["counts"] == {
        "products": 2,
        "serving_products": 1,
        "users": 2,
        "serving_users": 1,
        "personalized_users": 1,
        "interactions": 2,
    }
    assert all(value == 0 for value in manifest["integrity_checks"].values())
    assert json.loads((output / "api_bundle.json").read_text())["model_version"] == "baseline-fixture-v1"

    connection = duckdb.connect()
    product = connection.execute(
        f"SELECT product_id, product_id_api, is_serving_candidate "
        f"FROM read_parquet('{(output / 'products.parquet').as_posix()}') ORDER BY product_id"
    ).fetchall()
    user = connection.execute(
        f"SELECT user_id, total_events, buy_count, api_personalized "
        f"FROM read_parquet('{(output / 'users.parquet').as_posix()}') ORDER BY user_id"
    ).fetchall()
    connection.close()
    assert product == [(101, "101", True), (102, "102", False)]
    assert user == [("1", 1, 1, True), ("2", 1, 0, False)]


def test_export_rejects_api_product_outside_ml_catalog(tmp_path):
    data_dir, alias = _write_fixture(tmp_path, bundle_product_id="999")

    with pytest.raises(ValueError, match="api_products_missing_from_catalog=1"):
        export_dataset(data_dir, alias, tmp_path / "dataset")


def test_export_does_not_replace_existing_output_without_flag(tmp_path):
    data_dir, alias = _write_fixture(tmp_path)
    output = tmp_path / "dataset"
    export_dataset(data_dir, alias, output)

    with pytest.raises(FileExistsError, match="--overwrite"):
        export_dataset(data_dir, alias, output)
