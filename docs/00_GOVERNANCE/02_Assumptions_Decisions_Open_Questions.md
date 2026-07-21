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
| DEC-04 | Docker Compose cho MVP | Phù hợp quy mô học phần và tiêu chí demo toàn hệ thống |
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

## 4. Câu hỏi mở bắt buộc giải quyết trước Release

1. Nhóm dùng raw dataset 1,9 GB hay preprocessed dataset 1,3 GB làm nguồn vật lý chính?
2. Kích thước sample và tiêu chí chọn user/item là gì?
3. Website demo dùng stack nào, và catalog UI lấy dữ liệu từ đâu?
4. XGBoost dùng classifier baseline hay `XGBRanker` trong bản demo cuối?
5. Candidate generation tạo bao nhiêu ứng viên trước re-ranking?
6. Redis có được triển khai thật hay chỉ là target architecture?
7. Endpoint event sẽ ghi trực tiếp PostgreSQL hay qua queue nội bộ?
8. Điều khoản dataset có cho phép nhóm đưa file/snapshot lên GitHub công khai không?
9. Ngưỡng nghiệm thu metric sẽ được chốt sau baseline đầu tiên như thế nào?

## 5. Sai lầm cần tránh

- Gán ý nghĩa cụm K-Means trước khi xem centroid.
- Tạo negative samples ngẫu nhiên từ toàn catalog rồi gọi là “không quan tâm”.
- Dùng `page_visit` như bằng chứng item đã được hiển thị.
- Báo cáo “real-time training” trong khi pipeline thực chất là batch.
- Trình bày Kafka/Kubernetes trong sơ đồ như thành phần đã chạy nếu MVP không triển khai.
