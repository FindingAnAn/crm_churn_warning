# Quyết định Kiến trúc (Architecture Decision Records - ADR)

Thư mục này chứa toàn bộ các quyết định kiến trúc quan trọng của dự án Churn Prediction. 
Mỗi quyết định được lưu dưới dạng một file Markdown (ADR) với định dạng và đánh số tiến định.

## Nguyên tắc viết và đặt tên (Naming & Writing Conventions)
Theo tiêu chuẩn tại `15-Documentation_conventions.md` (Điểm 9):
- Nếu quyết định thay đổi công nghệ ảnh hưởng tới toàn bộ hệ thống hoặc thay đổi cấu trúc dữ liệu chính yếu -> **Bắt buộc viết ADR.**
- Định dạng Tên file: `[STT]-[hành-động-ngắn].md`. Ví dụ: `001-switch-to-xgboost.md`, `002-use-helm-for-deploy.md`.
- Trạng thái ADR: Thường là `Proposed`, `Accepted`, `Deprecated` hoặc `Superseded`.

## Mẫu (Template)
Sao chép nội dung file [001-template_ADR.md](./001-template_ADR.md) để bắt đầu một quyết định mới.
