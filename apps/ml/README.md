# RecoBridge ML

Pipeline preprocessing đọc trực tiếp sáu file Synerise Parquet theo kiểu
out-of-core và tạo cohort, catalog, canonical events, quarantine cùng các
manifest kiểm chứng được.

## Chạy profile smoke (1.000 buyer)

Từ thư mục `apps/ml`:

```powershell
python -m pip install -e .
recobridge-preprocess --profile smoke
```

Hoặc chạy module trực tiếp sau khi cài dependency:

```powershell
python -m recobridge_ml.preprocess --profile smoke
```

Đầu ra mặc định nằm tại `artifacts/data/smoke/` và không được commit. Profile
release dùng `--profile release` để chọn 20.000 buyer theo cùng seed/hash rule.
Pipeline không ghi đè thư mục có dữ liệu trừ khi truyền rõ `--overwrite`.

## Huấn luyện model

Sau khi có curated artifact, chạy profile smoke để kiểm tra nhanh:

```powershell
recobridge-train --profile smoke
```

Huấn luyện artifact phát hành trên cohort 20.000 buyer:

```powershell
recobridge-train --profile release
```

Trainer kiểm tra checksum/quality đầu vào, fit `StandardScaler` và K-Means
chỉ trên history train, tạo candidate theo cùng contract cho baseline/ranker,
huấn luyện `XGBRanker`, đánh giá validation/test và xuất bundle tại
`artifacts/models/<profile>/<model-version>/`. `latest.json` trỏ tới candidate
mới nhất; trainer không tự ghi `production.json` khi còn gate chưa được
xác minh.

`metrics.json` báo cáo Recall@100/200, query/catalog coverage và recall theo
nguồn candidate; metric ranking kèm phân phối theo query và khoảng tin cậy
bootstrap 95%. So sánh NDCG giữa ranker với baseline mạnh nhất dùng paired
bootstrap trên cùng tập query để tránh diễn giải quá mức từ một point estimate.

## Xác minh và phát hành

Không ghi `production.json` trực tiếp sau training. Chạy benchmark qua FastAPI
request path, sau đó promote bundle đã khớp checksum:

```powershell
python -m recobridge_api.benchmark `
  artifacts/models/release/<model-version>/serving_bundle.json `
  --output artifacts/models/release/performance-<model-version>.json

recobridge-promote `
  artifacts/models/release/<model-version> `
  artifacts/models/release/performance-<model-version>.json
```

Nếu ranker trượt bất kỳ offline gate nào, promoter chỉ phát hành baseline mạnh
nhất ở chế độ `baseline_fallback`; alias ghi rõ gate thất bại và không tuyên bố
XGBoost đã được promote. `production.previous.json` được giữ khi thay alias để
hỗ trợ rollback. Embedding retrieval chỉ bật để ablation bằng
`--enable-embedding-candidates`; kết quả kém hơn không được đưa vào mặc định.

## Jupyter Notebook

Mở [`preprocessing.ipynb`](preprocessing.ipynb) bằng kernel của virtual
environment dự án. Notebook dùng lại package pipeline, cho phép chọn profile,
chạy preprocessing và xem quality/split reports cùng curated event samples.
