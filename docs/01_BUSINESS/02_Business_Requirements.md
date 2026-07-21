# Business Requirements Document

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `BUS-02` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Actors

- **Shopper:** người dùng website, có thể đăng nhập hoặc ẩn danh.
- **Website/BFF:** consumer chính của Recommendation API.
- **Recommendation Service:** sinh và xếp hạng gợi ý.
- **Data/ML Operator:** chạy ETL, train, đánh giá và promote model.
- **Administrator:** giám sát health, version, cache và audit.

## 2. Yêu cầu chức năng

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-01 | Hệ thống trả top-N theo user/session/page context | Must |
| FR-02 | Hỗ trợ related items theo `product_id` | Must |
| FR-03 | Hỗ trợ anonymous/cold-start bằng fallback | Must |
| FR-04 | Ghi exposure, click, add-to-cart, purchase | Must |
| FR-05 | Gắn `request_id`, `model_version`, `strategy` vào response/log | Must |
| FR-06 | Lọc item không hoạt động/không có trong catalog demo | Must |
| FR-07 | Health/readiness/version endpoint | Must |
| FR-08 | Cache/invalidate theo model hoặc segment | Should |
| FR-09 | Giải thích gợi ý mức đơn giản bằng reason code | Could |
| FR-10 | A/B variant assignment | Future |

## 3. Yêu cầu phi chức năng

| ID | Thuộc tính | Mục tiêu MVP |
|---|---|---|
| NFR-01 | Latency | p95 ≤ 200 ms trong môi trường demo đã warm |
| NFR-02 | Availability | fallback khi model/cache/feature dependency lỗi |
| NFR-03 | Consistency | event retry không tạo bản ghi trùng |
| NFR-04 | Security | TLS ở môi trường triển khai; token/API key giữa service |
| NFR-05 | Observability | structured logs, metrics và request correlation |
| NFR-06 | Maintainability | API contract versioned; model artifact/version tách biệt |
| NFR-07 | Reproducibility | seed, time split, feature list và dependency version được lưu |
| NFR-08 | Deployability | khởi động qua Docker Compose từ môi trường sạch |

## 4. Business rules

1. Không trả item trùng trong cùng response.
2. Không trả item không tồn tại trong catalog serving.
3. Không trả quá `top_k` hoặc vượt giới hạn API.
4. Với người dùng không đủ feature, chuyển sang segment/popularity fallback.
5. `purchase` có trọng số cao hơn `add_to_cart`; `remove_from_cart` không tự động được xem là negative tuyệt đối.
6. Model mới chỉ được promote khi vượt baseline theo metric đã chốt và không vi phạm guardrail.
7. Event có cùng `(source, idempotency_key)` chỉ được xử lý một lần.
8. Retry chỉ áp dụng cho lỗi transient; lỗi validation không retry.

## 5. Ràng buộc

- Dataset không có exposure log của recommendation system hiện tại.
- `page_visit.url` không tiết lộ sản phẩm trên trang.
- `price` là bucket, không phải giá trị tiền tệ.
- Embedding đã lượng tử hóa, không phải raw text.
- Môi trường học phần giới hạn tài nguyên; phải sampling/aggregate thay vì xử lý toàn bộ online.
