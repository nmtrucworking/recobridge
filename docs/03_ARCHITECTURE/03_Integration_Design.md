# Thiết kế tích hợp và lựa chọn giao thức

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `ARC-03` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Các liên kết

| Liên kết | Giao thức MVP | Lý do |
|---|---|---|
| Website/BFF → Recommendation | REST/HTTPS + JSON | tương thích rộng, OpenAPI, debug và demo dễ |
| Website → Event API | REST/HTTPS + JSON | schema nhỏ, có idempotency và response rõ |
| Recommendation → PostgreSQL | DB protocol | transaction và constraint |
| Recommendation → Redis | Redis protocol | cache low-latency |
| Batch pipeline → files | Parquet/PyArrow | columnar, phù hợp analytics |
| Feedback → training pipeline | DB batch/outbox | đơn giản cho MVP; broker ở target |

## 2. REST vs gRPC vs Message Broker

| Tiêu chí | REST | gRPC | Message Broker |
|---|---|---|---|
| Kiểu tương tác | synchronous request-response | synchronous/streaming RPC | asynchronous event/message |
| Tích hợp web | tốt | cần adapter/gRPC-web | không phù hợp trực tiếp UI |
| Contract | OpenAPI/JSON Schema | Protobuf | event schema |
| Debug demo | dễ | trung bình | khó hơn |
| Coupling thời gian | cao | cao | thấp |
| Latency/throughput | đủ cho MVP | tốt cho service-to-service dày | tốt cho ingestion/decoupling |
| Quyết định | **chọn** | không cần cho MVP | target cho feedback scale lớn |

## 3. Lập luận bảo vệ

- REST là lựa chọn theo ràng buộc tích hợp website hiện có, không phải vì luôn nhanh nhất.
- gRPC hợp lý nếu có nhiều internal service, schema Protobuf thống nhất và throughput cao; lợi ích chưa bù độ phức tạp trong MVP.
- Broker không thay REST recommendation vì người dùng cần response top-N ngay; broker phù hợp đường event bất đồng bộ.

## 4. API versioning

- Prefix `/v1`.
- Thay đổi additive: thêm field optional.
- Breaking change: tạo `/v2` hoặc content negotiation.
- Response phải có `model_version` và `feature_version`, độc lập API version.

## 5. Contract ownership

- OpenAPI là nguồn sự thật cho HTTP contract.
- Consumer contract tests chạy trong CI.
- Example JSON phải validate được với OpenAPI.
- Không sửa request/response trực tiếp trong code mà không cập nhật contract.
