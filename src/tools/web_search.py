import asyncio
import os
import logging
from googleapiclient.discovery import build
import requests
from bs4 import BeautifulSoup
from typing import List, Dict

class BaseSearchTool:
    """
    Lớp cơ sở dùng chung cho các công cụ tìm kiếm qua Google Custom Search.
    """

    def __init__(self, search_type='web', num_results=10):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")
        self.search_type = search_type
        self.num_results = num_results

        if not self.api_key or not self.cse_id:
            raise EnvironmentError("Cần thiết lập GOOGLE_API_KEY và GOOGLE_CSE_ID trong biến môi trường.")

        self.service = build("customsearch", "v1", developerKey=self.api_key)
        self.logger = logging.getLogger(self.__class__.__name__)

    def _search(self, query):
        """
        Thực hiện tìm kiếm với query được cung cấp.
        """
        return self.service.cse().list(
            q=query,
            cx=self.cse_id,
            searchType='image' if self.search_type == 'image' else None,
            num=self.num_results
        ).execute()


class WebSearchTool:
    """
    Web search tool trả về title, URL, snippet và nội dung đầy đủ từ trang web.
    Dùng được trong hệ thống agent có hỗ trợ tool_call.
    """

    name = "web_search"
    description = (
        """Đây là tool tìm kiếm trên internet, bạn có thể sử dụng nó để tìm kiếm thông tin trên internet trong thời gian thực.
        Hãy sử dụng tools websearch khi có các thông tin liên quan đến thời gian, thời sự và các thông tin chưa rõ ràng.
        Với tool web search, hãy thử tìm kiếm trên những trang web lớn như wikipedia, ... (ở loop đầu tiên hãy thêm wikipedia vào query nếu đó là câu hỏi thông tin chính thức, hàn lâm như lịch sử khoa học).
        """
    )

    def __init__(self, num_results=3):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")
        if not self.api_key or not self.cse_id:
            raise EnvironmentError("Cần set GOOGLE_API_KEY và GOOGLE_CSE_ID trong biến môi trường.")

        self.service = build("customsearch", "v1", developerKey=self.api_key)
        self.num_results = num_results
        self.logger = logging.getLogger(self.__class__.__name__)

    def _extract_page_content(self, url: str, max_chars: int = 3000) -> str:
        try:
            resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return f"[Lỗi HTTP {resp.status_code}]"

            soup = BeautifulSoup(resp.text, "html.parser")
            article = soup.find("article")
            content = article.get_text(separator="\n", strip=True) if article else soup.body.get_text(separator="\n", strip=True)
            return content[:max_chars] or "[Không có nội dung khả dụng]"
        except Exception as e:
            return f"[Lỗi khi tải trang: {str(e)}]"

    def _search_sync(self, query: str) -> str:
        try:
            response = self.service.cse().list(q=query, cx=self.cse_id, num=self.num_results).execute()
            items = response.get("items", [])
            if not items:
                return f"Không tìm thấy kết quả nào cho truy vấn: {query}"

            formatted = []
            for i, item in enumerate(items):
                url = item.get("link")
                page_text = self._extract_page_content(url)
                formatted.append(
                    f"Kết quả {i+1}:\n"
                    f"- Tiêu đề: {item.get('title')}\n"
                    f"- URL: {url}\n"
                    f"- Đoạn trích: {item.get('snippet')}\n"
                    f"- Nội dung trang (tóm tắt):\n{page_text}\n"
                )

            return "\n".join(formatted)
        except Exception as e:
            self.logger.error(f"Lỗi trong quá trình tìm kiếm: {e}")
            return f"[Lỗi khi thực hiện tìm kiếm: {str(e)}]"

    async def _async_call(self, query: str) -> Dict[str, str]:
        """
        Phiên bản bất đồng bộ của hàm call
        """
        self.logger.info(f"Tìm kiếm web với query: {query}")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._search_sync, query)
        return {"result": result}

    def __call__(self, query: str) -> Dict[str, str]:
        """
        Hàm được gọi bởi agent, trả về dict {"result": "..."}
        Phiên bản đồng bộ để tương thích với agent không hỗ trợ async
        """
        self.logger.info(f"Tìm kiếm web với query: {query}")
        result = self._search_sync(query)
        return {"result": result}


class ImageSearchTool(BaseSearchTool):
    """
    Tìm kiếm hình ảnh minh họa, bản đồ, chân dung... qua Google Images.
    """

    name = "image_search"
    description = (
        "Tìm kiếm hình ảnh, bản đồ, hoặc các hình liên quan đến chủ đề người dùng yêu cầu."
    )

    def __init__(self):
        super().__init__(search_type='image', num_results=3)

    async def _async_call(self, query: str):
        try:
            response = self._search(query)
            items = response.get("items", [])

            if not items:
                return {"image_urls": [], "error": f"Không tìm thấy hình ảnh nào cho: {query}"}

            return {"image_urls": [item.get("link") for item in items if "link" in item]}
        except Exception as e:
            self.logger.error(f"Lỗi tìm kiếm hình ảnh cho '{query}': {e}")
            return {"image_urls": [], "error": f"Lỗi khi tìm kiếm hình ảnh: {str(e)}"}
            
    def __call__(self, query: str):
        """
        Phiên bản đồng bộ để tương thích với agent không hỗ trợ async
        """
        try:
            response = self._search(query)
            items = response.get("items", [])

            if not items:
                return {"image_urls": [], "error": f"Không tìm thấy hình ảnh nào cho: {query}"}

            return {"image_urls": [item.get("link") for item in items if "link" in item]}
        except Exception as e:
            self.logger.error(f"Lỗi tìm kiếm hình ảnh cho '{query}': {e}")
            return {"image_urls": [], "error": f"Lỗi khi tìm kiếm hình ảnh: {str(e)}"}
