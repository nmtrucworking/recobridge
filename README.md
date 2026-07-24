# RecoBridge

RecoBridge is an end-to-end recommendation demo with a Vinext/React storefront,
a FastAPI recommendation service, and durable PostgreSQL event ingestion.

## Run locally

For the presentation environment, start the verified release alias and web BFF
with one command:

```powershell
.\scripts\start-demo.ps1
.\scripts\smoke-demo.ps1
# after the demo
.\scripts\stop-demo.ps1
```

The demo uses two real release-cohort users (`10002945`, `10005456`) and the
checksum-protected `apps/ml/artifacts/models/release/production.json`. The
production strategy is the strongest governed baseline (`category_popular`);
the XGBRanker remains a candidate because Recall@200 did not pass its fixed
promotion gate.

Manual component startup:

```powershell
# Terminal 1: Recommendation API (Python >= 3.12)
python -m pip install -e ".\apps\api[test]"
$env:RECOBRIDGE_API_TOKEN="recobridge-demo-token"
$env:RECOBRIDGE_MODEL_BUNDLE_PATH="$PWD\apps\ml\artifacts\models\release\production.json"
python -m uvicorn recobridge_api.app:app --app-dir apps/api --reload --port 8000

# Terminal 2: web application (Node.js >= 22.13.0)
Set-Location apps/web
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. API documentation is available at
`http://localhost:8000/docs` and readiness at
`http://localhost:8000/v1/health/ready`.

The frontend calls its own `/api/*` BFF routes; the BFF adds the backend token
and forwards requests to the Recommendation API. Selecting a profile fetches a
new top-N list, rendering records an exposure, and likes/cart actions record
feedback with an idempotency key.

The API uses an isolated in-memory event store when
`RECOBRIDGE_DATABASE_URL` is not set. To persist events, run PostgreSQL 16
locally and set that variable before starting the API.

## Test locally

```powershell
python -m pip install -e ".\apps\api[test]"
python -m pytest apps/api/tests

Set-Location apps/web
npm test
```

See `apps/api/README.md` and `apps/web/README.md` for component-specific setup.
The presentation evidence and exact metric interpretation are recorded in
`docs/07_DELIVERY/08_Release_Evidence.md`.

## Export the complete product/user dataset

Build the cross-compatible release dataset after preprocessing and training:

```powershell
$env:PYTHONPATH="apps/ml"
python -m recobridge_ml.export_dataset --profile release
```

The generated `apps/ml/artifacts/datasets/release/` package contains the complete
product catalog, cohort user profiles, canonical interactions, the API serving
bundle, and a checksum/integrity manifest. See `apps/ml/DATASET.md` for its schema
and loading contract.
