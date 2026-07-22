# Model Serving và MLOps

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `ML-04` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Artifact bundle

```text
model_bundle/
├── manifest.json
├── xgb_model.json
├── kmeans_pipeline.joblib
├── feature_schema.json
├── candidate_config.json
├── metrics.json
└── checksum.sha256
```

`manifest.json` phải có model version, training cutoff, git commit, feature version, library versions và compatibility range.

## 2. Startup behavior

- API load artifact một lần khi khởi động.
- Validate checksum/schema.
- Warm up bằng synthetic feature vector hợp lệ.
- Readiness chỉ pass khi model và catalog tối thiểu sẵn sàng.
- Nếu candidate model lỗi, dùng last-known-good; không tự động phục vụ model chưa validate.

## 3. Online inference

1. Resolve user features.
2. Resolve cluster/candidates.
3. Build feature matrix đúng order từ schema.
4. Predict scores.
5. Post-filter/dedup/refill.
6. Log request summary; không log full sensitive feature vector.

## 4. Versioning

- API version: contract HTTP.
- Model version: artifact.
- Feature version: semantics/order.
- Data snapshot version: training source.
- Strategy version: candidate/post-filter rules.

Mọi response có `model_version` và `strategy_used`.

## 5. Monitoring

- System: p50/p95/p99, 5xx, CPU/RAM.
- Data: null/cardinality/distribution drift.
- Model: score distribution, fallback rate, coverage.
- Business: exposure/click/cart/buy by strategy.
- Integrity: duplicate event count, event write failure rate.

## 6. Retraining

MVP: manual batch bằng CLI local. Scheduled batch là target sau MVP. Trigger target:

- định kỳ;
- đủ event mới;
- drift vượt threshold;
- catalog thay đổi mạnh;
- metric operational suy giảm.

Không gọi là continual learning nếu model vẫn retrain batch.
