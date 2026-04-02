# Web Search Integration for Course Generation

## Overview

Integrated Tavily web search into the course generation system to provide up-to-date, factual content in theory sections while minimizing API costs.

## Strategy

- **1 web search request per 4-week block** (20 days of content)
- **20-40 results per search** (distributed across all days)
- **Theory-only integration** (web results enhance theory content, not code/practical)
- **LLM-generated unified query** (covers all day topics in single search)

## Configuration (.env)

```bash
# Tavily for Course Generation (bulk research for 4-week blocks)
# Minimum results required per 4-week block (1 request per 4 weeks)
TAVILY_COURSE_MIN_RESULTS=20
# Maximum results per 4-week block (distributed across 20 days)
TAVILY_COURSE_MAX_RESULTS=40
# Search depth for course generation (advanced = more thorough)
TAVILY_COURSE_SEARCH_DEPTH=advanced
# Number of retry attempts if results < minimum threshold
TAVILY_COURSE_MAX_RETRIES=2
```

## Implementation Details

### 1. Tavily Client Update (`backend/services/web_search/tavily_client.py`)

**Changes:**
- Added `use_case` parameter to `__init__` ('chat' or 'course')
- Course use case loads different config settings (higher results)
- New method: `search_for_course()` with retry logic

**Retry Logic:**
- If results < 20, retries with broader query (removes 30% of words)
- Maximum 2 retries by default
- Returns whatever results obtained even if below threshold

### 2. Course Web Search Service (`backend/services/course/web_search.py`) **[NEW FILE]**

**Key Components:**

#### `CourseWebSearchService`
Main service class for course web search.

**Methods:**
- `collect_day_topics()` - Collects all day topics for 4-week block
- `generate_unified_query()` - Uses LLM to create single search query
- `execute_search()` - Calls Tavily API with retry logic
- `distribute_results()` - Distributes results across days (1-2 per day)
- `format_results_for_day()` - Formats results for LLM prompt injection
- `run_full_search()` - Complete workflow (steps 1-4 combined)

**Data Classes:**
- `DayTopic` - Represents a single day's topic
- `WebSearchResult` - Single search result
- `CourseWebSearchData` - Container for distributed results

### 3. Course Generator Update (`backend/services/course/generator.py`)

**Changes to `_generate_theory_content()`:**
- Added `web_search_results` parameter (optional, default "")
- Injects web results into prompt when available
- LLM instructed to integrate research into theory

**Prompt Enhancement:**
```
📚 RESEARCH RESOURCES for {day_title}:
============================================================
[1] {title}
    Source: {domain}
    URL: {url}
    Summary: {content}

Use these resources to enhance the theory content with:
- Up-to-date information and best practices
- Real-world examples and applications
- Current industry standards and trends
- Common pitfalls and how to avoid them
```

### 4. Celery Tasks Update (`backend/apps/courses/tasks.py`)

**New Function: `_generate_in_blocks_with_web_search()`**

Processes course in 4-week blocks sequentially:

```python
async def _generate_in_blocks_with_web_search(...):
    while block_start <= duration_weeks:
        # STEP 1: Generate themes & titles for 4 weeks
        for week in block:
            generate_week_theme()
            generate_day_titles()
        
        # STEP 2: Run web search with actual titles
        web_search_data = run_full_search(
            day_titles=block_day_titles,
            week_themes=block_week_themes,
        )
        
        # STEP 3: Generate content with web results
        for day in block:
            generate_theory_with_web(web_search_data)
            generate_code()
            generate_quiz()
        
        block_start += 4
```

**Changes to `generate_course_content_task()`:**
- Calls new block-based generation function
- Removed single web search before all generation
- Web search now runs per 4-week block with actual titles

**Changes to `_generate_single_day_with_titles()`:**
- New function (titles pre-generated)
- Accepts `web_search_data` parameter
- Extracts day-specific results from search data
- Passes formatted results to `_generate_theory_content()`

