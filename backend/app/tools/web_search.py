import os
from tavily import AsyncTavilyClient

WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Searches for up-to-date information, news, trends, and facts on the Internet. Returns clean content from top pages.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Precise and concise search query. Use keywords."
                }
            },
            "required": ["query"]
        }
    }
}


async def web_search(query: str, **kwargs) -> str:
    """
    Асинхронно виконує пошук через Tavily.
    Усі винятки (відсутність ключа, мережеві помилки) прокидаються нагору до викликаючого коду.
    """
    api_key = os.environ.get("TAVILY_API_KEY")

    if not api_key:
        raise ValueError("TAVILY_API_KEY is not set in the environment variables.")

    client = AsyncTavilyClient(api_key=api_key)

    response = await client.search(
        query=query,
        search_depth="advanced",
        max_results=3
    )

    results = response.get("results", [])
    if not results:
        return f"No results found for query: '{query}'."

    formatted_results = []
    for item in results:
        formatted_results.append(f"Source: {item.get('url')}\nContent: {item.get('content')}")

    return "\n\n---\n\n".join(formatted_results)