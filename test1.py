import requests
from bs4 import BeautifulSoup
import re
import json

def get_search_results(url, max_results=2):
    response = requests.get(url, timeout=10)
    results = response.json()
    valid_results = []
    if 'items' in results:
        for item in results['items']:
            link = item.get('link')
            if not link:
                continue
            video_domains = [
                ".pdf", "youtube.com", "youtu.be", "vimeo.com",
                "facebook.com/watch", "dailymotion.com", "tiktok.com", "zingmp3.vn/video"
            ]
            if link.lower().endswith('.pdf') or any(domain in link.lower() for domain in video_domains):
                continue
            try:
                page = requests.get(link, timeout=10)
                soup = BeautifulSoup(page.content, 'html.parser')

                content = []
                for tag in soup.find_all(['p', 'div', 'span']):
                    text = tag.get_text(strip=True)
                    if text:
                        content.append(text)
                if not content:
                    continue
                print(f"Crawled: {link}")
                res = "\n".join(content)
                if not re.search(r'[a-zA-Z]', res):
                    continue

                valid_results.append((link, res))
                if len(valid_results) >= max_results:
                    break

            except Exception as e:
                print(f"[Error] Không thể crawl {link}: {e}")
                continue
        return valid_results

    else:
        print("[WARN] Không có mục 'items' trong JSON.")
        return []

if __name__ == "__main__":
    API_KEY = 'AIzaSyBvxun6WN7YRonYOaQ8yEjoJtI18HE2rGA'
    SEARCH_ENGINE_ID = 'a136a79f27a334484'
    query = "Cuộc chiến tranh biên giới Việt Trung diễn ra khi nào?"
    url = f'https://www.googleapis.com/customsearch/v1?key={API_KEY}&cx={SEARCH_ENGINE_ID}&q={query}&lr=lang_vi'

    results = get_search_results(url, max_results=2)
