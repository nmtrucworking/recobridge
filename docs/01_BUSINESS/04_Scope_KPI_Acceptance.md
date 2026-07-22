# Phạm vi, KPI và tiêu chí nghiệm thu

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `BUS-04` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Phạm vi MVP chặt

| Có trong MVP | Không bắt buộc trong MVP |
|---|---|
| Sample Synerise có quy tắc | Toàn bộ dữ liệu 168M+ event |
| K-Means segmentation | Deep sequential recommender |
| XGBRanker learning-to-rank | Online learning |
| REST API + OpenAPI | gRPC production |
| PostgreSQL; in-memory read-only lookup | Redis/Kafka/Kubernetes |
| Local process deployment | Multi-region |
| Exposure/feedback logging mới | Historical exposure reconstruction |

## 2. KPI theo tầng

### Data

- Schema validation pass 100% cho file được ingest.
- Duplicate key rate sau dedup bằng 0 trong curated layer.
- Tỷ lệ null của trường bắt buộc bằng 0.
- Data split không có timestamp leakage.

### K-Means

- Báo cáo silhouette và Davies–Bouldin.
- Mỗi cluster có kích thước tối thiểu hợp lý; không có cluster “rác” chiếm đa số mà không giải thích.
- Centroid profile có diễn giải nghiệp vụ, nhưng không dùng chỉ số nội tại để tuyên bố tăng conversion.

### Ranking

- So với `recent-popular`/`global-popular` baseline.
- Metric chính đề xuất: `NDCG@10`; metric phụ: `Recall@10`, `MRR`, coverage, novelty/diversity.
- Promotion gate: validation NDCG@10 cao hơn ít nhất 3% tương đối so với baseline mạnh nhất; test không thấp hơn baseline quá 1%.
- Candidate Recall@200 ≥ 0,70 và coverage@10 ≥ 90% coverage của baseline mạnh nhất.
- Nếu không đạt gate, strategy mặc định phải là baseline mạnh nhất và không được tuyên bố ranker đã promote.

### API/Operations

- 100% request hợp lệ trả schema đúng OpenAPI.
- p95 ≤ 200 ms trong load profile được công bố.
- Event duplicate test không tạo bản ghi thứ hai.
- API recommendation vẫn trả fallback khi model service bị vô hiệu hóa.

## 3. Acceptance scenarios

| ID | Given | When | Then |
|---|---|---|---|
| AC-01 | User có lịch sử | gọi `/recommendations` | nhận top-N từ hybrid strategy |
| AC-02 | User mới | gọi API | nhận fallback, không lỗi 500 |
| AC-03 | Cùng idempotency key | gửi event hai lần | chỉ có một event logic |
| AC-04 | Model artifact lỗi | gọi API | circuit/fallback hoạt động |
| AC-05 | top_k vượt giới hạn | gọi API | trả 422/400 theo contract |
| AC-06 | Product không có catalog | post-filter | item bị loại |
| AC-07 | Model mới kém baseline | promote | pipeline từ chối |
| AC-08 | Máy local sạch | khởi động API, web và PostgreSQL | health checks pass |

## 4. Điều kiện để tuyên bố “hoàn thành”

- Không dùng response JSON tĩnh.
- Có truy vết một item từ dữ liệu → feature → candidate → score → response → exposure event.
- Có ít nhất một failure injection.
- Có file metric và log chứ không chỉ ảnh chụp notebook.
- Số liệu slide khớp report.
