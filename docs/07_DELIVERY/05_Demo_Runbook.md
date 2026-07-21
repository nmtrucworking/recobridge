# Demo Runbook

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `DEL-05` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Mục tiêu demo

Chứng minh một luồng tích hợp thật, không phải notebook/model tách rời:

```text
Synerise sample → feature/model artifact → REST API → website widget → feedback log
```

## 2. Chuẩn bị

- clone release tag;
- `.env` hợp lệ;
- model bundle checksum pass;
- Docker images đã build;
- database reset/seed script;
- smoke tests pass;
- hai user demo có hành vi khác nhau;
- một anonymous session;
- script chuyển model hiện hành sang bundle lỗi/không tồn tại để demo readiness hoặc last-known-good fallback.

## 3. Kịch bản 8–10 phút

1. **30 giây:** nêu bài toán và boundary.
2. **60 giây:** mở architecture diagram, chỉ rõ REST và data feedback path.
3. **60 giây:** `docker compose ps` và health endpoints.
4. **2 phút:** user A/B nhận danh sách khác nhau; mở API response có request/model version.
5. **1 phút:** anonymous user nhận fallback có `strategy_used=popular`.
6. **1 phút:** click/add-to-cart và truy vấn DB/log theo request ID.
7. **1 phút:** gửi event trùng; chứng minh dedup.
8. **1 phút:** kích hoạt model failure; API dùng last-known-good/bundled fallback hoặc readiness fail đúng thiết kế.
9. **1 phút:** mở evaluation report so baseline và nêu hạn chế offline.
10. **30 giây:** kết luận trade-offs và hướng mở rộng.

## 4. Câu lệnh/bằng chứng cần quay

- `docker compose up -d`
- `docker compose ps`
- `/v1/health/ready`
- request/response recommendation
- query recommendation logs/feedback count
- duplicate event response
- failure injection + fallback response
- metrics report/model manifest

## 5. Rollback demo

Nếu UI lỗi, dùng Swagger/curl/Postman nhưng vẫn phải chứng minh DB/log. Nếu model candidate lỗi, chuyển last-known-good và ghi rõ. Video dự phòng không thay thế việc hiểu hệ thống.

## 6. Điều không được làm

- sửa DB tay ngay trước hội đồng mà không giải thích;
- dùng JSON tĩnh;
- nói Redis/Kafka/Kubernetes đang chạy nếu không có container/process;
- đưa metric không có report;
- giấu fallback bằng cách gọi đó là XGBoost output.
