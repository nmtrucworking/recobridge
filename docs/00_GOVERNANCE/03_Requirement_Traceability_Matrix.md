# Ma trận truy vết yêu cầu

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `GOV-03` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Mục đích

Liên kết yêu cầu → thiết kế → API/model → test → bằng chứng. Cột bằng chứng đang để `TBD` cho tới khi nhóm triển khai.

| ID | Yêu cầu | Thiết kế liên quan | Test chấp nhận | Bằng chứng |
|---|---|---|---|---|
| FR-01 | Trả top-N theo user/session/context | REC API + hybrid pipeline | API-T01 | TBD |
| FR-02 | Gợi ý sản phẩm liên quan theo product | Candidate generator | API-T02 | TBD |
| FR-03 | Ghi exposure/click/cart/purchase | Event API + event store | EVT-T01..04 | TBD |
| FR-04 | Fallback cho cold-start/dependency failure | Popular/cluster-popular cache | RES-T03 | TBD |
| FR-05 | Trả model version và request ID | Response contract | API-T03 | TBD |
| NFR-01 | Không hard-code recommendation | Model/catalog lookup | DEMO-T01 | TBD |
| NFR-02 | p95 API mục tiêu ≤ 200 ms trong profile demo | Cache + candidate cap | PERF-T01 | TBD |
| NFR-03 | Không tạo event trùng khi retry | Idempotency key + unique constraint | RES-T01 | TBD |
| NFR-04 | Dependency lỗi không gây cascade | timeout + circuit breaker | RES-T02 | TBD |
| NFR-05 | Có log/tracing theo request | structured log + request_id | OBS-T01 | TBD |
| ML-01 | K-Means phân cụm trên feature chuẩn hóa | scaler + KMeans | ML-T01 | TBD |
| ML-02 | XGBoost vượt popularity baseline ở metric chính | time split + evaluation | ML-T02 | TBD |
| ML-03 | Có đánh giá coverage/diversity | evaluation report | ML-T03 | TBD |
| SEC-01 | API được xác thực | bearer/API key nội bộ | SEC-T01 | TBD |
| SEC-02 | Không lưu raw token/PII trong log | log filter | SEC-T02 | TBD |
| OPS-01 | Toàn bộ MVP khởi động bằng Docker Compose | compose file | OPS-T01 | TBD |

## 2. Quy tắc cập nhật

- Mỗi test ID phải xuất hiện trong Test Strategy.
- Mỗi bằng chứng phải có đường dẫn tương đối hoặc URL commit/video.
- Nếu yêu cầu bị bỏ, phải ghi lý do và tác động; không được xóa âm thầm.
- Metric chỉ chuyển sang “Verified” khi có file kết quả có timestamp và model version.
