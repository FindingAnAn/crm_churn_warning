# Luồng Dữ Liệu (Data Flow)

> [!NOTE]
> Tài liệu này định nghĩa chi tiết cách dữ liệu chảy từ khi được sinh ra/thu thập cho đến khi tạo ra được file dự đoán (predictions) hoặc model artifacts.

## 1. Vòng đời Dữ liệu Tổng quát (High-level Data Lifecycle)

# TODO(author): Bổ sung sơ đồ Mermaid dạng flowchart mô tả tổng quan (ví dụ: Raw -> Cleaned -> Features -> Train/Test -> Model -> Inference).

```mermaid
flowchart TD
    A[Raw Data (Zip/CSV)] --> B(Ingestion Pipeline)
    B --> C[(Validated Data)]
    C --> D(Feature Engineering Pipeline)
    D --> E[(Feature Store / Parquet)]
    E --> F{Model Training Pipeline}
    F -->|Artifacts| G(MLflow Registry)
    E --> H{Inference Pipeline}
    H --> I[(Predictions DB)]
```

## 2. Chi tiết từng giai đoạn (Stage details)

### 2.1. Ingestion (Thu thập)
# TODO(author): Dữ liệu từ CSKH lấy theo định dạng nào? Lưu vào đâu? Ai trigger? Nếu có lỗi file (schema mismatch) xử lý thế nào?

### 2.2. Preprocessing & Feature Engineering
# TODO(author): Giải thích quá trình làm sạch. Đặc trưng tính theo công thức nào (Window nào? Cửa sổ xoay ra sao?).

### 2.3. Model Training Data
# TODO(author): Chiến lược chia tập Train/Test (Thời gian - Time-based split hay Random split?). 

### 2.4. Inference (Sinh điểm dự đoán)
# TODO(author): Chạy định kỳ (Batch daily/weekly) hay Realtime? Dữ liệu đầu ra format là gì, lưu về bảng/file nào để đội CSKH lấy?

## 3. Chính sách làm sạch/Xóa dữ liệu (Data Retention)
# TODO(author): Giữ file Raw bao lâu? (vd: 30 ngày) Models cũ giữ bao lâu?
