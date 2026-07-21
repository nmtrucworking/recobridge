# Data Flow và Sequence Diagrams

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `ARC-02` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Data Flow Level 0

```mermaid
flowchart LR
    D1[(Synerise Files)] --> P1[1.0 Chuẩn hóa dữ liệu]
    P1 --> D2[(Canonical Events)]
    D2 --> P2[2.0 Tạo đặc trưng]
    P2 --> D3[(Feature Tables)]
    D3 --> P3[3.0 Train/Evaluate]
    P3 --> D4[(Model Artifacts)]
    W[Website] --> P4[4.0 Recommendation API]
    D3 --> P4
    D4 --> P4
    P4 --> W
    W --> P5[5.0 Feedback Ingestion]
    P5 --> D5[(Operational Logs)]
    D5 --> P2
```

## 2. Recommendation request sequence

```mermaid
sequenceDiagram
    autonumber
    participant U as Shopper
    participant W as Website/BFF
    participant R as Recommendation API
    participant F as In-memory Artifact
    participant M as XGBoost Model
    participant C as In-memory Catalog

    U->>W: Open page
    W->>R: POST /v1/recommendations
    R->>R: Validate auth + schema
    R->>F: Load user/segment/context features
    alt Feature available
      F-->>R: Features + candidates
      R->>M: Predict relevance scores
      M-->>R: Scores
    else Cold-start or dependency failure
      F-->>R: Missing/error
      R->>R: Select cluster/global fallback
    end
    R->>C: Filter active catalog items
    C-->>R: Item validity/metadata
    R-->>W: Top-N + request_id + model_version
    W-->>U: Render widget
    W->>R: POST exposure event
```

## 3. Feedback sequence với idempotency

```mermaid
sequenceDiagram
    participant W as Website
    participant E as Event API
    participant DB as PostgreSQL

    W->>E: POST /v1/events/feedback + Idempotency-Key
    E->>DB: BEGIN
    E->>DB: INSERT event ON CONFLICT DO NOTHING
    E->>DB: COMMIT
    DB-->>E: inserted or duplicate
    E-->>W: 200 committed / duplicate flag
```

## 4. Failure sequence

```mermaid
sequenceDiagram
    participant B as BFF
    participant R as Recommendation API
    participant F as Feature Store
    B->>R: recommendation request
    R->>F: get features (timeout 50ms)
    F--xR: timeout
    R->>F: retry once with jitter (transient only)
    F--xR: timeout
    R->>R: circuit failure count++
    R->>R: use bundled popularity fallback
    R-->>B: 200 degraded=true
```

## 5. Điểm kiểm soát

- Không retry validation/auth errors.
- `200 degraded=true` chỉ khi fallback vẫn là response hợp lệ; nếu không có dữ liệu fallback, trả 503.
- Exposure chỉ gửi sau khi widget thực sự render/visible, không ngay khi API trả response.
