import os
import requests
from typing import List


def web_search_tavily(query: str, api_key: str, top_k: int = 5) -> List[str]:
    """
    Tìm kiếm web bằng Tavily API, trả về danh sách snippet.
    """
    endpoint = "https://api.tavily.com/search"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"query": query, "num_results": top_k}
    response = requests.get(endpoint, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    snippets = []
    for result in data.get("results", []):
        snippet = result.get("snippet", "")
        url = result.get("url", "")
        snippets.append(f"{snippet}\n(Nguồn: {url})")
    return snippets

if __name__ == "__main__":
    TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    query = "Why did Sirius Black give Harry the Firebolt?"
    if TAVILY_KEY:
        results = web_search_tavily(query, TAVILY_KEY)
        for i, snippet in enumerate(results, 1):
            print(f"[{i}] {snippet}\n---")
    else:
        print("Bạn cần đặt biến môi trường TAVILY_API_KEY cho Tavily API key.")
