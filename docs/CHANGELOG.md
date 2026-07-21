# Changelog

## [1.1.0] — 2026-07-21

### Changed

- Chốt baseline sản phẩm MVP và Definition of Done dựa trên implementation/evidence.
- Chọn XGBRanker, cohort release 20.000 users, candidate cap 200 và promotion gate cụ thể.
- Chốt stack FastAPI/PostgreSQL/Docker Compose; loại Redis, broker, outbox và online learning khỏi MVP.
- Chốt event API chỉ trả thành công sau durable commit và dùng opaque Bearer token cho demo.
- Chuyển các câu hỏi kiến trúc chặn triển khai thành quyết định; chỉ giữ lại licensing và thông số máy demo là câu hỏi mở.
- Thêm backlog P0 theo dependency, đầu ra và acceptance để triển khai thành sản phẩm chạy thật.

## [1.0.0] — 2026-07-18

### Added

- Baseline tài liệu đầy đủ cho RecoBridge.
- Quyết định chính thức sử dụng Synerise Dataset – RecSys Challenge 2025.
- BRD, use cases, KPI, acceptance criteria và traceability matrix.
- Kiến trúc context/container/deployment, data flow và sequence diagrams bằng Mermaid.
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
