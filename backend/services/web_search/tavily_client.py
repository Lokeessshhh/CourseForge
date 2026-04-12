"""
Tavily API Client for Web Search
Provides real-time web search capabilities for AI chat
"""

import logging
import requests
from django.conf import settings
from typing import List, Dict, Optional, Any

from .exceptions import (
    TavilySearchError,
    SearchRateLimitError,
    SearchAuthenticationError,
    SearchTimeoutError
)

# Explicit logger name matching Django logging configuration
logger = logging.getLogger('services.web_search.tavily_client')


class TavilyClient:
    """
    Client for Tavily AI Search API

    Tavily is a search engine built specifically for AI agents,
    delivering real-time, accurate, and factual results.

    Attributes:
        api_key: Tavily API key from settings
        base_url: Tavily API endpoint
        search_depth: Search depth (basic, advanced, fast, ultra-fast)
        max_results: Maximum number of results to return
    """

    def __init__(self, use_case: str = 'chat'):
        """
        Initialize Tavily client with Django settings

        Args:
            use_case: 'chat' for real-time chat search, 'course' for course generation
        """
        self.api_key = getattr(settings, 'TAVILY_API_KEY', None)
        self.base_url = "https://api.tavily.com/search"
        self.use_case = use_case

        if use_case == 'course':
            # Course generation: higher results for 4-week blocks
            self.search_depth = getattr(settings, 'TAVILY_COURSE_SEARCH_DEPTH', 'advanced')
            self.max_results = getattr(settings, 'TAVILY_COURSE_MAX_RESULTS', 40)
            self.min_results = getattr(settings, 'TAVILY_COURSE_MIN_RESULTS', 20)
            self.max_retries = getattr(settings, 'TAVILY_COURSE_MAX_RETRIES', 2)
        else:
            # Chat: lower results for fast responses
            self.search_depth = getattr(settings, 'TAVILY_CHAT_SEARCH_DEPTH', 'advanced')
            self.max_results = getattr(settings, 'TAVILY_CHAT_MAX_RESULTS', 5)
            self.min_results = 1
            self.max_retries = 1

        if not self.api_key:
            raise TavilySearchError(
                "TAVILY_API_KEY not configured in Django settings. "
                "Get your API key from https://app.tavily.com"
            )
    
    def search(self, query: str) -> Dict[str, Any]:
        """
        Search Tavily API and return results
        
        Args:
            query: Search query string
            
        Returns:
            Dict containing:
                - query: Original search query
                - answer: AI-generated answer (if enabled)
                - results: List of search results with title, url, content, score
            
        Raises:
            SearchAuthenticationError: If API key is invalid
            SearchRateLimitError: If rate limit exceeded
            SearchTimeoutError: If request times out
            TavilySearchError: For other API errors
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "query": query,
            "search_depth": self.search_depth,
            "max_results": self.max_results,
            "include_answer": True,
            "include_images": False,
            "include_raw_content": False
        }
        
        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=30  # 30 second timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.Timeout:
            raise SearchTimeoutError(
                "Search request timed out after 30 seconds. Please try again."
            )
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            
            if status_code == 401:
                raise SearchAuthenticationError(
                    "Invalid Tavily API key. Check your TAVILY_API_KEY setting."
                )
            elif status_code == 429:
                raise SearchRateLimitError(
                    "Tavily API rate limit exceeded. Please try again later."
                )
            elif status_code == 402:
                raise TavilySearchError(
                    "Tavily API credits exhausted. Upgrade your plan at https://app.tavily.com"
                )
            else:
                raise TavilySearchError(
                    f"Tavily API error (HTTP {status_code}): {str(e)}"
                )
        except requests.RequestException as e:
            raise TavilySearchError(
                f"Network error while searching: {str(e)}"
            )
        except Exception as e:
            raise TavilySearchError(
                f"Unexpected error during search: {str(e)}"
            )

    def search_for_course(self, query: str) -> Dict[str, Any]:
        """
        Search Tavily API for course generation with retry logic.
        Ensures minimum results threshold is met.

        Args:
            query: Search query (typically LLM-generated unified query)

        Returns:
            Dict containing:
                - query: Original search query
                - results: List of search results
                - success: True if min_results threshold met
                - retries: Number of retry attempts made

        Note:
            For course generation use case only.
            Retries with broader query if results < min_results.
        """
        if self.use_case != 'course':
            raise TavilySearchError(
                "search_for_course() requires TavilyClient(use_case='course')"
            )

        last_error = None
        results_data = None

        logger.info(f"[TAVILY] Starting course search with query: {query[:100]}...")
        logger.info(f"[TAVILY] Config: min_results={self.min_results}, max_results={self.max_results}, max_retries={self.max_retries}")

        for attempt in range(self.max_retries + 1):
            try:
                # First attempt: use original query
                # Retry attempts: broaden the query by removing specific terms
                if attempt > 0 and query:
                    # Simplify query for retry (remove last 30% of words)
                    words = query.split()
                    keep_count = max(int(len(words) * 0.7), len(words) - 3)
                    query = ' '.join(words[:keep_count]) + ' comprehensive guide tutorial'
                    logger.info(f"[TAVILY] Retry {attempt}/{self.max_retries} with broader query: {query[:80]}...")

                results_data = self.search(query)
                result_count = len(results_data.get('results', []))

                logger.info(f"[TAVILY] Attempt {attempt + 1}/{self.max_retries + 1}: Received {result_count} results")

                # Check if we met minimum threshold
                if result_count >= self.min_results:
                    logger.info(f"[TAVILY]  SUCCESS: {result_count} results (min: {self.min_results}, max: {self.max_results})")
                    logger.info(f"[TAVILY] Results breakdown:")
                    
                    # Log top 5 results for verification
                    top_results = results_data.get('results', [])[:5]
                    for i, result in enumerate(top_results, 1):
                        title = result.get('title', 'No title')[:60]
                        domain = self._extract_domain(result.get('url', ''))
                        score = result.get('score', 0) * 100
                        logger.info(f"[TAVILY]   [{i}] {title}... (source: {domain}, relevance: {score:.0f}%)")
                    
                    if result_count > 5:
                        logger.info(f"[TAVILY]   ... and {result_count - 5} more results")
                    
                    results_data['success'] = True
                    results_data['retries'] = attempt
                    return results_data
                else:
                    logger.warning(f"[TAVILY]  Below threshold: {result_count} results, need {self.min_results}. Retry {attempt}/{self.max_retries}")

            except Exception as e:
                last_error = e
                logger.error(f"[TAVILY]  Attempt {attempt + 1} failed: {str(e)}")
                if attempt >= self.max_retries:
                    break

        # All retries exhausted or max retries reached
        if results_data:
            result_count = len(results_data.get('results', []))
            # Return whatever we got, but mark as not meeting threshold
            results_data['success'] = False
            results_data['retries'] = self.max_retries
            results_data['error'] = f"Only got {result_count} results, needed {self.min_results}"
            logger.warning(f"[TAVILY]  COMPLETED WITH WARNING: {result_count} results (needed {self.min_results})")
            return results_data
        else:
            # Complete failure
            logger.error(f"[TAVILY]  COMPLETE FAILURE: No results after {self.max_retries + 1} attempts")
            raise TavilySearchError(
                f"Course search failed after {self.max_retries + 1} attempts: {str(last_error)}"
            )
    
    def format_results_for_llm(self, search_data: Dict[str, Any]) -> str:
        """
        Format search results for LLM context injection

        Args:
            search_data: Raw response from Tavily API

        Returns:
            Formatted string with search results for LLM consumption
        """
        formatted = []

        # Add AI-generated answer if available
        if search_data.get('answer'):
            formatted.append(f"AI-Generated Answer: {search_data['answer']}")
            formatted.append("")

        # Add search results
        results = search_data.get('results', [])
        if results:
            formatted.append("Web Search Results:")
            formatted.append("=" * 50)

            for i, result in enumerate(results, 1):
                formatted.append(f"\n[{i}] {result.get('title', 'No title')}")
                formatted.append(f"    URL: {result.get('url', 'No URL')}")
                formatted.append(f"    Relevance: {result.get('score', 0) * 100:.0f}%")
                formatted.append(f"    Content: {result.get('content', 'No content')}")

                # Add published date if available
                if result.get('published_date'):
                    formatted.append(f"    Published: {result['published_date']}")

        return "\n".join(formatted)
    
    def format_results_for_frontend(self, search_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format search results for frontend display

        Args:
            search_data: Raw response from Tavily API

        Returns:
            List of formatted result dictionaries
        """
        results = search_data.get('results', [])

        formatted_results = []
        for result in results:
            formatted_results.append({
                'title': result.get('title', 'No title'),
                'url': result.get('url', '#'),
                'content': result.get('content', ''),
                'score': result.get('score', 0),
                'published_date': result.get('published_date'),
                'domain': self._extract_domain(result.get('url', ''))
            })

        return formatted_results
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.replace('www.', '')
        except Exception:
            return url
    
    def get_usage_info(self) -> Dict[str, Any]:
        """
        Get API usage information
        
        Returns:
            Dict with current usage stats (requires dashboard API call)
        """
        # Note: Tavily doesn't expose usage via API yet
        # Users need to check dashboard at https://app.tavily.com
        return {
            'note': 'Check usage at https://app.tavily.com',
            'free_tier_limit': 1000,
            'limit_period': 'month'
        }
