import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings
from .engine import BundleError, RecommendationEngine
from .models import (
    EventAccepted,
    ExposureEvent,
    FeedbackEvent,
    HealthResponse,
    ModelVersionResponse,
    RecommendationRequest,
    RecommendationResponse,
    RelatedRequest,
)
from .store import (
    EventStore,
    EventStoreUnavailable,
    IdempotencyConflict,
    create_event_store,
)

logger = logging.getLogger("recobridge.api")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def error_response(code: str, message: str, request_id: str, retryable: bool, details: list[Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "retryable": retryable,
            "details": details or [],
        }
    }


def create_app(
    settings: Settings | None = None,
    engine: RecommendationEngine | None = None,
    store: EventStore | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    recommendation_engine = engine or RecommendationEngine(app_settings.model_bundle_path)
    event_store = store or create_event_store(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            event_store.initialize()
        except EventStoreUnavailable as exc:
            logger.warning(json.dumps({"level": "WARNING", "service": "recommendation-api", "event": "event_store_unavailable", "message": str(exc)}))
        yield
        event_store.close()

    api = FastAPI(
        title="RecoBridge Recommendation API",
        version="1.0.0",
        description="Recommendation serving and idempotent feedback ingestion.",
        lifespan=lifespan,
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    )
    bearer_scheme = HTTPBearer(auto_error=False, scheme_name="bearerAuth", bearerFormat="opaque")

    @api.middleware("http")
    async def request_context(request: Request, call_next):
        started = time.perf_counter()
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if supplied and len(supplied) <= 128 else str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(json.dumps({
            "timestamp": time.time(),
            "level": "INFO",
            "service": "recommendation-api",
            "request_id": request_id,
            "route": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }))
        return response

    async def require_token(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> None:
        import hmac

        if (
            credentials is None
            or credentials.scheme.lower() != "bearer"
            or not hmac.compare_digest(credentials.credentials, app_settings.api_token)
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing bearer token")

    @api.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        details = [
            {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_response("VALIDATION_ERROR", "request validation failed", request.state.request_id, False, details),
        )

    @api.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        code = {
            401: "UNAUTHENTICATED",
            409: "IDEMPOTENCY_CONFLICT",
            422: "VALIDATION_ERROR",
            503: "DEPENDENCY_UNAVAILABLE",
        }.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(code, str(exc.detail), request.state.request_id, exc.status_code == 503),
        )

    @api.exception_handler(BundleError)
    async def bundle_error_handler(request: Request, exc: BundleError):
        return JSONResponse(
            status_code=503,
            content=error_response("DEPENDENCY_UNAVAILABLE", str(exc), request.state.request_id, True),
            headers={"Retry-After": "5"},
        )

    def require_idempotency_key(value: str | None) -> str:
        if value is None or not 8 <= len(value) <= 128:
            raise HTTPException(status_code=422, detail="Idempotency-Key must contain 8 to 128 characters")
        return value

    @api.post("/v1/recommendations", response_model=RecommendationResponse, dependencies=[Depends(require_token)])
    async def create_recommendations(payload: RecommendationRequest, request: Request):
        return recommendation_engine.recommend(payload, request.state.request_id)

    @api.post("/v1/recommendations/related", response_model=RecommendationResponse, dependencies=[Depends(require_token)])
    async def create_related_recommendations(payload: RelatedRequest, request: Request):
        return recommendation_engine.related(payload, request.state.request_id)

    def write_event(endpoint: str, idempotency_key: str, payload: dict[str, Any]) -> EventAccepted:
        try:
            result = event_store.write(endpoint, idempotency_key, payload)
            return EventAccepted(event_id=result.event_id, accepted=True, duplicate=result.duplicate)
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except EventStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @api.post("/v1/events/exposure", response_model=EventAccepted, dependencies=[Depends(require_token)])
    async def create_exposure_event(
        payload: ExposureEvent,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        key = require_idempotency_key(idempotency_key)
        return write_event("exposure", key, payload.model_dump(mode="json"))

    @api.post("/v1/events/feedback", response_model=EventAccepted, dependencies=[Depends(require_token)])
    async def create_feedback_event(
        payload: FeedbackEvent,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        key = require_idempotency_key(idempotency_key)
        return write_event("feedback", key, payload.model_dump(mode="json"))

    @api.get("/v1/health/live", response_model=HealthResponse)
    async def liveness():
        return HealthResponse(status="ok", checks={"process": "ok"})

    @api.get("/v1/health/ready", response_model=HealthResponse)
    async def readiness():
        if not recommendation_engine.ready:
            return JSONResponse(
                status_code=503,
                content=HealthResponse(status="unavailable", checks={"bundle": recommendation_engine.error or "unavailable"}).model_dump(),
            )
        database = event_store.check()
        return HealthResponse(
            status="ok" if database == "ok" else "degraded",
            checks={"bundle": "ok", "catalog": str(len(recommendation_engine.products)), "database": database},
        )

    @api.get("/v1/models/version", response_model=ModelVersionResponse, dependencies=[Depends(require_token)])
    async def model_version():
        return ModelVersionResponse(**recommendation_engine.versions())

    return api


app = create_app()
