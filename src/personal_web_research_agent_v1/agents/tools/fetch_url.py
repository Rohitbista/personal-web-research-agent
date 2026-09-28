import re
import time
import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from personal_web_research_agent_v1.logging.logger_service import LoggerService

logger = LoggerService.get_instance()
_CTX = "src/agents/tools/fetch_url"


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
    #print(f"🌐 Fetching: {url}")

    logger.info(
        "fetch_url_content started",
        context=_CTX,
        data={"url": url, "max_chars": max_chars},
    )

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}

        start = time.monotonic()
        resp = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)

        resp.raise_for_status()

        logger.log_api_call(
            source="http",
            status=True,
            request={"url": url, "method": "GET"},
            response={
                "status_code": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "content_length": len(resp.text),
            },
            response_time_ms=str(elapsed_ms),
            message="fetch_url_content HTTP GET",
        )

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()

        truncated = text[:max_chars]
        suffix = "..." if len(text) > max_chars else ""

        logger.info(
            "fetch_url_content completed",
            context=_CTX,
            data={
                "url":            url,
                "raw_chars":      len(text),
                "returned_chars": len(truncated),
                "truncated":      bool(suffix),
            },
        )

        return f"[Source: {url}]\n\n{truncated}{suffix}"

    except Exception as exc:
        logger.error(
            "fetch_url_content failed",
            context=_CTX,
            data={"url": url, "error": str(exc)},
        )
        return f"Error fetching {url}: {exc}"