# Kiểm soát tài liệu

| Thuộc tính | Giá trị |
|---|---|
| **Mã tài liệu** | `GOV-01` |
| **Phiên bản** | `1.0.0` |
| **Ngày cập nhật** | `2026-07-18` |
| **Trạng thái** | Baseline thiết kế |
| **Chủ sở hữu** | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Mục đích

Thiết lập một nguồn sự thật duy nhất cho quyết định, yêu cầu, sơ đồ, API contract và bằng chứng kiểm thử. Mọi thay đổi làm lệch scope, schema, endpoint hoặc metric phải cập nhật tài liệu liên quan trong cùng pull request.

## 2. Quy tắc phiên bản

| Loại thay đổi | Tăng phiên bản | Ví dụ |
|---|---|---|
| Major | `X.0.0` | Thay đổi bài toán hoặc kiến trúc lõi |
| Minor | `1.X.0` | Thêm endpoint, use case hoặc model stage |
| Patch | `1.0.X` | Sửa lỗi diễn đạt, ví dụ, link hoặc schema không phá vỡ tương thích |

## 3. Trạng thái tài liệu

- **Draft:** đang soạn, chưa dùng làm chuẩn triển khai.
- **Baseline thiết kế:** đã chốt hướng, nhưng chưa có đủ bằng chứng chạy.
- **Implemented:** đã khớp với mã nguồn và môi trường demo.
- **Verified:** đã có test report/log/video đối chiếu.
- **Deprecated:** không còn là thiết kế hiện hành.

## 4. Ma trận trách nhiệm RACI

| Hạng mục | Data/ML | Backend | Frontend | QA/Docs |
|---|---:|---:|---:|---:|
| Dataset/schema | A/R | C | I | C |
| Feature/label/model | A/R | C | I | C |
| REST API | C | A/R | C | C |
| Widget/event tracking | C | C | A/R | C |
| Resilience/security | C | A/R | C | C |
| Test evidence | C | C | C | A/R |
| Tài liệu/slide | C | C | C | A/R |

`A`: chịu trách nhiệm cuối; `R`: thực hiện; `C`: tham vấn; `I`: được thông báo. Tên thành viên cụ thể cần được điền khi nhóm phân công.

## 5. Quy tắc bằng chứng

Một tuyên bố “đã hoàn thành” phải có ít nhất một trong các bằng chứng:

- commit/pull request;
- API response và log có `request_id`;
- test report;
- model artifact cùng metric file;
- ảnh chụp hoặc video demo;
- Docker Compose startup log.

Không sử dụng ảnh mockup hoặc JSON nhập tay làm bằng chứng hệ thống chạy.
