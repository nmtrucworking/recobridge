# Giả định, quyết định và câu hỏi mở

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `GOV-02` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Quyết định đã chốt

| ID | Quyết định | Lý do |
|---|---|---|
| DEC-01 | Synerise là dữ liệu chính | Có hành vi đa sự kiện, thời gian, product attributes và quy mô đủ lớn |
| DEC-02 | REST/JSON cho website → Recommendation Service | Dễ tích hợp với website hiện có, hỗ trợ OpenAPI và debug trực quan |
| DEC-03 | K-Means + XGBoost theo pipeline hybrid | K-Means hỗ trợ segmentation/candidate routing; XGBoost tối ưu scoring/ranking |
| DEC-04 | Chạy trực tiếp các thành phần MVP | Giảm phụ thuộc công cụ và phù hợp quy trình phát triển local |
| DEC-05 | Time-based split | Tránh leakage từ tương lai vào quá khứ |
| DEC-06 | Event endpoint có idempotency | Bảo vệ dữ liệu khi retry hoặc client gửi lại |

## 2. Giả định thiết kế

| ID | Giả định | Tác động nếu sai | Cách xác minh |
|---|---|---|---|
| ASM-01 | Website có thể gọi REST API từ backend/BFF | Phải đổi sang frontend-direct hoặc adapter | Xác minh stack website |
| ASM-02 | Product IDs của demo có thể ánh xạ sang catalog nội bộ | Không render được sản phẩm | Xây bảng mapping/catalog seed từ Synerise |
| ASM-03 | Máy demo đủ RAM để xử lý sample, không phải toàn bộ 168M+ events | Pipeline chậm hoặc OOM | Benchmark sample 1–5% và incremental aggregation |
| ASM-04 | MVP không cần Kafka | Event ingestion chỉ ở mức vừa | Load test và kiểm tra độ trễ ghi sự kiện |
| ASM-05 | Dữ liệu demo không chứa PII thực | Giảm phạm vi compliance | Kiểm tra file và không thêm trường định danh trực tiếp |

## 3. Mâu thuẫn nguồn cần xử lý bằng introspection

Các mô tả chính thức không hoàn toàn đồng nhất:

- Trang dataset mô tả `product_properties.embedding`; README repository mô tả trường `name` chứa vector embedding đã lượng tử hóa.
- Trang dataset mô tả search query là mảng 20 chiều; README repository mô tả encoding có 16 bucket.

**Quyết định:** pipeline không được hard-code tên cột phụ hoặc chiều vector. Bước ingestion phải đọc schema Parquet thực tế, ghi vào `schema_snapshot.json` và dừng nếu không khớp contract được chấp nhận.

## 4. Các câu hỏi đã được chốt ngày 2026-07-21

| Câu hỏi | Quyết định |
|---|---|
| Nguồn dữ liệu | Raw Parquet hiện có; curated cohort 20.000 buyers, seed 42 |
| Website demo | FastAPI/Jinja + vanilla JavaScript, catalog từ artifact/metadata đã curate |
| Ranker | `XGBRanker(objective="rank:ndcg")` |
| Candidate cap | Tối đa 200 item trước re-ranking |
| Redis | Không triển khai trong MVP |
| Event write | Ghi trực tiếp PostgreSQL trong transaction, không queue/outbox |
| Dataset công khai | Không commit raw/snapshot cho tới khi có bằng chứng quyền phân phối |
| Promotion metric | +3% validation NDCG@10 so với baseline mạnh nhất và các guardrail trong `GOV-04` |

Chi tiết và thứ tự ưu tiên quyết định xem [Baseline sản phẩm MVP](04_Product_MVP_Baseline.md).

## 5. Câu hỏi còn mở nhưng không chặn triển khai

1. Điều khoản dataset có cho phép phát hành curated snapshot hay chỉ cho phép script tái tạo?
2. Thông số máy demo chính thức là gì để ghi vào performance report?

## 6. Sai lầm cần tránh

- Gán ý nghĩa cụm K-Means trước khi xem centroid.
- Tạo negative samples ngẫu nhiên từ toàn catalog rồi gọi là “không quan tâm”.
- Dùng `page_visit` như bằng chứng item đã được hiển thị.
- Báo cáo “real-time training” trong khi pipeline thực chất là batch.
- Trình bày Kafka/Kubernetes trong sơ đồ như thành phần đã chạy nếu MVP không triển khai.
