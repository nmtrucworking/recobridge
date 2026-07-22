# Kế hoạch triển khai

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `DEL-03` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Kế hoạch 6 tuần

| Tuần | Mục tiêu | Exit criteria |
|---:|---|---|
| 1 | Chốt scope, tải/inspect data, schema snapshot | data manifest + architecture baseline |
| 2 | ETL sample, canonical events, catalog | quality report + DB seed |
| 3 | K-Means + baselines + candidates | cluster report + recall baseline |
| 4 | XGBoost train/evaluate + artifact bundle | metrics + model version |
| 5 | FastAPI, website integration, events, resilience | E2E flow + tests |
| 6 | Local runtime setup, load/failure test, docs/slide/demo | release candidate + evidence |

## 2. Work breakdown

### Data/ML

- inspect schema;
- sample by user;
- feature pipeline;
- K-Means;
- candidates;
- XGBoost;
- evaluation/artifact.

### Backend/Integration

- DB schema/migrations;
- API contract;
- model loader;
- recommendation and event endpoints;
- idempotency/resilience;
- logs/health.

### Frontend/Demo

- product catalog UI;
- recommendation widget;
- exposure/click tracking;
- user/context switch để chứng minh personalization;
- failure indicator/degraded state.

### QA/Docs

- traceability;
- contract/integration tests;
- performance/failure report;
- diagrams, slide và demo script.

## 3. Critical path

Schema thực tế → sample/feature → candidate/label → model artifact → API integration → E2E/failure test. UI mockup không nằm trên critical path nếu chưa có model và API thật.

## 4. Milestone gates

- M1 Data Ready.
- M2 Baseline Ready.
- M3 Model Candidate Ready.
- M4 Integration Ready.
- M5 Release Verified.
