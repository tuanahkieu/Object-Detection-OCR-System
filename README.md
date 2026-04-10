---
title: Object Detection OCR System
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Hệ thống Nhận diện và Xử lý OCR Bản vẽ Kỹ thuật

Hệ thống được thiết kế để tự động nhận diện các thành phần trong bản vẽ kỹ thuật (PartDrawing, Note, Table), cắt rời các vùng (crop), và thực thi bóc tách văn bản (OCR) nhằm phân tích thiết kế một cách nhanh chóng và chính xác.

## Đặc điểm nổi bật
* **Object Detection Interface:** Ứng dụng mô hình **RT-DETR** tiên tiến (phiên bản không sử dụng YOLO để đảm bảo tính thương mại), được tinh chỉnh để nhận diện tốt 3 cấu phần quan trọng của bản vẽ kỹ thuật.
* **Smart OCR Pipeline:** Tích hợp **EasyOCR** đi kèm một pipeline tiền xử lý ảnh mạnh mẽ (Denoising, Otsu Threshold, Cubic Interpolation) để đảm bảo chất lượng hình ảnh tốt nhất giống hệt bản scan trước khi đưa vào bộ đọc.
* **Table Structure Recognition:** Thuật toán hậu kiểm kết quả của EasyOCR giúp tự động gom và dựng rập khuôn (Row/Column mapping) đặc thù cho các dữ liệu nhạy cảm với cấu trúc tọa độ như Table.
* **Clean Data Export:** Cho phép xuất chuỗi phân tích dưới định dạng theo đúng JSON Requirement Standard và lưu trữ trích xuất các vật thể (crops) dưới hình ảnh cục bộ độc lập.

---

## 📸 Giao diện ứng dụng (Web Demo)
Hệ thống sử dụng **Flask + HTML Vanilla** giúp triển khai giao diện theo chiều hướng nhẹ nhất, load nhanh và không lưu trữ file dư thừa.

| ![Screenshot](static/placeholder.jpg) |
|:--:|
| Hiển thị trực quan dữ liệu phân tích |

---

## 🛠️ Hướng dẫn cài đặt & Chạy dưới local
Hệ thống được phát triển trên Python 3.9+. Trước khi bắt đầu, hãy đảm bảo bạn có cài đặt đầy đủ Python và pip.

### Bước 1. Cài đặt các thư viện
Clone repo này xuống và chạy:
```bash
pip install -r requirements.txt
```

### Bước 2. Cấu hình mô hình
1. Do dung lượng tải lớn, weights của model (`best.pt`) đã được cung cấp trực tiếp vào trong source hoặc tải về qua link Google Drive (nếu có).
2. Đặt model `best.pt` vào thư mục gốc của project ngang hàng với `app.py`.

### Bước 3. Khởi động dịch vụ Server
```bash
python app.py
```
* Server sẽ tự động chạy trên địa chỉ `http://0.0.0.0:5002`.
* Mở trình duyệt và truy cập `http://localhost:5002` để trải nghiệm ứng dụng.

---

## 🚀 Triển khai lên Hugging Face Spaces
Dự án đã được cấu hình sẵn môi trường dành riêng cho chuẩn triển khai của Hugging Face (sử dụng Docker).

1. Truy cập **Hugging Face > Mở tab Spaces > Chọn Create new Space**.
2. Nhập **Space name**, chọn Space SDK là **Docker** nằm ở dưới cùng.
3. Liên kết Git, Push toàn bộ thư mục local này lên repo đó hoặc tải lên trực tiếp.
4. Hugging Face sẽ tự động clone repo, nhận diện tệp `Dockerfile` thiết lập user non-root ở cổng `7860` và tiến hành Build Container.
5. Quá trình chạy có thể mất một vài phút tùy vào quá trình cài đặt Pytorch CPU + EasyOCR. Sau khi trạng thái chuyển sang **Running** thì bạn có thể cung cấp đường dẫn cho mọi người trực tiếp dùng thử!

---

## 📊 Phương pháp tiếp cận (Methodology)

### 1. Object Detection (RT-DETR)
Để thỏa mãn điều kiện cấp phép thương mại hóa và không bị giới hạn bản quyền YOLO, mình đã sử dụng **RT-DETR (Real-Time DEtection TRansformer)** - Model do Baidu phát triển có khả năng tracking tốt với các hộp neo tọa độ (anchor boxes) trên nền trắng đen như bản vẽ.

### 2. OCR Pre-Processing (Xử lý tiền OCR)
Bản vẽ chụp thường bị rỗ hạt, không đều sáng. Hệ thống sẽ:
1. `cvtColor` chuyển xám.
2. `cv2.resize` nhân 2.5 lần kích thước dùng thuật toán nội suy CUBIC giúp chữ có nét cong đẹp hơn.
3. `fastNlMeansDenoising` khử nhiễu rỗ của giấy.
4. `threshold + OTSU` tự động nhị phân hóa biến hình ảnh thành bản phân màu 255 (trắng tinh) & 0 (đen tinh).

### 3. Thuật toán cấu trúc Bảng (Row-Col grouping)
Thay vì dùng thư viện nặng như `img2table`, mình can thiệp bằng tọa độ Boxes đầu ra `detail=1` của EasyOCR:
* Sắp xếp toàn bộ dữ liệu quét dựa trên Tọa độ $Y$ trung tâm.
* Quét qua các dòng, gom cụm (cluster) những text nằm trên cùng 1 trục $Y$ thông qua sai số độ lệnh $\epsilon \approx 20px$.
* Ở mỗi Row đã được gom, tiến hành sort các đoạn text theo chiều trục $X$ để định hình Cột. Kết quả được join với separator ` | `.

### 4. Ghi nhận Output Crop Folder & Dữ liệu đầu ra 
Hệ thống tự nhận biết và lưu file crop theo template: `{tên_ảnh}_{tên_class}_{id}.jpg` tại thư mục `/uploads/crops`. Kết quả tải về cho người dùng dưới định dạng JSON gốc.

---

*Contact: Tuan Anh (tuankieu@example.com - Update if needed)*