from langchain_core.tools import tool
from ddgs import DDGS

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
    print(f"-> web_search tool is being used for query: '{query}'")
    try:
        with DDGS() as ddgs:
            # Fetch text results from DuckDuckGo
            raw_results = list(ddgs.text(query, max_results=max_results))
            
            if not raw_results:
                return "No search results found for this query."
            
            # Format the output into a clean string for the LLM to read easily
            formatted_results = []
            for item in raw_results:
                formatted_results.append(
                    f"Title: {item.get('title')}\n"
                    f"Link: {item.get('href')}\n"
                    f"Snippet: {item.get('body')}\n"
                    f"---"
                )
            return "\n\n".join(formatted_results)
            
    except Exception as e:
        return f"An error occurred during the search: {str(e)}"
