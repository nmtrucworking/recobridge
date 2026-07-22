# Risk Register

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `DEL-04` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


| ID | Rủi ro | P | I | Mức | Giảm thiểu | Dấu hiệu |
|---|---|---:|---:|---:|---|---|
| R-01 | OOM/chậm do dữ liệu lớn | 4 | 4 | 16 | scan/partition/sample theo user | swap/OOM, job kéo dài |
| R-02 | Schema khác mô tả | 3 | 4 | 12 | introspection + accepted variants | missing name/embedding |
| R-03 | XGBoost metric không hơn baseline | 3 | 4 | 12 | feature/candidate ablation; classifier baseline | NDCG thấp |
| R-04 | Negative sampling sai | 4 | 4 | 16 | ghi rõ unobserved negatives; hard-negative policy | metric ảo cao |
| R-05 | Position/exposure bias | 5 | 3 | 15 | không overclaim; thu exposure mới | offline-online lệch |
| R-06 | API latency cao | 3 | 4 | 12 | cap candidates, precompute, cache | p95 > target |
| R-07 | Duplicate feedback | 3 | 4 | 12 | idempotency + unique constraint | event count bất thường |
| R-08 | Demo phụ thuộc internet | 3 | 5 | 15 | local images/data/model; prebuild | download failure |
| R-09 | Runtime khác máy | 3 | 4 | 12 | dependency lock, env example, clean-machine test | path/port lỗi |
| R-10 | Tài liệu lệch code | 4 | 3 | 12 | update in same PR; contract tests | endpoint mismatch |
| R-11 | License dataset không rõ | 3 | 5 | 15 | không redistribute; kiểm tra terms | repo public chứa data |
| R-12 | Thu thập PII ngoài ý muốn | 2 | 5 | 10 | schema allowlist, log filter | email/token trong log |
| R-13 | Scope phình sang Kafka/K8s | 4 | 3 | 12 | giữ MVP/Target separation | chức năng lõi trễ |
| R-14 | Hội đồng hỏi “K-Means gợi ý thế nào?” | 4 | 3 | 12 | giải thích segmentation/candidates, không overclaim | lập luận mơ hồ |

P/I thang 1–5. Rủi ro ≥15 cần owner và review hằng tuần.
