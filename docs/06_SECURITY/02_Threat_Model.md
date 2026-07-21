# Threat Model

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `SEC-02` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. STRIDE summary

| Threat | Scenario | Control | Test |
|---|---|---|---|
| Spoofing | giả mạo BFF | JWT/API key, TLS | invalid/expired token |
| Tampering | sửa event/request | TLS, validation, request hash | payload mutation |
| Repudiation | phủ nhận model/action | audit log, request_id, model_version | trace replay |
| Information disclosure | log token/feature | log filtering, least privilege | secret scan |
| Denial of service | top_k lớn/request flood | limits, rate limit, timeout | load/abuse test |
| Elevation of privilege | consumer gọi admin | scopes/RBAC | forbidden scope test |

## 2. ML/data-specific threats

- Data poisoning qua feedback giả.
- Popularity manipulation bằng spam click/cart.
- Model artifact replacement.
- Training-serving skew.
- Membership/re-identification risk khi kết hợp dữ liệu.

## 3. Mitigations

- Event rate/anomaly checks theo user/session/IP ở hệ thống thật.
- Không train trực tiếp từ event chưa qua validation.
- Signed/checksummed model bundle.
- Feature schema validation ở serving.
- Separate staging/production model aliases.
- Rollback last-known-good.

## 4. Residual risks

- Dataset lịch sử không cho kiểm tra toàn bộ position/exposure bias.
- Demo không đủ traffic để đánh giá abuse và online business lift.
- JWT/API key nội bộ đơn giản không thay thế IAM production.
