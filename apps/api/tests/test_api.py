from datetime import UTC, datetime

from fastapi.testclient import TestClient

from recobridge_api.app import create_app
from recobridge_api.config import Settings
from recobridge_api.store import MemoryEventStore


TOKEN = "test-token-123"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def make_client() -> TestClient:
    app = create_app(
        settings=Settings(api_token=TOKEN, database_url="memory://"),
        store=MemoryEventStore(),
    )
    return TestClient(app)


def recommendation_payload(user_id: str | None = "u_mai") -> dict:
    return {
        "user_id": user_id,
        "session_id": "session-test",
        "context": {"page_type": "home", "device_type": "desktop"},
        "top_k": 4,
        "strategy": "hybrid",
    }


def feedback_payload(product_id: str = "sku_1048") -> dict:
    return {
        "request_id": "request-test",
        "user_id": "u_mai",
        "session_id": "session-test",
        "product_id": product_id,
        "event_type": "add_to_cart",
        "occurred_at": datetime.now(UTC).isoformat(),
    }


def test_recommendations_are_unique_versioned_and_personalized():
    with make_client() as client:
        mai = client.post("/v1/recommendations", json=recommendation_payload("u_mai"), headers=AUTH)
        minh = client.post("/v1/recommendations", json=recommendation_payload("u_minh"), headers=AUTH)
    assert mai.status_code == minh.status_code == 200
    mai_body, minh_body = mai.json(), minh.json()
    assert len(mai_body["items"]) == 4
    assert len({item["product_id"] for item in mai_body["items"]}) == 4
    assert mai_body["model_version"].startswith("baseline-")
    assert mai_body["feature_version"] == "demo-fv1"
    assert [item["product_id"] for item in mai_body["items"]] != [item["product_id"] for item in minh_body["items"]]


def test_cold_start_uses_truthful_fallback():
    with make_client() as client:
        response = client.post("/v1/recommendations", json=recommendation_payload(None), headers=AUTH)
    assert response.status_code == 200
    assert response.json()["degraded"] is True
    assert response.json()["strategy_used"] == "recent_popular"


def test_unavailable_xgboost_strategy_reports_baseline_fallback():
    payload = {**recommendation_payload("u_mai"), "strategy": "xgboost"}
    with make_client() as client:
        response = client.post("/v1/recommendations", json=payload, headers=AUTH)
    assert response.status_code == 200
    assert response.json()["degraded"] is True
    assert response.json()["strategy_used"] == "baseline_hybrid"


def test_related_excludes_seed_item():
    with make_client() as client:
        response = client.post(
            "/v1/recommendations/related",
            json={"product_id": "sku_1048", "top_k": 5},
            headers=AUTH,
        )
    assert response.status_code == 200
    assert "sku_1048" not in {item["product_id"] for item in response.json()["items"]}


def test_auth_and_validation_use_error_contract():
    with make_client() as client:
        unauthenticated = client.post("/v1/recommendations", json=recommendation_payload())
        invalid = client.post("/v1/recommendations", json={**recommendation_payload(), "top_k": 0}, headers=AUTH)
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "UNAUTHENTICATED"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_feedback_idempotency_and_conflict():
    headers = {**AUTH, "Idempotency-Key": "feedback-key-001"}
    payload = feedback_payload()
    with make_client() as client:
        first = client.post("/v1/events/feedback", json=payload, headers=headers)
        duplicate = client.post("/v1/events/feedback", json=payload, headers=headers)
        conflict = client.post("/v1/events/feedback", json={**payload, "product_id": "sku_2091"}, headers=headers)
    assert first.status_code == duplicate.status_code == 200
    assert first.json()["duplicate"] is False
    assert duplicate.json() == {**first.json(), "duplicate": True}
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_exposure_and_health_endpoints():
    payload = {
        "request_id": "request-test",
        "user_id": "u_mai",
        "session_id": "session-test",
        "widget_id": "homepage-top-n",
        "page_type": "home",
        "occurred_at": datetime.now(UTC).isoformat(),
        "items": [{"product_id": "sku_1048", "position": 1}],
    }
    with make_client() as client:
        exposure = client.post(
            "/v1/events/exposure",
            json=payload,
            headers={**AUTH, "Idempotency-Key": "exposure-key-001"},
        )
        live = client.get("/v1/health/live")
        ready = client.get("/v1/health/ready")
    assert exposure.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["checks"]["bundle"] == "ok"


def test_generated_openapi_keeps_the_documented_surface():
    schema = create_app(settings=Settings(api_token=TOKEN), store=MemoryEventStore()).openapi()
    assert set(schema["paths"]) == {
        "/v1/recommendations",
        "/v1/recommendations/related",
        "/v1/events/exposure",
        "/v1/events/feedback",
        "/v1/health/live",
        "/v1/health/ready",
        "/v1/models/version",
    }
    assert "bearerAuth" in schema["components"]["securitySchemes"]
    assert "security" not in schema["paths"]["/v1/health/live"]["get"]
