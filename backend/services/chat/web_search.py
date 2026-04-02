"""
Web Search Integration for Chat
Adds real-time web search capabilities to AI chat using Tavily API
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


# Keywords that trigger web search automatically
WEB_SEARCH_KEYWORDS = [
    # Search intent
    'search', 'web search', 'google', 'bing', 'look up',
    'find online', 'search the web', 'search online',
    
    # Time-sensitive
    'latest', 'current', 'recent', 'new', 'today',
    'yesterday', 'this week', 'this month', '2026', '2025',
    
    # News/Events
    'news', 'announcement', 'release', 'update', 'breaking',
    
    # Facts/Data
    'statistics', 'price', 'cost', 'population', 'market share',
    'ranking', 'report', 'study', 'survey',
    
    # People/Companies
    'who is', 'what company', 'founder', 'ceo', 'owner',
    
    # Technology
    'version', 'release date', 'documentation', 'changelog',
    
    # Weather/Current events
    'weather', 'temperature', 'forecast', 'score', 'result',
]


def should_trigger_web_search(query: str) -> bool:
    """
    Check if query should trigger web search based on keywords
    
    Args:
        query: User's query string
        
    Returns:
        True if web search should be triggered
    """
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in WEB_SEARCH_KEYWORDS)


async def perform_web_search(query: str) -> Optional[Dict[str, Any]]:
    """
    Perform web search using Tavily API

    Args:
        query: Search query

    Returns:
        Dict with search results or None if search fails
    """
    try:
        from services.web_search.tavily_client import TavilyClient

        # Use 'chat' use case for fast responses with fewer results (default: 5)
        client = TavilyClient(use_case='chat')
        results = await sync_to_async(client.search)(query)

        logger.info(f"Web search successful for query: {query[:50]}...")
        return {
            'success': True,
            'data': results,
            'formatted': client.format_results_for_llm(results),
            'frontend_results': client.format_results_for_frontend(results),
            'query': results.get('query', query)
        }

    except Exception as e:
        logger.warning(f"Web search failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'formatted': f"[Web search unavailable: {str(e)}]",
            'frontend_results': []
        }


def format_web_search_for_prompt(
    search_result: Optional[Dict[str, Any]]
) -> str:
    """
    Format web search results for LLM prompt injection
    
    Args:
        search_result: Result from perform_web_search()
        
    Returns:
        Formatted string for LLM context
    """
    if not search_result or not search_result.get('success'):
        return ""
    
    return f"""

🔍 WEB SEARCH RESULTS:
{search_result.get('formatted', 'No results available')}

Instructions:
- Use the above web search results to provide accurate, up-to-date information
- Cite sources when relevant (mention website names)
- If search results conflict with your training data, prefer the search results
- Be honest about uncertainties

"""
