---
ID: DAT-01
version: 1.0.0
status: Baseline thiết kế
---
# Lựa chọn bộ dữ liệu Synerise

| Thuộc tính        | Giá trị               |
| ----------------- | --------------------- |
| **Mã tài liệu**   | `DAT-01`              |
| **Phiên bản**     | `1.0.0`               |
| **Ngày cập nhật** | `2026-07-18`          |
| **Trạng thái**    | Baseline thiết kế     |
| **Chủ sở hữu**    | Nhóm dự án RecoBridge |

> **Quy ước:** Nội dung ghi **MVP** là phạm vi phải demo. Nội dung ghi **Target** là kiến trúc định hướng, không được trình bày như chức năng đã hiện thực nếu chưa có bằng chứng chạy thực tế.


## 1. Tuyên bố lựa chọn

Dự án chọn **Synerise Dataset – RecSys Challenge 2025** làm nguồn dữ liệu lịch sử chính. Dữ liệu được thu thập từ hành vi click của website bán lẻ thực tế trong khoảng sáu tháng và cung cấp năm loại event cùng thuộc tính sản phẩm.

## 2. Cấu trúc chính

| Nguồn | Trường cốt lõi | Vai trò |
|---|---|---|
| `product_buy` | client_id, timestamp, sku | tín hiệu mua |
| `add_to_cart` | client_id, timestamp, sku | ý định mua |
| `remove_from_cart` | client_id, timestamp, sku | thay đổi giỏ; tín hiệu cần diễn giải thận trọng |
| `page_visit` | client_id, timestamp, url | cường độ/ngữ cảnh truy cập; không ánh xạ rõ tới item |
| `search_query` | client_id, timestamp, query embedding | ngữ cảnh nhu cầu |
| `product_properties` | sku, category, price bucket, quantized embedding | item features/cold-start |

Repository chính thức công bố số event:

| Event | Số bản ghi |
|---|---:|
| product_buy | 1,682,296 |
| add_to_cart | 5,235,882 |
| remove_from_cart | 1,697,891 |
| page_visit | 150,713,186 |
| search_query | 9,571,258 |

Các con số trên mô tả dataset công bố, không phải số record mà MVP bắt buộc xử lý.

## 3. Lý do phù hợp

1. **Đa sự kiện:** cho phép tạo feature cường độ, recency, conversion proxy và sequence.
2. **Có timestamp:** hỗ trợ time split và rolling windows.
3. **Có product attributes:** category, price bucket và quantized text representation.
4. **Quy mô thực tế:** buộc thiết kế sampling/aggregation và tách offline/online.
5. **Nguồn chính thức:** có trang dataset, repository, baseline và evaluation pipeline.

## 4. Khác biệt giữa bài toán challenge và RecoBridge

Challenge yêu cầu tạo Universal Behavioral Profiles có khả năng khái quát trên nhiều downstream tasks. RecoBridge dùng dữ liệu này cho một mục tiêu hẹp hơn: candidate generation và ranking sản phẩm qua REST API. Vì vậy:

- không sao chép metric/architecture challenge như bằng chứng recommender online;
- không bắt buộc tạo embedding 2048 chiều;
- có thể dùng feature aggregation + K-Means + XGBoost;
- phải tự thiết kế exposure/feedback logs cho hệ thống mới.

## 5. Hạn chế và phản biện

- Không có historical recommendation exposure, position hoặc widget ID.
- `page_visit.url` không cho biết sản phẩm nào hiện diện trên trang.
- Price là quantile bucket, không dùng để tính GMV/AOV thực.
- Text không còn ở dạng raw; embedding đã lượng tử hóa.
- Remove-from-cart không đồng nghĩa “không thích”: có thể do mua sau, đổi số lượng hoặc lý do khác.
- Code repository dùng MIT License; điều này không tự động khẳng định quyền tái phân phối dataset. Nhóm phải kiểm tra terms riêng trước khi đưa dữ liệu lên GitHub.

## 6. Quyết định phiên bản dữ liệu

- **Khuyến nghị:** dùng raw dataset để xây pipeline RecoBridge, nhưng chỉ ingest sample/partition có kiểm soát.
- **Tham khảo:** dùng preprocessed dataset để học cách chia thời gian và đối chiếu baseline.
- **Không trộn target tương lai vào feature lịch sử.**

## 7. Nguồn

- Synerise dataset page: `https://recsys.synerise.com/data-set`
- ACM RecSys Challenge 2025: `https://recsys.acm.org/recsys25/challenge/`
- Official repository: `https://github.com/Synerise/recsys2025`
