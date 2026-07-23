# Changelog

## [1.3.0] — 2026-07-24

### Added

- Implemented leakage-aware K-Means, hybrid candidate generation, XGBRanker training, bootstrap evaluation, versioned checksums and release decisions.
- Added a bounded baseline serving bundle, checksum-protected production alias, rollback alias handling and full FastAPI request-path benchmark.
- Added experimental quantized-embedding retrieval behind an explicit flag and an ablation test path.

### Validation

- Release cohort: 20,000 users; XGBRanker test NDCG@10 = 0.033462 and candidate Recall@200 = 0.064998.
- The ranker remains unpromoted because Recall@200 is below 0.70; `category_popular` is released as the governed fallback.
- Production fallback p95 = 6.069 ms over 1,000 ASGI requests, below the 200 ms gate.
- 15 ML/API tests pass; production alias checksum and release bundle loading pass.

## [1.2.0] — 2026-07-22

### Added

- Triển khai Recommendation API bằng FastAPI theo contract `/v1`, gồm personalized/cold-start/related recommendation, health, version và error contract.
- Thêm PostgreSQL migration và event ingestion có durable commit, idempotent replay và conflict detection.
- Kết nối website Vinext/React qua BFF same-origin; UI tải top-N theo hồ sơ, ghi exposure sau render và feedback khi tương tác.
- Thêm hướng dẫn chạy local cho web, Recommendation API và PostgreSQL, cùng unit/contract/consumer tests.

### Validation

- 7 API tests, 3 web tests, ESLint và Vinext production build pass.
- FastAPI + PostgreSQL health pass; recommendation, feedback dedup, BFF recommendation và exposure đã được kiểm tra end-to-end.
- Production artifact local của web đã build và chạy BFF thành công.

## [1.1.0] — 2026-07-21

### Changed

- Chốt baseline sản phẩm MVP và Definition of Done dựa trên implementation/evidence.
- Chọn XGBRanker, cohort release 20.000 users, candidate cap 200 và promotion gate cụ thể.
- Chốt stack FastAPI/PostgreSQL chạy local; loại Redis, broker, outbox và online learning khỏi MVP.
- Chốt event API chỉ trả thành công sau durable commit và dùng opaque Bearer token cho demo.
- Chuyển các câu hỏi kiến trúc chặn triển khai thành quyết định; chỉ giữ lại licensing và thông số máy demo là câu hỏi mở.
- Thêm backlog P0 theo dependency, đầu ra và acceptance để triển khai thành sản phẩm chạy thật.

## [1.0.0] — 2026-07-18

### Added

- Baseline tài liệu đầy đủ cho RecoBridge.
- Quyết định chính thức sử dụng Synerise Dataset – RecSys Challenge 2025.
- BRD, use cases, KPI, acceptance criteria và traceability matrix.
- Kiến trúc context/component/deployment, data flow và sequence diagrams bằng Mermaid.
- Thiết kế REST API và OpenAPI 3.1 contract.
- Chiến lược K-Means + XGBoost, feature engineering, time-based evaluation và MLOps.
- Resilience: timeout, retry, circuit breaker, idempotency, transaction/outbox và fallback.
- Security architecture, threat model và privacy governance cập nhật theo pháp luật Việt Nam có hiệu lực năm 2026.
- Test strategy, risk register, project plan, demo runbook và hướng dẫn bảo vệ đề tài.

### Known gaps

- Chưa có số liệu thực nghiệm thực tế của nhóm.
- Chưa xác minh schema trực tiếp từ file dataset đã tải về.
- Chưa có bằng chứng triển khai, test report và video demo.
- Chưa xác minh điều khoản cho phép tái phân phối dataset trong repository dự án.
