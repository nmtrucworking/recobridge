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

## Jupyter Notebook

Mở [`preprocessing.ipynb`](preprocessing.ipynb) bằng kernel của virtual
environment dự án. Notebook dùng lại package pipeline, cho phép chọn profile,
chạy preprocessing và xem quality/split reports cùng curated event samples.
