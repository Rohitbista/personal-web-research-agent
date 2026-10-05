import time
from langchain_core.tools import tool
from ddgs import DDGS

from personal_web_research_agent_v1.logging.logger_service import LoggerService

logger = LoggerService.get_instance()
_CTX = "src/agents/tools/web_search_DDG"


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """
    Searches the live internet using DuckDuckGo.
    Use this tool whenever the user asks about current events, real-time data,
    or topics you do not have native knowledge about.

    Args:
        query: The search engine text string to query.
        max_results: The maximum number of snippet results to return (default is 5).
    """
    #print(f"-> web_search tool is being used for query: '{query}'")

    logger.info(
        "web_search started",
        context=_CTX,
        data={"query": query, "max_results": max_results},
    )

    try:
        start = time.monotonic()
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)

        logger.log_api_call(
            source="ddg",
            status=True,
            request={"query": query, "max_results": max_results},
            response={"results_returned": len(raw_results)},
            response_time_ms=str(elapsed_ms),
            message="web_search DDG call",
        )

        if not raw_results:
            logger.info(
                "web_search returned no results",
                context=_CTX,
                data={"query": query},
            )
            return "No search results found for this query."

        formatted_results = []
        for item in raw_results:
            formatted_results.append(
                f"Title: {item.get('title')}\n"
                f"Link: {item.get('href')}\n"
                f"Snippet: {item.get('body')}\n"
                f"---"
            )

        output = "\n\n".join(formatted_results)

        logger.info(
            "web_search completed",
            context=_CTX,
            data={"query": query, "results_count": len(raw_results)},
        )

        return output

    except Exception as e:
        logger.error(
            "web_search failed",
            context=_CTX,
            data={"query": query, "error": str(e)},
        )
        return f"An error occurred during the search: {str(e)}"