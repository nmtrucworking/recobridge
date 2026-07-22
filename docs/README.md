# RecoBridge — Bộ tài liệu dự án

**RecoBridge** là hệ thống gợi ý sản phẩm thông minh tích hợp vào website bán hàng thông qua REST API. Bộ dữ liệu chính được lựa chọn là **Synerise Dataset – RecSys Challenge 2025**. Phương án Machine Learning đã chốt là kiến trúc hybrid: **K-Means hỗ trợ phân khúc/candidate routing**, **XGBRanker thực hiện learning-to-rank**.

| Thuộc tính | Giá trị |
|---|---|
| Phiên bản bộ tài liệu | `1.0.0` |
| Ngày chốt baseline | `2026-07-18` |
| Phạm vi | Kiến trúc hệ thống, tích hợp, dữ liệu, ML, API, bảo mật, kiểm thử, triển khai và bảo vệ đề tài |
| Trạng thái | Hồ sơ thiết kế; cần cập nhật bằng chứng triển khai trong giai đoạn hiện thực |

## 1. Mục tiêu của bộ tài liệu

Bộ tài liệu được tổ chức để đáp ứng trực tiếp bốn nhóm tiêu chí của Đề tài 18:

1. **Kiến trúc tích hợp:** context, component, data flow và sequence diagram; giải thích lựa chọn REST so với gRPC và message broker.
2. **Tính toàn vẹn dữ liệu:** timeout, retry có điều kiện, circuit breaker, idempotency, transaction và cơ chế chống dual-write.
3. **Hiện thực hóa:** hợp đồng API, hướng dẫn chạy local, kịch bản demo không dùng dữ liệu hard-code, test cases và bằng chứng cần thu thập.
4. **Thuyết trình:** ma trận đánh đổi, câu hỏi phản biện, giới hạn dữ liệu và lập luận bảo vệ lựa chọn kiến trúc.

**Giới hạn cần nói rõ:** tài liệu tốt không tự động bảo đảm điểm tuyệt đối. Phần hiện thực chiếm tỷ trọng lớn và chỉ được công nhận khi có hệ thống chạy, log, test và video/demo tương ứng.

## 2. Cấu trúc thư mục

```text
RecoBridge_Docs_v1.0/
├── 00_GOVERNANCE/      # kiểm soát tài liệu, giả định, traceability
├── 01_BUSINESS/        # charter, BRD, use cases, KPI và acceptance
├── 02_DATA/            # Synerise, data dictionary, chất lượng, labeling
├── 03_ARCHITECTURE/    # kiến trúc, flow, tích hợp, resiliency, ADR
├── 04_ML/              # chiến lược ML, feature, train/evaluate, MLOps
├── 05_API/             # API design và OpenAPI contract
├── 06_SECURITY/        # kiến trúc bảo mật và threat model
├── 07_DELIVERY/        # triển khai, test, tiến độ, rủi ro, demo, phản biện
├── 08_APPENDICES/      # nguồn tham khảo, checklist, rubric coverage
└── examples/           # contract/config mẫu, không phải source production
```

## 3. Lộ trình đọc

| Vai trò | Tài liệu nên đọc trước |
|---|---|
| Giảng viên/hội đồng | [Project Charter](01_BUSINESS/01_Project_Charter.md) → [System Architecture](03_ARCHITECTURE/01_System_Architecture.md) → [Rubric Coverage](08_APPENDICES/03_Rubric_Coverage.md) |
| Backend/Integration | [Integration Design](03_ARCHITECTURE/03_Integration_Design.md) → [API Design](05_API/01_API_Design.md) → [Resilience](03_ARCHITECTURE/04_Resilience_Data_Integrity.md) |
| Data/ML | [Dataset Selection](02_DATA/01_Dataset_Selection_Synerise.md) → [Data Dictionary](02_DATA/02_Data_Dictionary_and_Mapping.md) → [ML Strategy](04_ML/01_ML_Problem_and_Strategy.md) |
| QA | [Acceptance Criteria](01_BUSINESS/04_Scope_KPI_Acceptance.md) → [Test Strategy](07_DELIVERY/02_Test_Strategy.md) → [Demo Runbook](07_DELIVERY/05_Demo_Runbook.md) |
| Người thuyết trình | [ADR](03_ARCHITECTURE/05_Architecture_Decision_Records.md) → [Risk Register](07_DELIVERY/04_Risk_Register.md) → [Defense Guide](07_DELIVERY/06_Presentation_Defense.md) |

Nguồn quyết định triển khai ưu tiên cho toàn nhóm: [Baseline sản phẩm MVP](00_GOVERNANCE/04_Product_MVP_Baseline.md).
Danh sách công việc có dependency và acceptance: [Backlog hoàn thiện sản phẩm](07_DELIVERY/07_Implementation_Backlog.md).

## 4. Baseline kiến trúc đã chốt

- **Dữ liệu lịch sử:** Synerise Parquet, không nạp nguyên khối vào API serving.
- **Serving store:** PostgreSQL cho event/audit; catalog và model lookup được nạp read-only vào memory. Không dùng Redis trong MVP.
- **ML:** K-Means phân cụm người dùng; candidate generation theo cụm/danh mục/popularity; XGBRanker xếp hạng top-N.
- **Tích hợp:** website/BFF gọi Recommendation Service bằng REST/JSON.
- **Event ingestion:** MVP nhận sự kiện bằng REST và lưu bền vững; message broker là hướng mở rộng khi lưu lượng hoặc yêu cầu decoupling tăng.
- **Triển khai:** chạy trực tiếp bằng Python và Node.js; PostgreSQL 16 local dùng khi cần lưu event bền vững.
- **Fallback:** cached popular/cluster-popular khi model, feature hoặc dependency không sẵn sàng.

## 5. Quy tắc sử dụng tài liệu

- Không tuyên bố `page_visit` là product exposure: dữ liệu Synerise không cung cấp ánh xạ URL → sản phẩm.
- Không hard-code chiều embedding: mô tả chính thức và README repository có khác biệt; phải introspect schema thực tế.
- Không coi K-Means là recommender hoàn chỉnh hoặc đối thủ ngang cấp với XGBoost; hai mô hình giải hai tầng khác nhau.
- Không đánh giá bằng random split thuần túy; hành vi phải chia theo thời gian.
- Không dùng retry cho thao tác không idempotent nếu chưa có `Idempotency-Key` hoặc cơ chế deduplication.
- Không công bố dataset trong repository dự án trước khi xác minh điều khoản phân phối; license MIT của repository code không mặc nhiên áp dụng cho dữ liệu.

## 6. Definition of Done của bộ hồ sơ

Bộ hồ sơ chỉ được chuyển từ **Baseline thiết kế** sang **Release** khi:

- OpenAPI khớp với endpoint đang chạy.
- Sơ đồ component và deployment khớp quy trình chạy local thực tế.
- Traceability matrix có liên kết tới test/report/log/video.
- Có ít nhất một baseline, một K-Means pipeline và một XGBoost pipeline được đánh giá trên time-based split.
- Demo thể hiện fallback và ít nhất một lỗi dependency có kiểm soát.
- Các con số metric trong slide được truy xuất từ artifact thực nghiệm, không nhập tay.

Xem checklist tại [Quality Checklist](08_APPENDICES/02_Quality_Checklist.md).
