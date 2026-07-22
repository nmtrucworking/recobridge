# Baseline sản phẩm MVP đã chốt

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `GOV-04` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-21` |
| **Trạng thái** | Baseline triển khai |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

Tài liệu này là nguồn quyết định ưu tiên khi các tài liệu thiết kế cũ còn dùng từ như “đề xuất”, “tùy chọn”, “classifier/ranker” hoặc “target”. Mọi thay đổi phạm vi phải cập nhật tài liệu này trước khi triển khai.

## 1. Kết quả sản phẩm phải bàn giao

RecoBridge MVP là một sản phẩm chạy end-to-end, không phải notebook hoặc sơ đồ minh họa. Bản bàn giao phải cho phép:

1. chạy ETL và training batch từ Synerise Parquet bằng một lệnh;
2. sinh model bundle có version và báo cáo metric máy đọc được;
3. khởi động website demo, Recommendation API và PostgreSQL trực tiếp trên máy local;
4. gọi API để nhận top-N khác nhau theo user/context, đồng thời có cold-start fallback;
5. render recommendation trên website và ghi exposure/click/cart/purchase vào PostgreSQL;
6. chứng minh idempotency, fallback, model version và một lần rollback model;
7. chạy smoke test và xuất bằng chứng, không dùng response JSON tĩnh.

Dashboard quản trị riêng không thuộc MVP. Thông tin vận hành tối thiểu được cung cấp qua health/version endpoint, structured log và truy vấn/report có sẵn.

## 2. Phạm vi dữ liệu đã chốt

| Hạng mục | Quyết định |
|---|---|
| Nguồn vật lý | Sáu file raw Parquet hiện có trong `apps/ml/synerise_dataset` |
| Cohort | 20.000 user có ít nhất một `product_buy`, chọn ổn định bằng hash với seed `42` |
| Catalog | Toàn bộ SKU hợp lệ trong `product_properties`; serving chỉ trả SKU có metadata hợp lệ |
| Event item-level | `product_buy`, `add_to_cart`, `remove_from_cart` |
| Search | Chỉ dùng thống kê tần suất/recency và vector tổng hợp nếu schema thực tế hợp lệ |
| Page visit | Chỉ aggregate count/recency cho cohort; không ánh xạ URL thành SKU |
| Split | Test = 14 ngày cuối; validation = 14 ngày liền trước; train = phần lịch sử còn lại |
| Tính tái lập | Lưu schema snapshot, checksum file nguồn, cohort IDs/hash, cutoff, seed và quality report |

Nếu cohort 20.000 user vượt tài nguyên máy demo, pipeline được phép chạy profile `smoke` 1.000 user để phát triển; artifact phát hành vẫn phải dùng profile `release` 20.000 user. Không commit raw dataset hoặc curated sample nếu chưa xác minh quyền phân phối.

## 3. Mô hình và recommendation strategy

### 3.1 Baseline bắt buộc

Phải triển khai và đánh giá cùng split/candidate contract:

- global popular;
- recent popular trong 14 ngày trước cutoff;
- cluster popular;
- category popular.

### 3.2 K-Means

- Input là user aggregates chỉ tính trước cutoff, qua `StandardScaler`.
- Thử `k ∈ {4, 6, 8, 10}` với seed `42`.
- Chọn k có silhouette tốt nhất trong các phương án mà cluster nhỏ nhất chiếm ít nhất 3% cohort; nếu không phương án nào đạt, chọn k có Davies–Bouldin thấp nhất và ghi limitation.
- K-Means chỉ tạo `cluster_id`, distance và cluster profile cho candidate routing; không trực tiếp quyết định top-N cuối.

### 3.3 Candidate generation

Mỗi request tạo union theo thứ tự:

1. 60 recent-popular items;
2. 60 cluster-popular items;
3. 60 category-affinity items;
4. 40 item-similarity items từ lịch sử hoặc product context.

Sau dedup, lọc catalog và item đã mua gần đây, candidate pool tối đa 200; nếu thiếu thì refill bằng recent/global popular. Related-items dùng category + product embedding similarity, loại seed item, không giả vờ là personalized ranking.

### 3.4 Ranker đã chọn

- Dùng `XGBRanker(objective="rank:ndcg")`; không dùng `XGBClassifier` trong release MVP.
- `qid = (user_id, cutoff)` và các dòng cùng qid phải liên tiếp.
- Relevance: `product_buy = 2`, `add_to_cart = 1`, candidate không có hành động quan sát được = `0`.
- `remove_from_cart` chỉ là feature; không gán negative tuyệt đối.
- Negative chỉ lấy trong candidate pool tại cutoff; không lấy ngẫu nhiên từ toàn catalog.
- Hyperparameter tuning dùng validation; test chỉ chạy một lần cho báo cáo release.

### 3.5 Promotion gate

Model được đặt làm strategy mặc định khi đồng thời đạt:

- validation NDCG@10 cao hơn ít nhất 3% tương đối so với baseline mạnh nhất;
- test NDCG@10 không thấp hơn baseline mạnh nhất quá 1% tương đối;
- candidate Recall@200 được báo cáo và đạt ít nhất 0,70;
- catalog coverage@10 không thấp hơn 90% coverage của baseline mạnh nhất;
- không có leakage/schema mismatch và toàn bộ artifact checksum hợp lệ;
- p95 của API ≤ 200 ms với profile hiệu năng đã công bố.

Nếu ranker không đạt gate, sản phẩm vẫn chạy bằng baseline tốt nhất và báo `strategy_used` trung thực; không được tuyên bố model ML đã được promote. Kết quả thất bại vẫn là bằng chứng thực nghiệm hợp lệ nhưng chưa đạt acceptance `ML-02`.

## 4. Kiến trúc triển khai MVP

| Thành phần | Lựa chọn đã chốt |
|---|---|
| Recommendation API | Python 3.12 + FastAPI + Pydantic |
| ML/data | Polars/PyArrow, scikit-learn, XGBoost, joblib |
| Database | PostgreSQL 16 |
| Website demo | Vinext/React hiện có, gọi Recommendation API qua BFF same-origin để không lộ token |
| Deployment | Tiến trình local: `web`, `recommendation-api`, PostgreSQL; `trainer` là one-shot profile/job |
| Cache | Không dùng Redis trong MVP; artifact và lookup read-only được nạp vào memory khi startup |
| Event pipeline | Ghi trực tiếp PostgreSQL trong transaction; batch retraining đọc event từ DB |
| Broker/outbox | Không thuộc MVP |
| Training | Manual batch command; không online learning, không training trong request path |
| Model release | Bundle versioned, `production.json` trỏ current version, giữ một version trước để rollback |

API recommendation không phụ thuộc PostgreSQL trên request path sau khi artifact/catalog đã nạp, nhờ đó vẫn trả fallback khi DB ghi event tạm thời lỗi. Readiness chỉ pass khi model bundle hoặc fallback bundle hợp lệ và catalog không rỗng.

## 5. Contract và bảo mật

- Giữ các endpoint trong OpenAPI hiện hành: recommendation, related, exposure, feedback, health và model version.
- Event endpoint chỉ trả thành công sau khi transaction PostgreSQL commit; response `200` dùng cho cả bản ghi mới và deduplicated, kèm cờ phân biệt.
- Cùng `(source, endpoint, Idempotency-Key)` và cùng payload trả kết quả cũ; khác payload trả `409`.
- Dùng Bearer token tĩnh lấy từ environment cho demo; không tuyên bố đây là JWT/OAuth production.
- Health endpoint không yêu cầu token; các endpoint còn lại yêu cầu token.
- Không log token, raw query vector hoặc full feature vector.

## 6. Definition of Done bắt buộc

| Gate | Bằng chứng tối thiểu |
|---|---|
| Data Ready | `schema_snapshot.json`, `data_manifest.json`, quality report và curated tables |
| Model Ready | baseline report, cluster report, `metrics.json`, model bundle và checksum |
| API Ready | OpenAPI contract tests, recommendation/fallback/idempotency tests |
| Integration Ready | website render top-N và feedback xuất hiện trong PostgreSQL |
| Operations Ready | clean local startup, health pass, smoke test và rollback model |
| Release Verified | traceability matrix trỏ tới test report/log/video theo commit và model version |

Một hạng mục chỉ được đánh dấu hoàn thành khi có file hoặc log bằng chứng trong repo/release bundle. Notebook khám phá, mockup, ảnh JSON nhập tay và flow diagram không thay thế implementation.

## 7. Thứ tự triển khai bắt buộc

1. Introspect schema và tạo profile `smoke`/`release`.
2. Curate catalog/events và tạo time split không leakage.
3. Implement baselines, K-Means, candidates, XGBRanker và evaluation.
4. Export bundle rồi implement model loader/recommendation API.
5. Implement PostgreSQL schema, event idempotency và website demo.
6. Hoàn thiện cấu hình chạy local, chạy contract/integration/performance/failure tests.
7. Chỉ sau khi các test pass mới cập nhật slide, video và trạng thái tài liệu.

Không bắt đầu dashboard, Kafka, Redis, Kubernetes, A/B testing hoặc online learning trước khi sáu gate ở mục 6 hoàn tất.
