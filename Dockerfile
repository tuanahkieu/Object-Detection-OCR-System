# Sử dụng môi trường Python siêu nhẹ
FROM python:3.9-slim

# Đặt thư mục làm việc
WORKDIR /app

# Copy file thư viện và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code của bạn vào (app.py, templates, static, best.pt...)
COPY . .

# Hugging Face Spaces yêu cầu chạy web ở cổng 7860
EXPOSE 7860

# Lệnh khởi động server
CMD ["gunicorn", "-b", "0.0.0.0:7860", "--timeout", "120", "app:app"]