# Sử dụng Python 3.11 làm base image
FROM python:3.11-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài đặt các dependencies hệ thống cần thiết
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements trước để tận dụng Docker cache
COPY src/requirements.txt .

# Cài đặt Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code
COPY src/ ./src/
COPY vanh_draft/ ./vanh_draft/

# Tạo thư mục logs nếu cần
RUN mkdir -p /app/logs

# Expose port mà FastAPI sẽ chạy
EXPOSE 9000

# Thiết lập biến môi trường
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9000/health || exit 1

# Command để chạy ứng dụng
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "9000", "--reload"] 