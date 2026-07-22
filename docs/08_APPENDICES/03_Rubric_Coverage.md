# Bao phủ tiêu chí chấm điểm

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `APP-03` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Kiến trúc — 30%

| Yêu cầu | Tài liệu | Bằng chứng cần có |
|---|---|---|
| Sơ đồ kiến trúc tích hợp | ARC-01 | diagram khớp runtime thực tế |
| Data Flow | ARC-02 | trace data end-to-end |
| Sequence Diagram | ARC-02 | request, feedback, failure |
| Chọn REST/gRPC/Broker | ARC-03, ADR | thuyết trình trade-off |

## 2. Tính toàn vẹn dữ liệu — 30%

| Yêu cầu | Tài liệu | Bằng chứng cần có |
|---|---|---|
| Retry Pattern | ARC-04 | transient failure test |
| Circuit Breaker | ARC-04 | open/degraded metrics/log |
| Transaction | ARC-04 | DB transaction test |
| Không trùng khi retry | API-02 | duplicate test/query DB |
| Lỗi nửa chừng | ARC-02/04 | failure injection video |

## 3. Hiện thực hóa — 30%

| Yêu cầu | Tài liệu | Bằng chứng cần có |
|---|---|---|
| Không hard-code | BUS-04, DEL-05 | model-driven response |
| REST API chạy | API-01/openapi | Swagger/curl + logs |
| Model thực | ML-03/04 | artifact + metrics |
| Local runtime | DEL-01 | clean startup |
| Website integration | BUS-03, DEL-05 | widget + feedback |

## 4. Thuyết trình — 10%

| Yêu cầu | Tài liệu | Bằng chứng |
|---|---|---|
| Ưu/nhược giải pháp | ADR, DEL-06 | slide trade-off |
| Giới hạn dữ liệu/model | DAT-01, ML-03 | trả lời phản biện |
| Demo có cấu trúc | DEL-05 | runbook/video |

## 5. Điểm nghẽn thực tế

Bộ docs có thể bao phủ toàn bộ câu hỏi lý thuyết. Tuy nhiên, 30% hiện thực hóa và một phần integrity chỉ đạt điểm khi có **bằng chứng chạy**. Ba hạng mục có rủi ro mất điểm cao nhất:

1. recommendation vẫn là JSON/hard-code;
2. retry tạo duplicate event;
3. sơ đồ có Kafka/Kubernetes nhưng demo không có.
