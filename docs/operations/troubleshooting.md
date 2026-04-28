# Cẩm nang Xử lý Sự cố (Troubleshooting Guide)

> [!NOTE]
> Tài liệu này liệt kê các lỗi thường gặp trong quá trình vận hành pipeline Churn Prediction và cách khắc phục nhanh.

## 1. ETL/Ingestion Pipeline
### Lỗi: Không thể kéo dữ liệu (Connection Refused)
- **Dấu hiệu:** `# TODO(author): Ví dụ DAG IngestionTask bị đỏ (fail).`
- **Nguyên nhân có thể:** `# TODO(author): Ví dụ sai Credentials DB CSKH, hoặc bị chặn Firewall.`
- **Cách xử lý:** `# TODO(author): Check Secrets trên K8s, VPN...`

### Lỗi: Thiếu dữ liệu (Missing Data)
- **Dấu hiệu:** `SchemaMismatch` hoặc `DataQualityError`.
- **Cách xử lý:** `# TODO(author): Báo cho team DBA hoặc bypass check nếu được duyệt.`

## 2. API / Inference
### Lỗi: Pod CrashLoopBackOff (Hết RAM / OOMKilled)
- **Dấu hiệu:** `/health` endpoint báo timeout 502/504 Bad Gateway. Grafana báo Memory Limit Exceeded.
- **Cách xử lý:** `# TODO(author): Nâng Limit/Request trên Helm, Restart Pod.`

### Lỗi: Dự đoán không nhất quán (Model Drift Warning)
- **Dấu hiệu:** Tỉ lệ Churn dự đoán đột ngột chênh lệc 5x so với quá khứ.
- **Cách xử lý:** `# TODO(author): Thu thập data gần nhất, chạy Retraining Pipeline thủ công, verify trước khi đẩy model lên Production.`

## 3. Kubernetes Deployment & Airflow Helm
### Lỗi: `invalid mode: /churn_data` khi mount volume trên Docker Desktop Windows
- **Dấu hiệu:** Kubernetes Pod Operator báo lỗi tạo Container. Nguyên nhân do mount data bằng `host_path` có chứa `D:\...`. Docker cắt lấy chuỗi `:` làm parameter mode nên báo lỗi.
- **Cách xử lý:** Không dùng format ổ Windows. Đổi `host_path` sang chuẩn mount ngầm của Docker Desktop Virtual Machine: `/run/desktop/mnt/host/d/Churn_Prediction_Product/...`

### Lỗi: Airflow Webserver không đọc được log (NameResolutionError / Failed to resolve)
- **Dấu hiệu:** UI báo `Max retries exceeded with url... Failed to resolve '[worker-pod-name]'`. Hiện tượng này diễn ra khi Airflow dùng `KubernetesExecutor`.
- **Nguyên nhân:** Khi 1 task kết thúc, Worker Pod đó bị K8s xóa. Trong khi chạy local, hệ thống lại chưa có kho chứa Log riêng nên Webserver mò tìm vào đúng cái IP của Pod đã biến mất.
- **Cách xử lý:** Phải sửa cấu hình Helm (`values-local.yaml`) bật Persistent Volume cho Log (`logs.persistence.enabled: true`).

### Lỗi: KPO báo `Missing required environment variables: PG_USER and PG_PW`
- **Dấu hiệu:** Task Ingest / Pipeline thất bại ngay từ giây đầu tiên vì không gọi được Database.
- **Nguyên nhân:** DAG gọi KPO pod ra là một container mới hoàn toàn (trống rỗng), không có `.env` file bên cạnh như chạy local script.
- **Cách xử lý:** Khởi tạo DB Crentials thành 1 cái Secrets trong cụm K8s (`kubectl create secret generic churn-db-secret --from-env-file=".env"`). Xong xuôi, tại KubernetesPodOperator, inject secret đố vào Pod = `env_from=[k8s.V1EnvFromSource(secret_ref=...)]`. 

### Lỗi: UPGRADE FAILED: `cannot patch ... with kind StatefulSet ... fields other than ... are forbidden`
- **Dấu hiệu:** Terminal báo lỗi đỏ chót từ chối khi gõ `helm upgrade`, đặc biệt nếu vừa mới bật ổ cứng Volumes Persistence cho StatefulSets (vd: `airflow-triggerer`).
- **Nguyên nhân:** Thiết kế chuẩn của K8s không cho phép tự ý cấp phát Volumes đè vào các StatefulSets đang chạy sống.
- **Cách xử lý:** Reset cái StatefulSets đang kẹt (ví dụ: `kubectl delete statefulset airflow-triggerer -n default`) và chạy lại `helm upgrade` là xong. Bộ sinh Pod sẽ rà soát và cấu hình Volume mới mượt mà.

## 4. Monitoring & Grafana (Môi trường Local Docker Desktop)
### Lỗi: Dashboard Grafana có báo Request/Limit nhưng báo "No data" ở biểu đồ tài nguyên thực tế (CPU/Memory Utilisation)
- **Dấu hiệu:** Trên Grafana, bảng `Kubernetes / Compute Resources / Namespace (Pods)` hiển thị trống trơn các biểu đồ dạng đường, trong khi cột Limit và Quota vẫn có số.
- **Nguyên nhân:** 
  1. Kubelet mặc định chặn Prometheus scrape dữ liệu do lỗi chứng chỉ tự ký (self-signed).
  2. Dù Prometheus vượt qua bảo mật (bằng cách chỉnh `insecureSkipVerify: true` trong Helm values), **Docker Desktop có giới hạn cố hữu**: Kubelet (chạy cAdvisor) của nó chỉ xuất metrics cấp độ "Pod", chứ KHÔNG có metric cấp độ "Container". Nhãn (label) `container` bị bỏ trống.
  3. Dashboard mặc định của cộng đồng lại dùng câu lệnh PromQL bắt buộc nhóm theo nhãn `container` (ví dụ: `sum by (pod, container)`). Vì tìm không ra nhãn này, nó báo lỗi "No data".
- **Cách xử lý:**
  Đây là giới hạn thuần túy của giả lập Local, lên Production thật sẽ không bị. Để phục vụ việc theo dõi ở Local, hãy ấn vào menu **Explore** (la bàn) trên Grafana và gõ các câu lệnh tuỳ chỉnh không cần nhãn `container`.
  
  *Ví dụ các câu lệnh PromQL dùng cho Docker Desktop:*
  - Theo dõi RAM tổng của toán bộ Pipeline Churn:
    ```promql
    sum(container_memory_usage_bytes{pod=~"churn-pipeline-.*"}) by (pod)
    ```
  - Theo dõi CPU của toàn bộ namespace mặc định:
    ```promql
    sum(irate(container_cpu_usage_seconds_total{namespace="default"}[5m])) by (pod)
    ```
