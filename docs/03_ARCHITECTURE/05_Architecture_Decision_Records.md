# Architecture Decision Records

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `ARC-05` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## ADR-001 — Synerise làm dữ liệu chính

**Status:** Accepted.  
**Context:** cần behavioral logs đa sự kiện.  
**Decision:** dùng Synerise; sample theo user và time.  
**Consequences:** feature phong phú nhưng thiếu exposure/position và giá thực.

## ADR-002 — REST thay gRPC cho serving MVP

**Status:** Accepted.  
**Decision:** REST/JSON/OpenAPI giữa BFF và Recommendation Service.  
**Trade-off:** dễ tích hợp và trình bày; payload/latency kém tối ưu hơn Protobuf nhưng không phải bottleneck chính của MVP.

## ADR-003 — Hybrid K-Means + XGBoost

**Status:** Accepted.  
**Decision:** K-Means không trực tiếp trả recommendation cuối; dùng cluster/candidate routing. XGBoost score/rank.  
**Trade-off:** phức tạp hơn một model đơn nhưng câu chuyện kiến trúc rõ và xử lý cold-start tốt hơn.

## ADR-004 — PostgreSQL làm serving/audit store

**Status:** Accepted.  
**Reason:** transaction, unique constraint, query/report đơn giản.  
**Alternative:** document store hoặc event store chuyên dụng; chưa cần trong MVP.

## ADR-005 — Docker Compose, không Kubernetes

**Status:** Accepted.  
**Reason:** phù hợp tài nguyên, tái lập demo và tiêu chí học phần.  
**Consequence:** không chứng minh autoscaling production; chỉ trình bày target.

## ADR-006 — Feedback REST durable synchronous commit

**Status:** Accepted.  
**Decision:** API validate, ghi trực tiếp PostgreSQL trong transaction và chỉ trả `200` sau commit; batch training đọc theo watermark.
**Alternative:** Kafka/outbox; chưa có downstream consumer độc lập nên chỉ tăng hạ tầng và failure modes trong MVP.

## ADR-009 — Không dùng Redis trong MVP

**Status:** Accepted.
**Decision:** load model, feature lookup, catalog và popularity fallback read-only vào memory khi startup.
**Trade-off:** mỗi replica giữ một bản dữ liệu nhưng deployment MVP chỉ có một replica; đổi lại giảm dependency và failure mode.

## ADR-010 — XGBRanker là ranker release

**Status:** Accepted.
**Decision:** dùng `XGBRanker(objective="rank:ndcg")` với graded relevance; không phát hành `XGBClassifier`.
**Reason:** mục tiêu cần tối ưu thứ tự top-N theo query group và metric chính là NDCG@10.

## ADR-007 — Time-based evaluation

**Status:** Accepted.  
**Reason:** hành vi là dữ liệu thời gian; random split có leakage và không phản ánh dự đoán tương lai.

## ADR-008 — OpenAPI 3.1 làm contract source of truth

**Status:** Accepted.  
**Reason:** chuẩn ngôn ngữ độc lập, hỗ trợ validation/client generation và consumer testing.
