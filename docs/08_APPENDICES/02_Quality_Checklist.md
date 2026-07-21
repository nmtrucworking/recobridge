# Quality Checklist

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `APP-02` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## A. Scope và consistency

- [ ] Tên dự án, dataset và model nhất quán toàn bộ docs/slide/code.
- [ ] MVP và Target được phân biệt.
- [ ] Không còn con số giả định bị trình bày như đo thực tế.
- [ ] Open questions quan trọng đã đóng hoặc ghi rõ.

## B. Data

- [ ] Schema introspection đã chạy trên file thực.
- [ ] `name/embedding` và vector dimension được xác nhận.
- [ ] Sampling manifest và source checksum tồn tại.
- [ ] Time split/cutoff không leakage.
- [ ] Không gọi `page_visit` là item exposure.
- [ ] Không commit dataset nếu chưa xác minh quyền.

## C. ML

- [ ] Có global/recent popular baseline.
- [ ] K-Means preprocessing fit train-only.
- [ ] Cluster meaning dựa centroid, không đặt trước.
- [ ] Candidate recall được đo.
- [ ] XGBoost có qid/label policy rõ.
- [ ] Có NDCG/Recall + coverage/diversity.
- [ ] Report chứa data/model/feature version.

## D. API/integration

- [ ] OpenAPI validate.
- [ ] Examples validate contract.
- [ ] Response có request/model version.
- [ ] Event endpoint có idempotency.
- [ ] Error retryable phân loại đúng.
- [ ] Website gửi exposure sau render.

## E. Reliability/security

- [ ] Timeout/retry/circuit breaker được test.
- [ ] Fallback có strategy/degraded flag.
- [ ] Duplicate event không tạo record mới.
- [ ] Token/PII không xuất hiện trong logs.
- [ ] Secret không commit.

## F. Deployment/demo

- [ ] Compose khởi động từ máy/môi trường sạch.
- [ ] Health checks pass.
- [ ] Demo có hai user khác nhau và anonymous.
- [ ] Có failure injection.
- [ ] Có DB/log trace theo request ID.
- [ ] Video/ảnh và report khớp release commit.

## G. Thuyết trình

- [ ] Giải thích REST vs gRPC vs broker.
- [ ] Giải thích K-Means vs XGBoost đúng tầng.
- [ ] Nêu hạn chế Synerise.
- [ ] Không đồng nhất offline metric với business lift.
- [ ] Mọi số liệu trên slide có nguồn/bằng chứng.
