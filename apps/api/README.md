# RecoBridge API

FastAPI service implementing the contract in `docs/05_API/openapi.yaml`.

## Local development

```powershell
python -m pip install -e ".[test]"
$env:RECOBRIDGE_API_TOKEN="recobridge-demo-token"
uvicorn recobridge_api.app:app --reload --port 8000
pytest
```

Without `RECOBRIDGE_DATABASE_URL`, the service uses an isolated in-memory event
store for local development. For durable exposure and feedback ingestion, run
PostgreSQL 16 locally and set `RECOBRIDGE_DATABASE_URL` before starting the API.
