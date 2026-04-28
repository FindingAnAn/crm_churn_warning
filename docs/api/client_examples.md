# API Client Examples

> [!NOTE]
> Tài liệu này liệt kê các đoạn code mẫu (Snippets) gọi API của hệ thống (ví dụ: REST endpoint để predict, hoặc GraphQL query). 

## 1. Gọi API Dự đoán từ Python (Predict API)

# TODO(author): API yêu cầu headers gì? Bearer Token / API Key?
```python
import requests

url = "http://localhost:8000/predict"
payload = {
    "customer_id": "CUST_12345",
    # TODO(author): bổ sung mock payload theo đúng schema.
}

headers = {
    "Content-Type": "application/json",
    # "Authorization": "Bearer YOUR_TOKEN"
}

response = requests.post(url, json=payload, headers=headers)

if response.status_code == 200:
    print("Dự đoán Churn:", response.json())
else:
    print("Lỗi:", response.text)
```

## 2. Gọi bằng cURL (Terminal)

# TODO(author): Copy lệnh curl tương đương để test nhanh trên Terminal.
```bash
curl -X 'POST' \
  'http://localhost:8000/predict' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "customer_id": "string"
}'
```

## 3. Swagger UI
# TODO(author): Link tới trang Swagger tự phát sinh (nếu dùng FastAPI) khi chạy dev. Ví dụ: `http://localhost:8000/docs`
