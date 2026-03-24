"""
Tavily Search API integration for web search capabilities.
Provides real-time web search for up-to-date information.
"""
import logging
from typing import List, Optional, Dict, Any
import aiohttp
import asyncio

from django.conf import settings

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


class TavilySearchService:
    """
    Tavily search service for web search integration.
    Used to augment RAG with real-time web information.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Tavily search service.
        
        Args:
            api_key: Tavily API key (defaults to settings.TAVILY_API_KEY)
        """
        self.api_key = api_key or getattr(settings, "TAVILY_API_KEY", None)
        if not self.api_key:
            logger.warning("Tavily API key not configured")

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        include_answer: bool = True,
        include_raw_content: bool = False,
    ) -> Dict[str, Any]:
        """
        Perform a synchronous search.
        
        Args:
            query: Search query
            max_results: Maximum results to return
            search_depth: "basic" or "advanced"
            include_domains: Only search these domains
            exclude_domains: Exclude these domains
            include_answer: Include AI-generated answer
            include_raw_content: Include raw HTML content
            
        Returns:
            Search results dict
        """
        return asyncio.run(self._async_search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
        ))

    async def _async_search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        include_answer: bool = True,
        include_raw_content: bool = False,
    ) -> Dict[str, Any]:
        """Async search implementation."""
        if not self.api_key:
            return {"error": "Tavily API key not configured", "results": []}

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
        }

        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TAVILY_API_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("Tavily API error: %s - %s", response.status, error_text)
                        return {"error": f"API error: {response.status}", "results": []}
                    
                    data = await response.json()
                    return self._format_response(data)

        except asyncio.TimeoutError:
            logger.error("Tavily search timed out")
            return {"error": "Search timed out", "results": []}
        except Exception as e:
            logger.exception("Tavily search failed: %s", e)
            return {"error": str(e), "results": []}

    def _format_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format Tavily response for our use."""
        return {
            "answer": data.get("answer"),
            "results": [
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": item.get("content"),
                    "score": item.get("score"),
                }
                for item in data.get("results", [])
            ],
            "images": data.get("images", []),
        }

    def search_for_context(
        self,
        query: str,
        max_results: int = 3,
    ) -> str:
        """
        Search and format results as context string.
        
        Args:
            query: Search query
            max_results: Maximum results
            
        Returns:
            Formatted context string
        """
        result = self.search(
            query=query,
            max_results=max_results,
            include_answer=True,
        )

        if result.get("error"):
            return f"[Search error: {result['error']}]"

        context_parts = []

        # Add AI answer if available
        if result.get("answer"):
            context_parts.append(f"Summary: {result['answer']}")

        # Add search results
        for i, item in enumerate(result.get("results", [])[:max_results], 1):
            context_parts.append(
                f"\n[{i}] {item['title']}\n"
                f"Source: {item['url']}\n"
                f"{item['content'][:500]}"
            )

        return "\n".join(context_parts)


def tavily_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Convenience function for Tavily search.
    
    Args:
        query: Search query
        max_results: Maximum results
        
    Returns:
        Search results dict
    """
    service = TavilySearchService()
    return service.search(query, max_results=max_results)
