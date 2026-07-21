# Feature Engineering

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `ML-02` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Feature groups

### User

- recency từ interaction/buy gần nhất;
- counts 1/7/30/90 ngày theo event type;
- cart-to-buy, remove-to-cart ratios;
- active days và session intensity;
- category/price bucket affinity;
- diversity: unique sku/category;
- cluster_id và centroid distances.

### Item

- category, price bucket;
- global/recent buy/cart counts;
- unique users;
- freshness trong horizon;
- quantized embedding-derived representation;
- popularity percentile.

### User–item

- prior interaction counts;
- time since last interaction;
- category/price preference match;
- similarity giữa user profile vector và item vector;
- item popularity trong user cluster;
- seen/bought flags trong history.

### Context

- hour/day-of-week;
- session depth và recent event sequence;
- page type/current product trong operational system;
- source/device nếu website demo thu được.

## 2. Feature contract

Mỗi feature cần:

- tên và kiểu;
- mô tả;
- source tables;
- cutoff rule;
- null/default policy;
- transformation;
- version;
- online availability.

Ví dụ:

| Feature | Type | Cutoff-safe | Online | Default |
|---|---|---:|---:|---|
| `user_buy_count_30d` | int | Có | precomputed | 0 |
| `item_popularity_7d` | float | Có | cache/DB | global prior |
| `same_category_affinity` | bool | Có | computed | false |
| `user_cluster_id` | category | Có | stored | cold_start_cluster |

## 3. K-Means preprocessing

- log-transform heavy-tailed counts;
- cap outlier theo train quantiles;
- StandardScaler fit train only;
- PCA cho vector cao chiều nếu cần;
- thử nhiều `k`, init và seed;
- lưu full preprocessing pipeline cùng model.

## 4. Embedding caution

Quantized arrays không phải continuous embedding gốc. Không mặc định dùng Euclidean/cosine trực tiếp trên mã bucket mà chưa kiểm chứng encoding. Phương án an toàn cho MVP:

- one-hot/frequency encoding từng bucket vị trí;
- learned/target statistics có leakage control;
- baseline không dùng embedding, sau đó ablation test.

## 5. Feature leakage review

Mỗi feature phải trả lời: “Giá trị này có tồn tại tại thời điểm request/cutoff không?” Nếu không, loại khỏi train hoặc tính lại đúng thời điểm.
