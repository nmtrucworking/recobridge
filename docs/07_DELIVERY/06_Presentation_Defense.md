# Hướng dẫn thuyết trình và phản biện

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `DEL-06` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Luận điểm trung tâm

> RecoBridge là bài toán tích hợp hệ thống có thành phần ML, không phải bài toán notebook. Giá trị nằm ở dữ liệu đúng thời điểm, candidate/ranking hợp lý, API contract, resilience, feedback loop và khả năng vận hành.

## 2. Câu hỏi thường gặp

### Tại sao dùng Synerise?

Có hành vi đa sự kiện, timestamp và product attributes; phù hợp xây user features và ranking. Hạn chế là thiếu exposure/position và giá thực, nên nhóm không overclaim về online CTR/GMV.

### Tại sao K-Means và XGBoost cùng tồn tại?

K-Means phân đoạn/routing candidate và hỗ trợ sparse user. XGBoost score/rank candidate. Hai mô hình giải hai tầng, không phải so sánh ngang hàng.

### Tại sao không collaborative filtering?

Có thể là baseline/alternative, nhưng đề tài chỉ định XGBoost/K-Means và dự án cần tận dụng context/item/user engineered features. Không phủ nhận CF; nêu là hướng so sánh tương lai.

### Tại sao REST, không gRPC?

Consumer là website/BFF, OpenAPI/JSON đơn giản và đủ latency. gRPC hợp internal high-throughput nhưng tăng adapter/tooling mà MVP chưa cần.

### Message broker ở đâu?

Recommendation request cần synchronous response nên dùng REST. MVP ghi feedback trực tiếp vào PostgreSQL và batch training đọc theo watermark, nên chưa có dual-write. Broker/outbox chỉ hợp lý khi xuất hiện downstream consumer bất đồng bộ thật.

### Nếu API gọi dependency lỗi nửa chừng?

Model/catalog bundle được validate khi startup và có last-known-good/fallback. Event writes dùng idempotency và một PostgreSQL transaction để không trùng; lỗi DB trả 503 và client chỉ retry với cùng key.

### Tại sao không random split?

Random split cho phép thống kê tương lai rò vào quá khứ và không mô phỏng dự đoán thực tế. Dùng time-based split và feature cutoff.

### K-Means có “chính xác” không?

Clustering không có accuracy theo nhãn nếu không có ground truth. Dùng silhouette/DBI và kiểm tra giá trị downstream; không suy luận cụm tốt = conversion tốt.

## 3. Ưu/nhược điểm cần nói thẳng

| Quyết định | Ưu | Nhược |
|---|---|---|
| Synerise | phong phú, thực tế | thiếu exposure và raw semantics |
| XGBoost | mạnh trên tabular, explainable | phụ thuộc feature/negative sampling |
| K-Means | nhanh, dễ diễn giải | giả định hình học, cần chọn k |
| REST | tích hợp dễ | synchronous coupling |
| Local process deployment | ít phụ thuộc công cụ | cần quản lý từng tiến trình |

## 4. Câu kết luận bảo vệ

Không khẳng định “mô hình tốt nhất”. Khẳng định giải pháp **phù hợp ràng buộc**, có baseline, có trade-off, có failure handling và có đường nâng cấp rõ.
