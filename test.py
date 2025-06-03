import os
import re
import time
from langchain_google_community import GoogleSearchAPIWrapper
from urllib.parse import urlparse
from langchain_community.document_loaders import SeleniumURLLoader
os.environ["GOOGLE_CSE_ID"] = "a5d5e7ccaa08f450e"
os.environ["GOOGLE_API_KEY"] = "AIzaSyBvxun6WN7YRonYOaQ8yEjoJtI18HE2rGA"

search = GoogleSearchAPIWrapper()

def get_top_links(query: str, num_results: int) -> list[str]:
    search = GoogleSearchAPIWrapper()
    results = search.results(query, num_results=num_results)
    filtered_links = [
        item.get("link")
        for item in results
        if item.get("link")
        and not any(domain in item.get("link") for domain in ["youtube.com", "youtu.be", "vimeo.com"])
    ]
    return filtered_links[:num_results]

def url_2txt(url, output_folder):
    start_time = time.time()
    timeout=10
    loader = SeleniumURLLoader([url])
    try:
        doc = loader.load()
        if time.time() - start_time > timeout:
            print(f"Cannot crawl {url} due to time out.")
            return
        page_content = doc[0].page_content
        
        if page_content:
            parsed_url = urlparse(url)
            path = parsed_url.path
            file_name = re.sub(r'\W+', '_', path.split("/")[-1]) + ".txt"

            output_path = os.path.join(output_folder, file_name)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as file:
                file.write(page_content)
            
            print(f"File saved to {output_path}")
        else:
            print("No content found to save.")
    except Exception as e:
        print(f"Error when crawl {url}: {e}")

if __name__ == "__main__":
    query = "Cuộc kháng chiến chống Trung Quốc năm 1979 ?"
    top_links = get_top_links(query, 3)
    output_folder = "/home/vanh/chatbot_fpt/output_folder"

    print("Top 3 links:")
    for link in top_links:
        print(link)

    for link in top_links:
        print(f"Crawling {link} ...")
        url_2txt(link, output_folder)