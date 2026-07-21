# Chiến lược kiểm thử

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `DEL-02` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Test pyramid

- Unit: feature transforms, candidate merge, post-filter, error classification.
- Contract: OpenAPI request/response và consumer expectations.
- Integration: API + PostgreSQL + Redis/model artifact.
- ML: split/leakage, baseline, reproducibility.
- Resilience: timeout, duplicate, dependency failure.
- E2E: website → API → render → feedback → DB.
- Performance: warm p95 theo load profile công bố.

## 2. Test catalog

| ID | Test |
|---|---|
| API-T01 | valid personalized request returns ≤ top_k unique items |
| API-T02 | related request excludes seed item if rule requires |
| API-T03 | response includes request/model/feature versions |
| EVT-T01 | exposure accepted with positions |
| EVT-T02 | click feedback accepted |
| EVT-T03 | duplicate idempotency key deduplicated |
| EVT-T04 | same key/different payload returns 409 |
| RES-T01 | DB timeout retry does not duplicate event |
| RES-T02 | feature/cache dependency triggers circuit/fallback |
| RES-T03 | new user receives popular fallback |
| ML-T01 | preprocessing fitted train-only and K-Means reproducible |
| ML-T02 | XGBoost compared with same-split baseline |
| ML-T03 | coverage/diversity report generated |
| SEC-T01 | invalid/expired token rejected |
| SEC-T02 | logs contain no token/PII |
| PERF-T01 | p95 within declared profile |
| OPS-T01 | clean compose startup and health pass |
| DEMO-T01 | recommendation changes by user/context and is not static |

## 3. ML tests

- Feature column order exact match artifact.
- No NaN/inf after preprocessing.
- qid sorted/contiguous.
- No user/item future statistics leak.
- Model predicts finite scores.
- Ranking stable for same input/version.

## 4. Performance profile phải công bố

Ví dụ: 20 concurrent users, 1,000 requests, warm cache, fixed top_k=12, local machine specs. Không so sánh latency nếu profile khác nhau.

## 5. Test report format

- environment and commit;
- timestamp;
- pass/fail/skip;
- logs/metrics link;
- defect ID;
- model/data version;
- known limitations.
