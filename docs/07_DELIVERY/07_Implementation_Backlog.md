# Backlog hoàn thiện sản phẩm

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `DEL-07` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-21` |
| **Trạng thái** | Baseline triển khai |

Backlog này chuyển [baseline sản phẩm](../00_GOVERNANCE/04_Product_MVP_Baseline.md) thành các hạng mục có đầu ra kiểm chứng được. Chỉ nhận việc P1 sau khi toàn bộ P0 trước nó đã đạt acceptance.

| ID | P | Hạng mục | Đầu ra bắt buộc | Acceptance / test | Phụ thuộc |
|---|---:|---|---|---|---|
| RB-001 | P0 | Chuẩn hóa project/runtime | `pyproject.toml` hoặc lockfile, package layout, CLI entrypoint, seed/config chung | cài mới và import pass trên Python 3.12 | — |
| RB-002 | P0 | Introspect Synerise | schema snapshot, row counts, min/max timestamp, checksum, quality report | fail-fast khi thiếu/cột sai; không hard-code vector dimension | RB-001 |
| RB-003 | P0 | Curate cohort/split | profile smoke 1k và release 20k, canonical events/catalog, split manifest | rerun cùng seed cho cùng cohort; không timestamp leakage | RB-002 |
| RB-004 | P0 | Feature pipeline | user/item/pair feature tables và feature schema version | train-only fit; không NaN/inf; test feature-order | RB-003 |
| RB-005 | P0 | Baselines | global/recent/cluster/category popular implementations + metrics | cùng split/candidate contract; report JSON | RB-004 |
| RB-006 | P0 | K-Means/candidates | fitted scaler+K-Means, cluster report, candidate generator | k rule đúng `GOV-04`; unique candidates ≤200; Recall@200 report | RB-004, RB-005 |
| RB-007 | P0 | XGBRanker/evaluation | trained ranker, tuning record, test report, plots | qid contiguous; promotion gate tự động pass/fail | RB-006 |
| RB-008 | P0 | Model bundle/release | manifest, schemas, model files, lookup tables, checksum, `production.json` | bundle validation, current/previous load và rollback test | RB-007 |
| RB-009 | P0 | PostgreSQL schema | migrations cho feedback/idempotency/request audit | unique constraint; reset/seed deterministic | RB-001 |
| RB-010 | P0 | Recommendation API | FastAPI endpoints khớp OpenAPI, model loader, hybrid/fallback | API-T01..03, ML artifact mismatch và readiness tests | RB-008, RB-009 |
| RB-011 | P0 | Event API | exposure/feedback durable commit, request hash và dedup | EVT-T01..04; DB lỗi trả 503; retry cùng key không trùng | RB-009, RB-010 |
| RB-012 | P0 | Website demo | product list/detail, user selector, recommendation widget, tracking | E2E-T01; exposure chỉ gửi sau render; A/B users khác nhau | RB-010, RB-011 |
| RB-013 | P0 | Docker Compose | `web`, `recommendation-api`, `postgres`, trainer profile, health checks | clean build/up; không cần internet khi chạy demo | RB-008..RB-012 |
| RB-014 | P0 | Verification | unit, contract, integration, ML, failure, performance, smoke scripts | toàn bộ test catalog P0 pass; p95 profile được lưu | RB-013 |
| RB-015 | P0 | Release evidence | traceability links, logs, metrics, screenshots/video, release notes | mỗi Must requirement có bằng chứng theo commit/model version | RB-014 |
| RB-016 | P1 | Scheduled retraining | scheduled job + watermark monitoring | không ảnh hưởng manual release path | RB-015 |
| RB-017 | P2 | Redis/broker/outbox | chỉ mở khi có benchmark hoặc consumer chứng minh nhu cầu | ADR mới và failure tests trước khi merge | RB-015 |

## Quy tắc đóng ticket

- Code review xong nhưng chưa có test/bằng chứng thì ticket vẫn chưa hoàn thành.
- Không dùng notebook làm implementation chính; notebook chỉ để exploration và phải gọi lại package code.
- Mỗi artifact/report chứa `git_commit`, data/model/feature version và timestamp.
- Nếu RB-007 không đạt promotion gate, mở defect/experiment cụ thể; không hạ ngưỡng âm thầm và không chặn RB-010 dùng baseline mạnh nhất làm production strategy.
- Mọi thay đổi OpenAPI, DB schema hoặc feature schema phải đi kèm migration/version và compatibility test.
