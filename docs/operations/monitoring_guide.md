# Cẩm nang Giám sát Hệ thống (Observability & Monitoring Guide)

Tài liệu này là "Kim chỉ nam" cho team Vận hành (DataOps/Sysadmin) trong việc theo dõi luồng Machine Learning (đặc biệt là XGBoost) và sức khoẻ của cụm Kubernetes (K8s).

## 1. Cấu trúc Mạng lưới & Cổng truy cập (Port Mapping)

Hệ thống được thiết kế theo chuẩn phân tách Microservices, mỗi thành phần đảm nhiệm một đầu việc đặc thù, sở hữu cổng (Port) và không gian (Namespace) riêng:

| Dịch vụ | Chức năng cốt lõi | Namespace K8s | Port nội bộ | Lệnh Port-forward truy cập (PowerShell) |
| :--- | :--- | :--- | :--- | :--- |
| **Airflow Web UI** | Quản lý / Trigger Task, xem Log | `default` | `8080/TCP` | `kubectl port-forward svc/airflow-api-server 8080:8080 -n default` |
| **Grafana UI** | Giao diện Vẽ Biểu đồ (Mắt thần) | `monitoring` | `80/TCP` | `kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring` *(User: admin/dmst_ai)* |
| **Prometheus DB** | Lưu trữ số liệu thô (Metrics) / Test PromQL | `monitoring` | `9090/TCP` | `kubectl port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090 -n monitoring` |

---

## 2. Cài đặt Hệ thống Mắt Thần (Kube-Prometheus-Stack)

Để theo dõi, hệ thống bắt buộc cần cài đặt bộ `kube-prometheus-stack` của cộng đồng (chứa đầy đủ Node Exporter, Grafana, và Prometheus). Nếu bạn bắt đầu với máy ảo Server trống, chạy các lệnh sau:

```bash
# 1. Thêm kho thư viện Helm của Prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 2. Cài đặt ngăn xếp giám sát lên K8s
# (Cần chuẩn bị sẵn file `values.yaml` ở thư mục dự án để ghi đè, tắt Alertmanager HA cho nhẹ máy)
.\helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  -f infrastructure/helm/monitoring/values.yaml
```

---

## 3. Hệ Sinh Thái Dashboard (Phân Tích Bố Cục)

Khi truy cập vào Grafana, hệ thống sẽ tự động sinh ra một Catalog đầy đủ của `kubernetes-mixin` và `node-exporter-mixin`. Dưới đây là từ điển diễn giải cụ thể cho toàn bộ list:

### Khối Giám Sát Cấu Trúc Vật Lý / Ảo (Node Exporter)
Dành cho Sysadmin quản lý tài nguyên máy ảo:
- **Node Exporter / Nodes (⭐ QUAN TRỌNG):** Dashboard "nhìn phát biết luôn" sinh tử của Máy ảo. Phản ánh RAM rảnh rỗi, Load Average CPU, và % Disk (Hết ổ cứng là lỗi vỡ tổ phổ biến nhất của Data Pipeline).
- **Node Exporter / USE Method / Node:** Phân tích độ nghẽn thắt cổ chai (Utilization - Saturation - Errors).
- **Node Exporter / USE Method / Cluster:** Giống như Node nhưng tổng hợp cho tất cả các máy chủ trong cụm K8s.
- `Node Exporter / AIX` và `MacOS`: Bỏ qua nếu chạy Linux.

### Khối Giám Sát Lõi Kubernetes Control Plane
Dành cho DevOps tìm lỗi K8s API hay Scheduler:
- **Kubernetes / API server:** Số liệu request vào não bộ K8s.
- **Kubernetes / Controller Manager:** Health của bộ điều khiển lõi.
- **Kubernetes / Kubelet:** Health của agent chạy trên từng Node máy tính.
- **Kubernetes / Scheduler:** Tốc độ tìm Node trống để bơm Task Airflow vào.
- **Kubernetes / Proxy:** Giám sát mạng nội bộ K8s.
*=> Khối này hiếm khi người làm DataOps cần đụng vào!*

### Khối Giám Sát Ứng dụng & Luồng Data (Tầng Compute Resources)
Dành cho bạn - Nhóm Kỹ sư Dữ liệu tối ưu Airflow và XGBoost:
- **Kubernetes / Compute Resources / Namespace (Pods) (⭐ KİM CHỈ NAM):** Nắm bắt toàn cảnh sự bào mòn tài nguyên của "đại bản doanh" Airflow. Lọc góc trái từ `namespace=All` thành `namespace=default` để check độ "ngốn" cấu hình của dự án mình.
- **Kubernetes / Compute Resources / Pod (⭐ PHẪU THUẬT ML TASK):** Check "kính hiển vi" vào một task cụ thể. Khi XGBoost (File `monthly_v2_cli`) chạy lúc nửa đêm ngốn bao nhiêu Memory, dashboard này sẽ hiển thị tường tận.
- **Hàng loạt các bảng Network / Computing khác (Workload, Cluster, Persistent Volumes):** Rất đa mục đích để kiểm tra dung lượng ổ đĩa của Log hay băng thông tải file CSV.

