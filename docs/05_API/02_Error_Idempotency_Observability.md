# Error, idempotency và observability contract

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `API-02` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Error principles

- Client error không retry.
- Dependency/transient error có `retryable=true` và có thể kèm `Retry-After`.
- Không trả stack trace, SQL hoặc secret.
- Mọi error có request ID.

## 2. Idempotency behavior

| Trường hợp | Response |
|---|---|
| Key mới, payload mới | 202, `duplicate=false` |
| Key cũ, payload cùng hash | 202, `duplicate=true`, cùng logical event ID |
| Key cũ, payload khác | 409 IDEMPOTENCY_CONFLICT |
| Không có key | 400/422 |

## 3. Structured logging

Tối thiểu:

```json
{
  "timestamp": "...",
  "level": "INFO",
  "service": "recommendation-api",
  "request_id": "...",
  "route": "/v1/recommendations",
  "status_code": 200,
  "latency_ms": 47,
  "strategy": "hybrid",
  "model_version": "...",
  "candidate_count": 200,
  "returned_count": 12,
  "degraded": false
}
```

Không log bearer token, raw query embedding, full feature vector hoặc user PII.

## 4. Metrics

- `http_requests_total{route,status}`
- `http_request_duration_ms`
- `recommendation_strategy_total{strategy}`
- `recommendation_fallback_total{reason}`
- `candidate_count`
- `model_inference_duration_ms`
- `feedback_duplicate_total`
- `outbox_lag_seconds`
- `circuit_breaker_state{dependency}`

## 5. Correlation

Request ID truyền từ BFF hoặc server sinh; được trả về header/body, ghi vào recommendation log và feedback event. Đây là khóa truy vết end-to-end trong demo.
