# Quản trị dữ liệu và quyền riêng tư

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `DAT-05` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Phạm vi

Dataset Synerise được công bố ở dạng ẩn danh/pseudonymous. Tuy nhiên, dữ liệu vận hành do RecoBridge ghi lại có thể trở thành dữ liệu cá nhân nếu liên kết với tài khoản, thiết bị hoặc lịch sử hành vi. Thiết kế phải tách dữ liệu demo học thuật khỏi dữ liệu người dùng thật.

## 2. Nguyên tắc

- Data minimization: chỉ thu trường cần cho recommendation và audit.
- Purpose limitation: không tái sử dụng event cho mục đích khác mà không xem xét.
- Pseudonymization: không đưa email, tên, số điện thoại vào feature/log.
- Retention: đặt thời hạn cho raw operational events.
- Access control: tách quyền xem raw logs, model admin và API consumer.
- Auditability: ghi ai/phiên bản nào truy cập hoặc promote model.

## 3. Pháp luật Việt Nam cần đối chiếu

Tại thời điểm bộ tài liệu này:

- **Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15** có hiệu lực từ 01/01/2026.
- **Nghị định 356/2025/NĐ-CP** quy định chi tiết và có hiệu lực từ 01/01/2026.
- **Luật Dữ liệu số 60/2024/QH15** có hiệu lực từ 01/07/2025.

Tài liệu này không thay thế tư vấn pháp lý. Với demo dùng dữ liệu công bố và ID ẩn danh, nhóm vẫn cần tránh tái định danh và không thu dữ liệu thật ngoài mục đích.

## 4. Retention đề xuất cho MVP

| Data | Retention đề xuất | Lý do |
|---|---|---|
| Raw Synerise local | trong thời gian học phần | nguồn nghiên cứu, không commit public |
| Curated sample | trong thời gian dự án | tái lập experiment |
| API access logs | 30 ngày | debug/observability |
| Feedback events | 90 ngày hoặc theo mục tiêu train | feature/replay |
| Model artifacts | ít nhất 3 phiên bản gần nhất | rollback |
| Secrets/tokens | không ghi log | bảo mật |

## 5. Dataset redistribution control

- Lưu script download/instruction, không lưu dataset vào Git nếu chưa có quyền.
- Thêm dataset path vào `.gitignore`.
- Không suy ra license dữ liệu từ MIT License của source code repository.
- Ghi checksum và nguồn tải thay vì sao chép file vào artifact nộp.
