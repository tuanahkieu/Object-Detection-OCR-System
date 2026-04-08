# Sử dụng môi trường Python siêu nhẹ
FROM python:3.9-slim

# Đặt thư mục làm việc
WORKDIR /app

# Cài đặt các thư viện lõi của hệ điều hành Linux dành cho OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy file requirements và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code của bạn vào
COPY . .

# Mở cổng 7860
EXPOSE 7860

# Lệnh khởi động server
CMD ["gunicorn", "-b", "0.0.0.0:7860", "--timeout", "120", "app:app"]