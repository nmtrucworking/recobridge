# Resilience và tính toàn vẹn dữ liệu

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `ARC-04` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Phân loại thao tác

| Thao tác | Idempotent tự nhiên | Retry? | Cơ chế |
|---|---:|---:|---|
| GET health/version | Có | Có | exponential backoff nhỏ |
| POST recommendation | Logic read-only | Có giới hạn | request_id; không tạo side effect |
| POST feedback | Không mặc định | Chỉ khi có key | Idempotency-Key + unique constraint |
| Model promotion | Không | Không tự động | state machine/locking |
| Cache invalidate | Cần thiết kế | Có key/version | dedup theo operation ID |

## 2. Timeout budget đề xuất

Với p95 mục tiêu 200 ms:

- request validation/auth: 10–20 ms;
- cache/feature lookup: 30–60 ms;
- candidate + scoring: 50–100 ms;
- catalog filter/serialization: 20–40 ms;
- reserve: phần còn lại.

Giá trị phải được đo, không trình bày như SLA production.

## 3. Retry policy

- Chỉ retry network timeout, connection reset, 429 hoặc 5xx được phân loại transient.
- Tối đa 1–2 retry trong request path.
- Exponential backoff + jitter.
- Không retry 400/401/403/404/422.
- Không có retry lồng nhau ở nhiều tầng.

## 4. Circuit breaker

Trạng thái: Closed → Open → Half-Open. Circuit là target cho dependency remote sau MVP; recommendation MVP dùng artifact local nên ưu tiên startup validation và timeout cho PostgreSQL event write. Khi circuit được bổ sung:

- fail-fast dependency call;
- sử dụng local/cached fallback;
- phát metric `circuit_state` và alert;
- thử probe giới hạn ở half-open.

## 5. Transaction và training input

MVP chỉ có một durable write: transaction insert feedback vào PostgreSQL rồi commit trước khi trả `200`. Batch training đọc trực tiếp bảng event theo watermark; vì không publish sang broker nên không có dual-write hoặc outbox trong MVP. Outbox chỉ được bổ sung khi có downstream broker/service thật.

## 6. Idempotency design

- Header: `Idempotency-Key`.
- Scope: `(client/source, endpoint, key)`.
- Lưu request hash và response/result tối thiểu.
- Nếu cùng key nhưng payload khác: trả 409 Conflict.
- TTL đủ dài để bao phủ retry window; event analytics có thể giữ unique key lâu hơn.

## 7. Fallback hierarchy

1. personalized XGBoost ranking;
2. cluster-level popular;
3. category-related popular;
4. global recent popular;
5. empty response có reason code nếu catalog không sẵn sàng.

Fallback phải được log bằng `strategy_used`, không được ngụy trang thành model output.

## 8. Failure test matrix

| Failure | Expected behavior |
|---|---|
| PostgreSQL event store down | recommendation vẫn chạy; event endpoint trả 503 rõ ràng |
| Model file corrupt | startup readiness fail hoặc last-known-good model |
| DB write timeout | retry nếu transaction chưa commit; idempotency bảo vệ |
| Duplicate feedback | no duplicate row; response duplicate flag |
| Catalog missing items | filter và refill từ candidate list |
| Dependency slow | timeout + circuit + degraded response |

Nguồn pattern: Microsoft Azure Architecture Center — Retry, Circuit Breaker, Saga/transaction patterns.
