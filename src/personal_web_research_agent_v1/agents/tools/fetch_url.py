import re
import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool


@tool
def fetch_url_content(url: str, max_chars: int = 4000) -> str:
    """
    Fetches the full readable text from a webpage URL.
    Use this after web_search to get complete information from a promising page —
    search snippets are often too short to be useful.

    Args:
        url:       The URL to fetch.
        max_chars: Maximum characters to return (default 4000).
    """
    print(f"🌐 Fetching: {url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
        resp = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()

        truncated = text[:max_chars]
        suffix = "..." if len(text) > max_chars else ""
        return f"[Source: {url}]\n\n{truncated}{suffix}"

    except Exception as exc:
        return f"Error fetching {url}: {exc}"