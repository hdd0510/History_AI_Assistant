# Gemini History Chatbot

Một chatbot sử dụng Gemini pro của Google để cung cấp thông tin lịch sử, tạo câu đố và tìm kiếm hình ảnh lịch sử.

## Yêu cầu hệ thống

- Python 3.8+
- Các thư viện trong file `src/requirements.txt`
- API key của Google (GOOGLE_API_KEY)
- Custom Search Engine ID (GOOGLE_CSE_ID)

## Cài đặt

1. Clone repository và cài đặt các thư viện:

```bash
pip install -r src/requirements.txt
```

2. Tạo file `.env` trong thư mục gốc với các biến môi trường sau:

```
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_custom_search_engine_id
```

## Sử dụng CLI test

Để tương tác với chatbot qua CLI, bạn có thể sử dụng file `cli_test.py`:

### Chế độ tương tác

```bash
python cli_test.py
```

Trong chế độ này, bạn có thể nhập tin nhắn và nhận phản hồi từ chatbot. Để thoát, nhập `exit`, `quit`, `q`, hoặc `bye`.

### Sử dụng ID phiên đã có

Để tiếp tục cuộc hội thoại từ một phiên trước đó:

```bash
python cli_test.py --session YOUR_SESSION_ID
```

### Chế độ không tương tác (đơn tin nhắn)

Để gửi một tin nhắn đơn và nhận phản hồi:

```bash
python cli_test.py --message "Tin nhắn của bạn"
```

## Các loại câu hỏi hỗ trợ

Chatbot được thiết kế để xử lý các loại yêu cầu khác nhau:

1. **Tìm kiếm thông tin lịch sử**: 
   - "Ai là Lý Thái Tổ?"
   - "Kể về sự kiện Điện Biên Phủ"

2. **Tìm kiếm hình ảnh lịch sử**:
   - "Cho tôi xem hình ảnh về Hoàng thành Thăng Long"
   - "Tìm bản đồ cổ của Việt Nam"

3. **Tạo câu đố lịch sử**:
   - "Tạo câu đố về Hai Bà Trưng"
   - "Cho tôi trắc nghiệm về thời kỳ Đông Sơn"

## Cấu trúc dự án

- `src/app.py`: API FastAPI cho chatbot
- `src/langgraph/`: Định nghĩa đồ thị agent và các node
- `src/tools/`: Các công cụ tìm kiếm và tạo câu đố
- `src/memory/`: Quản lý bộ nhớ phiên
- `cli_test.py`: Công cụ CLI để test chatbot 