---

## 4. Chiến lược "Trực gác" - Khi nào nên can thiệp?

Đội làm DataOps sẽ cần hình thành các cột mốc đèn báo đỏ để cứu nguy hệ thống (Tùy chỉnh thông báo ở màn Grafana Alerting):

| Tín Hiệu (Màn hình Dashboard) | Phán Đoán (Bệnh Lí) | Hành Động Can Thiệp Nhanh (Intervention) |
| :--- | :--- | :--- |
| **Node Exporter / Nodes:** Ổ cứng khả dụng xuống dưới `15%`. | Log Error của Airflow hoặc Model Cache Pickles (`/data/saved/`) tích tụ không được dọn dẹp. | Trigger ngay cái DAG `ds_churn_housekeeping` để xóa cache cũ. Kéo dung lượng PVC (Persistent Virtual Claim) của Logs. |
| **Compute Resources / Pod:** Nửa đêm, Memory của Pod KPO XGBoost nhảy lên quá mốc Request Memory cài sẵn chạm mức Limit vạch màu cam. | Thuật toán quá phức tạp hoặc dữ liệu `cas_customer` tháng đó phình to gấp đôi. | Can thiệp bằng cách tăng `resources.requests.memory` cho Worker Pods ở biểu mẫu Helm Airflow. |
| **Airflow Web UI:** Báo Pod bị kẹt ở trạng thái `Pending` kéo dài 30 phút. | K8s Cluster đã bị hút cạn Memory, không còn Node trống để nhét Pod Airflow vào. | Tạm dừng các luồng Ingest phụ trợ. Checkout Grafana để xem Pod nào đang "ăn" nhiều nhất. Nếu cần phải scale scale-up (Tăng cường RAM vật lý cho VM). |

---

## 5. Từ Điển PromQL (Truy vấn hệ thống Churn Prediction)

Thỉnh thoảng, bạn không cần nhìn hình, bạn chỉ muốn test thuật toán query trực tiếp trên Prometheus (Port 9090) hay cài chuông báo động. Dưới đây là các câu SQL (PromQL) "chân ái" của ngành:

### Q1: Bắt lỗi Pod KPO bị nghẽn cỏ lùi (Pod Crash / Pending)
```promql
kube_pod_status_phase{namespace="default", phase=~"Failed|Pending"} > 0
```
- **Tại sao dùng:** Khi K8sPodOperator chạy xong là biến mất. Nếu tìm ra Pod mang danh "Pending" hoặc "Failed" thì có luồng nào đó (Ingest, Modeling) đang bị lỗi code Python, sập container hoặc hết RAM kẹt không gỡ được. 
- **Khi nào dùng:** Set thành Alert gửi về Slack hàng ngày.

### Q2: Soi Độ Tham Ăn Của XGBoost
```promql
sum(container_memory_usage_bytes{namespace="default", pod=~"churn-pipeline-.*"}) by (pod)
```
- **Tại sao dùng:** Câu lệnh thần thánh rà quét tất cả các Pod tên bắt đầu bằng `churn-pipeline-v2...`. Nhờ nó, bạn tính được dung lượng RAM trung bình thuật toán cần xài mỗi lần train.
- **Khi nào dùng:** Mở Cổng 9090 Gõ xem thử trước triển khai (sizing estimation) để báo IT sếp sắm máy chủ 16GB hay 32GB RAM thì an toàn.

### Q3: Tín hiệu sống còn của hệ sinh thái (Airflow Health)
```promql
rate(kube_pod_container_status_restarts_total{namespace="default", container="airflow-scheduler"}[10m]) > 0
```
- **Tại sao dùng:** Scheduler là "trái tim" của Airflow. Nếu nó bị khởi động lại liên tục (CrashLoopBackOff) ở 10 phút gần đây, nghĩa là Scheduler đang bị quá tải DAGs hoặc kẹt cấu hình Database (giống đợt chập lỗi DB `.env`).
- **Khi nào dùng:** Khung cảnh khẩn cấp (Emergency Drop). Thấy tín hiệu này là toàn bộ Team Data phải vào cuộc xem log.