**Expected Logs:**
```
[BLOCK GENERATION] Starting block-based generation for 8 weeks

============================================================
[BLOCK 1] Processing weeks 1-4 (4 weeks)
============================================================
[BLOCK 1] Step 1: Generating week themes and day titles...
  - Week 1 Day 1: Introduction to Python
  - Week 1 Day 2: Variables and Data Types
  ...
[BLOCK 1] Step 2: Running web search...
Generated unified search query: Python programming beginner tutorial variables functions guide
Course search successful: 35 results (min: 20)
Results distributed: 35 results → 20 days (success=True)
[BLOCK 1] Step 3: Generating content with web results...
Using 2 web results for Week 1 Day 1 theory
[BLOCK 1] Completed 20/20 days successfully

============================================================
[BLOCK 2] Processing weeks 5-8 (4 weeks)
============================================================
[BLOCK 2] Step 1: Generating week themes and day titles...
  - Week 5 Day 1: Object-Oriented Programming Basics
  ...
[BLOCK 2] Step 2: Running web search...
Course search successful: 38 results (min: 20)
[BLOCK 2] Step 3: Generating content with web results...
Using 2 web results for Week 5 Day 1 theory
[BLOCK 2] Completed 20/20 days successfully

[BLOCK GENERATION] All 2 blocks completed for 8 weeks
```

## Flow Diagram

### Updated: Block-Based Generation with Web Search per 4 Weeks

```
Course Generation Request
         ↓
Detect Topic (LLM)
         ↓
┌───────────────────────────────────────────┐
│ 4-WEEK BLOCK 1                            │
│ ┌─────────────────────────────────────┐   │
│ │ STEP 1: Generate Themes & Titles    │   │
│ │ - Week 1-4 themes                   │   │
│ │ - Week 1-4 day titles (20 days)     │   │
│ └─────────────────────────────────────┘   │
│              ↓                            │
│ ┌─────────────────────────────────────┐   │
│ │ STEP 2: WEB SEARCH (1 request)      │   │
│ │ - Collect all 20 day titles         │   │
│ │ - Generate unified query (LLM)      │   │
│ │ - Tavily search (20-40 results)     │   │
│ │ - Distribute to 20 days             │   │
│ └─────────────────────────────────────┘   │
│              ↓                            │
│ ┌─────────────────────────────────────┐   │
│ │ STEP 3: Generate Content            │   │
│ │ - Theory + Web Results (parallel)   │   │
│ │ - Code (parallel)                   │   │
│ │ - Quiz                              │   │
│ └─────────────────────────────────────┘   │
└───────────────────────────────────────────┘
         ↓ (if more weeks)
┌───────────────────────────────────────────┐
│ 4-WEEK BLOCK 2 (Weeks 5-8)                │
│ ┌─────────────────────────────────────┐   │
│ │ STEP 1: Generate Themes & Titles    │   │
│ │ - Week 5-8 themes                   │   │
│ │ - Week 5-8 day titles (20 days)     │   │
│ └─────────────────────────────────────┘   │
│              ↓                            │
│ ┌─────────────────────────────────────┐   │
│ │ STEP 2: WEB SEARCH (1 request)      │   │
│ │ - Collect all 20 day titles         │   │
│ │ - Generate unified query (LLM)      │   │
│ │ - Tavily search (20-40 results)     │   │
│ │ - Distribute to 20 days             │   │
│ └─────────────────────────────────────┘   │
│              ↓                            │
│ ┌─────────────────────────────────────┐   │
│ │ STEP 3: Generate Content            │   │
│ │ - Theory + Web Results (parallel)   │   │
│ │ - Code (parallel)                   │   │
│ │ - Quiz                              │   │
│ └─────────────────────────────────────┘   │
└───────────────────────────────────────────┘
         ↓
Weekly Tests (MCQ + Coding)
         ↓
Course Ready
```

### Web Search Count by Duration

