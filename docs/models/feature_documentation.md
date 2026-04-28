# Tài Liệu Đặc Trưng (Features Documentation)

> [!NOTE]
> File này giải thích ý nghĩa logic kinh doanh của mỗi Feature (Đặc trưng) được dùng trong mô hình. 
> Việc này tránh trường hợp Data Engineer tính sai luồng so với thiết kế của Data Scientist.

## Bảng tra cứu Features (Feature Store Index)

# TODO(author): Lập bảng liệt kê toàn bộ số lượng Feature.

| Tên Feature (Feature Name) | Kiểu Dữ liệu (Data Type) | Mô tả Nghiệp vụ (Business Definition) | Nguồn (Source/Table) | Khung thời gian (Window) |
|-----------------------------|---------------------------|----------------------------------------|-----------------------|---------------------------|
| `txn_count_30d`             | Integer                   | Số lượng giao dịch thành công trong 30 ngày | DB: `transactions`    | 30 ngày (Rolling)         |
| `avg_balance_7d`            | Float                     | Số dư trung bình trong 7 ngày gần nhất   | DB: `accounts`        | 7 ngày                    |
| `is_vip`                    | Boolean                   | Khách hàng thuộc nhóm VIP hay không      | DB: `customers`       | N/A                       |
| # TODO: ...                | ...                       | ...                                    | ...                   | ...                       |

## Phương pháp xử lý Missing Value (Imputation Logic)
# TODO(author): Nếu feature bị Null (không có lịch sử giao dịch), thì điền là 0 hay dùng Mean? Giải thích cụ thể cho từng nhóm feature (Numerical/Categorical).

## Xử lý Ngoại lai (Outlier Handling)
# TODO(author): Feature nào được Cap/Clip (cắt ngọn đáy VD: 1% và 99% percentile).
