"""
Custom exceptions for web search services
"""


class TavilySearchError(Exception):
    """Exception raised for Tavily API errors"""
    pass


class SearchRateLimitError(TavilySearchError):
    """Exception raised when rate limit is exceeded"""
    pass


class SearchAuthenticationError(TavilySearchError):
    """Exception raised when API key is invalid"""
    pass


class SearchTimeoutError(TavilySearchError):
    """Exception raised when search request times out"""
    pass
