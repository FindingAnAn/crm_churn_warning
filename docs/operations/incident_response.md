# Quy trình Ứng phó Sự cố (Incident Response)

> [!IMPORTANT]
> Tài liệu này dành cho On-call Engineer khi có P1/P2 Incident.

## 1. Phân loại mức độ (Severity)
- **P1 (Critical):** Hệ thống không thể dự đoán, ảnh hưởng trực tiếp đến người dùng cuối. 
- **P2 (Major):** Pipeline tính toán chậm, dữ liệu bị sai khác lớn, model có vấn đề.
- **P3 (Minor):** Lỗi warning, hệ thống dự phòng vẫn chạy.

## 2. Quy trình (Step-by-step Runbook)
1. **Triage (Đánh giá):** # TODO(author): Ai tiếp nhận? Xác nhận sơ bộ ảnh hưởng.
2. **Mitigation (Khắc phục tạm thời):** # TODO(author): Dừng tính năng hay Rollback model cũ gần nhất? (Lệnh: `...`)
3. **Resolution (Khắc phục triệt để):** # TODO(author): Sửa lỗi code / Pipeline và apply CI/CD.
4. **Post-mortem:** Bắt buộc viết lại báo cáo nguyên nhân cốt lõi (RCA) sau khi P1/P2 đóng.
