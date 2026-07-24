# Product and user dataset

RecoBridge exports one governed release dataset with two representations:

- complete Parquet tables for ML, analysis and retraining;
- a bounded JSON bundle for low-latency Recommendation API serving.

This avoids loading the complete 1.5-million-product catalog into the API while
keeping every curated product, cohort user and canonical interaction available
to ML.

## Build

From the repository root:

```powershell
$env:PYTHONPATH="apps/ml"
python -m recobridge_ml.export_dataset --profile release
```

Use `--overwrite` to replace an existing generated dataset. For another profile,
pass an explicit trainer-generated serving bundle:

```powershell
python -m recobridge_ml.export_dataset `
  --profile smoke `
  --serving-bundle <path-to-serving_bundle.json> `
  --output-dir <output-directory>
```

The release output is generated at `apps/ml/artifacts/datasets/release/` and is
intentionally excluded from Git because it is reproducible and contains large
binary files.

## Files

| File | Purpose |
|---|---|
| `products.parquet` | Complete curated catalog with ML numeric IDs, API string IDs, embeddings, price/category, popularity and serving membership |
| `users.parquet` | Complete cohort with activity aggregates, category preference, recent purchases and API-personalization status |
| `interactions.parquet` | Complete canonical event history with session, split and lineage fields |
| `api_bundle.json` | Checksum-verified trainer output directly loadable by `RecommendationEngine` |
| `manifest.json` | Counts, schemas, SHA-256 checksums, source/model versions and referential-integrity results |

## Identifier contract

| Entity | ML field | API field |
|---|---|---|
| Product | `product_id BIGINT` | `product_id_api VARCHAR` / JSON `product_id` |
| Category | `category_id BIGINT` | `category_id_api VARCHAR` / JSON `category` |
| User | `user_id VARCHAR` | JSON `user_id` |

All user IDs are pseudonymous source identifiers encoded as strings. The export
does not add names, email addresses, phone numbers or other direct PII.

## Load

API:

```powershell
$env:RECOBRIDGE_MODEL_BUNDLE_PATH="$PWD\apps\ml\artifacts\datasets\release\api_bundle.json"
python -m uvicorn recobridge_api.app:app --app-dir apps/api --port 8000
```

ML / DuckDB:

```sql
SELECT * FROM read_parquet('apps/ml/artifacts/datasets/release/products.parquet');
SELECT * FROM read_parquet('apps/ml/artifacts/datasets/release/users.parquet');
SELECT * FROM read_parquet('apps/ml/artifacts/datasets/release/interactions.parquet');
```

An export fails before replacing its destination when it finds duplicate IDs,
an API product outside the ML catalog, an API user outside the cohort, an
interaction user outside the cohort, a matched item outside the catalog, or a
production-alias checksum mismatch.
