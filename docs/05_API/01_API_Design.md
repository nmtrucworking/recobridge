# Thiết kế REST API

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `API-01` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Endpoints

| Method | Path | Mục đích |
|---|---|---|
| POST | `/v1/recommendations` | top-N personalized/contextual |
| POST | `/v1/recommendations/related` | related items |
| POST | `/v1/events/exposure` | ghi item đã hiển thị |
| POST | `/v1/events/feedback` | click/cart/purchase |
| GET | `/v1/health/live` | process alive |
| GET | `/v1/health/ready` | dependencies/model ready |
| GET | `/v1/models/version` | model/feature/strategy version |

## 2. Recommendation request

```json
{
  "user_id": "u_123",
  "session_id": "s_456",
  "context": {
    "page_type": "product_detail",
    "product_id": "sku_789",
    "device_type": "desktop"
  },
  "top_k": 12,
  "strategy": "hybrid"
}
```

## 3. Response

```json
{
  "request_id": "01J...",
  "model_version": "xgb-2026-07-18.1",
  "feature_version": "fv1",
  "strategy_used": "hybrid",
  "degraded": false,
  "items": [
    {"product_id": "sku_10", "score": 0.91, "rank": 1, "reason_code": "CLUSTER_AFFINITY"}
  ],
  "latency_ms": 47
}
```

## 4. Error contract

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "top_k must be between 1 and 50",
    "request_id": "01J...",
    "retryable": false,
    "details": []
  }
}
```

| HTTP | Code | Retry |
|---:|---|---:|
| 400/422 | VALIDATION_ERROR | Không |
| 401 | UNAUTHENTICATED | Không |
| 403 | FORBIDDEN | Không |
| 409 | IDEMPOTENCY_CONFLICT | Không |
| 429 | RATE_LIMITED | Có theo Retry-After |
| 503 | DEPENDENCY_UNAVAILABLE | Có giới hạn |

## 5. Headers

- `Authorization: Bearer ...` với opaque token lấy từ environment trong MVP; không tuyên bố JWT/OAuth.
- `X-Request-ID` optional; server tạo nếu thiếu.
- `Idempotency-Key` bắt buộc cho event write.
- `Traceparent` nếu dùng OpenTelemetry.

## 6. Pagination

Recommendation top-N không pagination trong MVP. Giới hạn `top_k` tối đa 50 để bảo vệ latency và payload.

## 7. Contract source

Xem [openapi.yaml](openapi.yaml). Ví dụ JSON trong thư mục `examples/` phải validate với contract này.