| Duration | 4-Week Blocks | Web Search Requests |
|----------|---------------|---------------------|
| 1 week   | 1 block       | 1 request           |
| 2 weeks  | 1 block       | 1 request           |
| 3 weeks  | 1 block       | 1 request           |
| 4 weeks  | 1 block       | 1 request           |
| 5 weeks  | 2 blocks      | 2 requests          |
| 8 weeks  | 2 blocks      | 2 requests          |
| 9 weeks  | 3 blocks      | 3 requests          |
| 12 weeks | 3 blocks      | 3 requests          |
| 16 weeks | 4 blocks      | 4 requests          |

## API Cost Analysis

### Before (No Web Search)
- **Cost:** $0 (LLM only)
- **Content freshness:** LLM training data only

### After (With Web Search)
- **4-week course:** 1 search request
- **8-week course:** 1-2 search requests (currently 1, can be enhanced)
- **12-week course:** 1 search request (currently 1, can be enhanced to 3)

**Tavily Pricing (as of 2024):**
- Free tier: 1,000 searches/month
- Paid plans start at $X/month for Y searches

**Estimated Monthly Cost:**
- 100 courses/month (4 weeks each) = 100 searches = **FREE**
- 500 courses/month (4 weeks each) = 500 searches = **FREE**
- 2,000 courses/month = 2,000 searches = **Paid plan required**

## Result Distribution Strategy

**Current Implementation:**
- Sequential distribution (results 1-2 → Day 1, results 3-4 → Day 2, etc.)
- Simple and fast
- Ensures all days get at least 1 result

**Future Enhancement (Optional):**
- LLM-based scoring of each result against day topics
- Better relevance matching
- Slightly slower (more LLM calls)

## Error Handling

### Web Search Fails Completely
- Course generation continues without web results
- Logs warning, proceeds with LLM-only content
- No user-facing impact

### Results < 20 (Below Threshold)
- Retry with broader query (up to 2 times)
- If still < 20, use available results
- Logs warning about insufficient results

### Tavily API Unavailable
- Graceful fallback (no web search)
- Course generation proceeds normally
- Error logged for debugging

## Testing Checklist

- [ ] Tavily API key configured in `.env`
- [ ] Course generation runs without errors
- [ ] Web search executes before content generation
- [ ] Results distributed to days correctly
- [ ] Theory content includes web research
- [ ] Fallback works when search fails
- [ ] Logs show search status and result count

## Future Enhancements

1. **Multiple 4-week blocks:** For courses > 4 weeks, run separate searches per block
2. **Smart result matching:** LLM scoring for better day-topic relevance
3. **Result caching:** Cache search results for similar courses
4. **Progressive enhancement:** Add more searches for advanced topics
5. **Analytics:** Track which searches produce best results

## Files Modified/Created

### Created:
1. `backend/services/course/web_search.py` - New web search service

### Modified:
1. `backend/.env.example` - Added Tavily course config
2. `backend/services/web_search/tavily_client.py` - Course use case + retry logic
3. `backend/services/course/generator.py` - Theory generation with web results
4. `backend/apps/courses/tasks.py` - Web search integration in tasks

## Usage Example

```python
# Automatic - runs during course generation
# No manual intervention needed

# Trigger course generation via API:
POST /api/courses/generate/
{
    "course_name": "Python for Data Science",
    "duration": "4 weeks",
    "level": "beginner",
    "goals": ["Learn Python basics", "Data manipulation", "Visualization"]
}

# Web search runs automatically:
# 1. Detects topic: "Python Data Science"
# 2. Generates query: "Python data science beginner tutorial pandas numpy visualization guide"
# 3. Searches Tavily: 20-40 results
# 4. Distributes to 20 days
# 5. Enhances theory content with research
```

## Monitoring & Debugging

**Key Log Messages:**
```
[TASK] Running web search for 4 weeks (1 request)...
Generated unified search query: Python programming beginner tutorial guide
Executing course web search: Python programming...
Course search successful: 35 results (min: 20)
Results distributed: 35 results → 20 days (success=True)
Using 2 web results for Week 1 Day 1 theory
```

**Troubleshooting:**
- Check Tavily API key: `settings.TAVILY_API_KEY`
- Check result count: Look for "Course search successful" log
- Verify distribution: Look for "Using X web results for Week Y Day Z"
- Check fallback: Look for "Web search failed" warnings
