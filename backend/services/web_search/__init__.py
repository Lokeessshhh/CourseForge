"""
Web Search Services
Provides web search functionality for AI chat using Tavily API
"""

from .tavily_client import TavilyClient, TavilySearchError

__all__ = ['TavilyClient', 'TavilySearchError']
