# Project Charter

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `BUS-01` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Tên và tuyên bố dự án

**RecoBridge – Hệ thống gợi ý sản phẩm thông minh tích hợp REST API.**

RecoBridge tách logic recommendation khỏi website bán hàng thành một dịch vụ độc lập. Dịch vụ nhận ngữ cảnh người dùng/phiên/trang, sinh ứng viên, xếp hạng sản phẩm và trả top-N; đồng thời thu thập feedback để phục vụ đánh giá và huấn luyện lại.

## 2. Vấn đề cần giải quyết

Website bán hàng có catalog lớn thường dựa vào bestseller, danh mục hoặc lựa chọn thủ công. Các cách này không khai thác đầy đủ lịch sử hành vi, khó cá nhân hóa và khó đo lường chất lượng theo từng phiên. Đề tài cần chứng minh không chỉ một model, mà là **luồng tích hợp hoàn chỉnh** giữa dữ liệu, ML service và website.

## 3. Mục tiêu

### Mục tiêu nghiệp vụ

- Tăng khả năng khám phá sản phẩm phù hợp.
- Cung cấp recommendation widget có thể tích hợp mà không sửa sâu lõi website.
- Tạo nền tảng ghi nhận exposure/feedback để đóng vòng lặp dữ liệu.

### Mục tiêu kỹ thuật MVP

1. ETL sample Synerise thành user/product/interaction features.
2. Huấn luyện K-Means và XGBoost từ dữ liệu thật.
3. Recommendation API trả top-N theo input thực.
4. Website hiển thị recommendation và gửi feedback.
5. Có fallback khi model/dependency không sẵn sàng.
6. Chạy toàn bộ trực tiếp trên máy local.

## 4. Deliverables

| Nhóm | Sản phẩm |
|---|---|
| Tài liệu | BRD/SRS rút gọn, kiến trúc, data/ML/API/security/test/runbook |
| ML | model artifacts, feature schema, evaluation report, baseline comparison |
| Integration | Recommendation API, event API, website widget/BFF integration |
| Operations | local process startup, health checks, logs, seed/migration |
| Demo | kịch bản end-to-end, failure scenario và video/log bằng chứng |

## 5. Ngoài phạm vi MVP

- Recommendation streaming thời gian thực quy mô lớn.
- Online learning sau từng click.
- Kubernetes, service mesh và multi-region.
- Hệ thống A/B testing production đầy đủ.
- Tối ưu doanh thu bằng dữ liệu margin thực — Synerise chỉ cung cấp price bucket.
- Suy diễn nội dung từ URL page_visit — mapping không được cung cấp.

## 6. Tiêu chí thành công

- Demo không hard-code danh sách gợi ý.
- Có ít nhất ba chiến lược: popularity fallback, cluster-based candidate, XGBoost ranking.
- API có request validation, error contract, request_id và model_version.
- Test chứng minh idempotency và fallback.
- Evaluation dùng time-based split và so với baseline.
- Tài liệu và sơ đồ khớp hiện trạng triển khai.
