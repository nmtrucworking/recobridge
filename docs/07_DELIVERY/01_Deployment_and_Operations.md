# Triển khai và vận hành

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `DEL-01` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. MVP deployment

Các thành phần chạy trực tiếp trên máy local:

- `web` hoặc BFF demo bằng Node.js;
- `recommendation-api` bằng Python;
- PostgreSQL 16 khi cần lưu event bền vững;
- batch job/profile để seed/train;
- thư mục model artifacts local.

Redis, broker và outbox không thuộc MVP. API nạp artifact/lookup read-only vào memory khi startup.

## 2. Startup order

1. PostgreSQL health pass.
2. Migration/seed catalog.
3. Model artifact available.
4. Recommendation API load/warm/readiness pass.
5. Website/BFF start.

Mỗi tiến trình phải có health check và retry startup rõ ràng.

## 3. Environments

| Env | Mục đích | Dữ liệu |
|---|---|---|
| local | phát triển | sample nhỏ |
| test | integration/contract | deterministic fixtures |
| demo | trình bày | curated Synerise sample + model release |

## 4. Backup/restore MVP

- Export schema/migration.
- Backup PostgreSQL trước demo.
- Giữ model artifact current + previous.
- Có script reset/seed.
- Không phụ thuộc internet khi demo nếu có thể.

## 5. Health checks

- Liveness: process loop hoạt động.
- Readiness: model valid, DB reachable, catalog count > 0.
- PostgreSQL event store lỗi không làm recommendation readiness fail nếu model/fallback bundle và catalog vẫn hợp lệ; event endpoint phải trả lỗi rõ ràng.

## 6. Demo reliability checklist

- Cài dependency và build ứng dụng trước buổi demo.
- Kiểm tra port conflict.
- Dùng đường dẫn tương đối hoặc biến môi trường cho tài nguyên dự án.
- Seed deterministic.
- Có script `smoke-test`.
- Có video dự phòng nhưng vẫn phải chuẩn bị demo live.
