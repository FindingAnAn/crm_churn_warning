# CSKH Confirmed Churners Directory

Thư mục này chứa file danh sách khách hàng đã xác nhận rời bỏ
(confirmed churners) từ bộ phận Chăm sóc Khách hàng (CSKH).

## Format

File CSV với cột `cms_code_enc`:

```csv
cms_code_enc
ABC123
DEF456
GHI789
```

## Convention

- File name: `confirmed_churners.csv`
- Encoding: UTF-8
- Cột bắt buộc: `cms_code_enc` (mã KH đã encode)
- Cập nhật: Đội CSKH cung cấp định kỳ hàng tháng

## Docker Path

```
Host:      /data/churn_prediction/ftp_churn/cskh/confirmed_churners.csv
Container: /churn_data/cskh/confirmed_churners.csv
```
