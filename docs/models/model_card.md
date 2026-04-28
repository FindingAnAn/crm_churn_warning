# Thẻ Mô Hình (Model Card)

Mô hình theo quy định phải có Model Card cung cấp mức độ tin tưởng, hiệu năng, và hướng dẫn cho mọi bên liên quan.

## 1. Thông tin chung (Model Details)
- **Người phát triển:** Nhóm Khoa học Dữ liệu (Data Science Team)
- **Ngày tạo mô hình:** # TODO(author): Ngày huấn luyện phiên bản này (VD: 2026-04)
- **Phiên bản:** # TODO(author): vX.Y.Z
- **Thuật toán/Loại mô hình:** # TODO(author): Random Forest, XGBoost hay Neural Networks?
- **Giấy phép/Quyền hạn:** Nội bộ (Internal Use Only)

## 2. Mục đích sử dụng (Intended Uses)
- **Mục đích chính:** # TODO(author): Mô hình dự đoán nhóm khách hàng thuê bao B2B có nguy cơ hủy dịch vụ trong 30 ngày tới.
- **Người dùng chính (Ai sẽ xem/dùng):** # TODO(author): Chuyên viên CSKH.
- **Các giới hạn (Out-of-Scope):** # TODO(author): KHÔNG dùng để khóa tự động tài khoản, chỉ dùng cảnh báo. KHÔNG áp dụng cho khách hàng cá nhân (B2C).

## 3. Các thông số đầu vào (Factors/Features)
- # TODO(author): Liệt kê nhanh tập đầu vào hoặc [Link tới `feature_documentation.md`](./feature_documentation.md)

## 4. Chỉ số Thiết lập (Metrics)
# TODO(author): Metrics nào là thước đo chính của model này (VD: F1 Score, Recall, AUC-ROC)? Tại sao chọn metric đó?
- **Precision:** Chúng ta có chấp nhận báo động giả (False Positive) nhiều để đảm bảo bắt trọn rủi ro không?
- **Recall:** Tỉ lệ phát hiện thực tế.

## 5. Cảnh báo và Rủi ro Hệ thống (Caveats & Recommendations)
- # TODO(author): Nếu thị trường biến động (VD: đổi gói cước toàn cục), mô hình có bị trôi (Data drift) không? Nên retraining định kỳ bao lâu 1 lần (1 tháng/1 tuần)?
