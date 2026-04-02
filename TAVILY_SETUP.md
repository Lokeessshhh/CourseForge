# Tavily Web Search Integration

## Overview
Your CourseForge chat now supports real-time web search using Tavily API. This allows the AI to search the internet for up-to-date information when answering questions.

## Setup Instructions

### 1. Get Your Tavily API Key

1. **Sign Up**: Go to [https://app.tavily.com](https://app.tavily.com)
2. **Create Account**: Sign up with email or Google/GitHub
3. **Verify Email**: Check your email and verify your account
4. **Get API Key**: Your API key will be displayed on the dashboard (starts with `tvly-`)
5. **Copy Key**: Copy the API key for use in your backend

### 2. Configure Backend Environment

Add the following to your `backend/.env` file:

```env
# Tavily Web Search API
TAVILY_API_KEY=tvly-your-actual-api-key-here
TAVILY_SEARCH_DEPTH=advanced
TAVILY_MAX_RESULTS=5
```

### 3. Environment Variables Explained

| Variable | Required | Default | Options | Description |
|----------|----------|---------|---------|-------------|
| `TAVILY_API_KEY` | **Yes** | - | - | Your Tavily API key from dashboard |
| `TAVILY_SEARCH_DEPTH` | No | `advanced` | `basic`, `advanced`, `fast`, `ultra-fast` | Search quality vs speed |
| `TAVILY_MAX_RESULTS` | No | `5` | 1-10 | Number of search results to return |

### 4. Search Depth Options

| Depth | Speed | Quality | Credits/Search | Best For |
|-------|-------|---------|----------------|----------|
| `fast` | Fastest | Basic | 1 | Simple queries |
| `basic` | Fast | Good | 1 | General search |
| `advanced` | Medium | Best | 2 | Research, complex queries |
| `ultra-fast` | Instant | Minimal | 1 | Real-time chat |

**Recommended**: Use `advanced` for best quality answers.

### 5. Free Tier Limits

- **Free Tier**: 1,000 searches per month
- **Credit Cost**: 2 credits per search (advanced depth)
- **Effective Limit**: ~500 searches/month with advanced depth
- **Upgrade**: Check [Tavily Pricing](https://app.tavily.com/pricing)

### 6. Usage Monitoring

Monitor your API usage at: [https://app.tavily.com/dashboard](https://app.tavily.com/dashboard)

## Features

### Auto-Detection
Web search is automatically triggered for queries containing:
- Search keywords: "search", "google", "look up"
- Time-sensitive: "latest", "current", "recent", "2026"
- News/Events: "news", "announcement", "release"
- Facts/Data: "statistics", "price", "population"

### Manual Toggle
Users can manually enable/disable web search using the 🔍 toggle button in the chat input.

### Search Results Display
- Search results shown as a collapsible card
- Each result shows: title, source domain, relevance score, content snippet
- Clickable links to open source websites
- Loading state while searching

## Example Usage

### User Query Examples:
```
"What is the latest Python version?"
→ Web search triggered automatically
→ Returns current version with release date

"Search for React 19 new features"
→ Web search triggered by keyword
→ Returns latest React 19 features

"Who won the 2026 Super Bowl?"
→ Time-sensitive query triggers search
→ Returns current year information
```

## Troubleshooting

### "Invalid API Key" Error
- Check your `TAVILY_API_KEY` in `.env`
- Ensure no extra spaces or quotes
- Restart backend after changing `.env`

### "Rate Limit Exceeded" Error
- You've exceeded your monthly quota
- Wait until next month or upgrade plan
- Reduce `TAVILY_MAX_RESULTS` to conserve credits

### "Search Timed Out" Error
- Network connectivity issue
- Tavily API temporarily unavailable
- Try again in a few moments

### Search Not Triggering
- Check if query contains trigger keywords
- Manually enable web search toggle
- Check backend logs for errors

## API Reference

### Backend Service
```python
from services.chat.web_search import perform_web_search

# Perform search
result = await perform_web_search("latest AI news")

# Result structure
{
    'success': True,
    'data': {
        'query': 'latest AI news',
        'answer': 'AI-generated summary...',
        'results': [
            {
                'title': 'Article Title',
                'url': 'https://example.com',
                'content': 'Content snippet...',
                'score': 0.95
            }
        ]
    }
}
```

## Cost Optimization Tips

1. **Use `basic` depth** for simple queries (1 credit vs 2)
2. **Limit results** to 3-5 with `TAVILY_MAX_RESULTS`
3. **Cache common queries** to avoid repeat searches
4. **Monitor usage** regularly in Tavily dashboard
5. **Use auto-detection** to only search when needed

## Support

- **Tavily Docs**: [https://docs.tavily.com](https://docs.tavily.com)
- **Tavily Dashboard**: [https://app.tavily.com](https://app.tavily.com)
- **CourseForge Issues**: Check backend logs for detailed error messages
