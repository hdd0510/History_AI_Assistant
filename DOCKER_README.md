# History AI Assistant - Docker Setup

Hướng dẫn chạy ứng dụng History AI Assistant bằng Docker.

## Yêu cầu hệ thống

- Docker
- Docker Compose
- Ít nhất 4GB RAM
- 10GB dung lượng ổ cứng trống

## Cấu hình trước khi chạy

### 1. Tạo file .env

Copy file `env.example` thành `.env` và cấu hình:

```bash
cp env.example .env
```

Sau đó chỉnh sửa file `.env`:

```env
# Google API Configuration
GOOGLE_API_KEY=your_actual_google_api_key_here
GOOGLE_CSE_ID=your_actual_google_cse_id_here

# MongoDB Configuration (optional)
MONGO_URI=mongodb://admin:password123@mongodb:27017
```

### 2. Lấy Google API Key và CSE ID

1. **Google API Key**: 
   - Truy cập [Google Cloud Console](https://console.cloud.google.com/)
   - Tạo project mới hoặc chọn project có sẵn
   - Enable Google Custom Search API và Google Generative AI API
   - Tạo API key trong Credentials

2. **Google Custom Search Engine ID (CSE ID)**:
   - Truy cập [Google Custom Search](https://cse.google.com/)
   - Tạo search engine mới
   - Copy Search Engine ID

## Cách chạy

### 1. Sử dụng Docker Compose (Khuyến nghị)

```bash
# Build và chạy tất cả services
docker-compose up -d

# Xem logs
docker-compose logs -f app

# Dừng services
docker-compose down
```

### 2. Sử dụng Docker trực tiếp

```bash
# Build image
docker build -t history-ai-assistant .

# Chạy container với MongoDB
docker run -d --name mongodb \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=password123 \
  mongo:7.0

# Chạy ứng dụng
docker run -d --name history-ai-app \
  -p 8000:8000 \
  -e GOOGLE_API_KEY=your_google_api_key \
  -e GOOGLE_CSE_ID=your_google_cse_id \
  -e MONGO_URI=mongodb://admin:password123@host.docker.internal:27017 \
  --link mongodb \
  history-ai-assistant
```

## Truy cập ứng dụng

- **API Documentation**: http://localhost:9000/docs
- **ReDoc**: http://localhost:9000/redoc
- **Health Check**: http://localhost:9000/health

## Các endpoints chính

- `POST /chat` - Gửi tin nhắn chat
- `GET /chat-history/{user_id}/{thread_id}` - Lấy lịch sử chat
- `GET /docs` - API documentation

## Troubleshooting

### 1. Lỗi kết nối MongoDB
```bash
# Kiểm tra MongoDB container
docker-compose logs mongodb

# Restart MongoDB
docker-compose restart mongodb
```

### 2. Lỗi Google API
- Kiểm tra `GOOGLE_API_KEY` có hợp lệ không
- Đảm bảo API key có quyền truy cập Google GenAI và Custom Search API
- Kiểm tra `GOOGLE_CSE_ID` có đúng không

### 3. Lỗi port đã được sử dụng
```bash
# Kiểm tra port đang sử dụng
netstat -tulpn | grep 9000

# Thay đổi port trong docker-compose.yml
ports:
  - "9001:9000"  # Thay đổi từ 9000 thành 9001
```

### 4. Lỗi ModuleNotFoundError
```bash
# Rebuild image nếu có thay đổi requirements.txt
docker-compose build --no-cache

# Restart containers
docker-compose down && docker-compose up -d
```

## Backup và Restore

### Backup MongoDB
```bash
docker exec mongodb mongodump --out /data/backup
docker cp mongodb:/data/backup ./backup
```

### Restore MongoDB
```bash
docker cp ./backup mongodb:/data/
docker exec mongodb mongorestore /data/backup
```

## Monitoring

```bash
# Xem resource usage
docker stats

# Xem logs real-time
docker-compose logs -f

# Kiểm tra health status
docker-compose ps
```

## Cleanup

```bash
# Dừng và xóa containers
docker-compose down

# Xóa volumes (cẩn thận - sẽ mất data)
docker-compose down -v

# Xóa images
docker rmi history-ai-assistant
``` 