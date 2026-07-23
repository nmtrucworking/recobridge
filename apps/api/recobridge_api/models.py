from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PageType(StrEnum):
    HOME = "home"
    CATEGORY = "category"
    PRODUCT_DETAIL = "product_detail"
    CART = "cart"
    CHECKOUT = "checkout"


class DeviceType(StrEnum):
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"


class RecommendationContext(StrictModel):
    page_type: PageType
    product_id: str | None = None
    category_id: str | None = None
    device_type: DeviceType | None = None


class RecommendationRequest(StrictModel):
    user_id: str | None = Field(default=None, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    context: RecommendationContext
    top_k: int = Field(default=12, ge=1, le=50)
    strategy: str = Field(default="hybrid", pattern="^(hybrid|xgboost|cluster|popular)$")


class RelatedRequest(StrictModel):
    product_id: str = Field(min_length=1, max_length=128)
    top_k: int = Field(default=12, ge=1, le=50)


class RecommendationItem(StrictModel):
    product_id: str
    category_id: str | None = None
    price_bucket: int | None = Field(default=None, ge=0)
    score: float
    rank: int = Field(ge=1)
    reason_code: str | None = None


class RecommendationResponse(StrictModel):
    request_id: str
    model_version: str
    feature_version: str
    strategy_used: str
    degraded: bool
    items: list[RecommendationItem]
    latency_ms: int = Field(ge=0)


class ExposureItem(StrictModel):
    product_id: str
    position: int = Field(ge=1)


class ExposureEvent(StrictModel):
    request_id: str
    user_id: str | None = None
    session_id: str
    widget_id: str
    page_type: str
    occurred_at: datetime
    items: list[ExposureItem] = Field(min_length=1)


class EventType(StrEnum):
    CLICK = "click"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    PURCHASE = "purchase"


class FeedbackEvent(StrictModel):
    request_id: str
    user_id: str | None = None
    session_id: str
    product_id: str
    event_type: EventType
    occurred_at: datetime


class EventAccepted(StrictModel):
    event_id: str
    accepted: bool
    duplicate: bool


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, str] = Field(default_factory=dict)


class ModelVersionResponse(BaseModel):
    model_version: str
    feature_version: str
    strategy_version: str
