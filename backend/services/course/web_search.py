"""
Course Web Search Service
Integrates Tavily web search into course generation.

Strategy:
- 1 web search request per 4-week block (20 days)
- LLM generates unified query from all day topics
- Minimum 20 results, maximum 40 results
- Results distributed across days for theory content enhancement
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# Explicit logger name matching Django logging configuration
logger = logging.getLogger('services.course.web_search')


@dataclass
class DayTopic:
    """Represents a single day's topic for search"""
    week_number: int
    day_number: int
    title: str
    theme: str = ""


@dataclass
class WebSearchResult:
    """Single web search result"""
    title: str
    url: str
    content: str
    score: float
    domain: str
    published_date: Optional[str] = None


@dataclass
class CourseWebSearchData:
    """Container for web search data distributed across days"""
    # Map of (week_number, day_number) -> list of results
    day_results: Dict[tuple, List[WebSearchResult]] = field(default_factory=dict)
    # Unified query that was used
    unified_query: str = ""
    # Total results retrieved
    total_results: int = 0
    # Whether search met minimum threshold
    success: bool = False
    # Search metadata
    retries: int = 0
    error: Optional[str] = None


class CourseWebSearchService:
    """
    Web search service for course generation.

    Usage:
        1. Collect all day topics for 4-week block
        2. Generate unified search query via LLM
        3. Execute Tavily search (20-40 results)
        4. Distribute results to each day
        5. Inject into theory generation prompts
    """

    def __init__(self):
        self.tavily_client = None
        self.llm_client = None

    def _get_tavily_client(self):
        """Lazy load Tavily client for course use case"""
        if self.tavily_client is None:
            from services.web_search.tavily_client import TavilyClient
            self.tavily_client = TavilyClient(use_case='course')
        return self.tavily_client

    def _get_llm_client(self):
        """Lazy load LLM client for query generation"""
        if self.llm_client is None:
            from services.llm.qwen_client import QwenClient
            self.llm_client = QwenClient(max_tokens=500, temperature=0.3)
        return self.llm_client

    def collect_day_topics(
        self,
        duration_weeks: int,
        day_titles: Dict[tuple, str],
        week_themes: Dict[int, str],
    ) -> List[DayTopic]:
        """
        Collect all day topics for a 4-week block.

        Args:
            duration_weeks: Number of weeks (typically 4)
            day_titles: Dict mapping (week, day) -> title string
            week_themes: Dict mapping week_number -> theme string

        Returns:
            List of DayTopic objects for all days
        """
        topics = []
        for week_num in range(1, duration_weeks + 1):
            week_theme = week_themes.get(week_num, "")
            for day_num in range(1, 6):  # 5 days per week
                title = day_titles.get((week_num, day_num), f"Week {week_num} Day {day_num}")
                topics.append(DayTopic(
                    week_number=week_num,
                    day_number=day_num,
                    title=title,
                    theme=week_theme,
                ))
        return topics

    def generate_unified_query(
        self,
        course_topic: str,
        skill_level: str,
        day_topics: List[DayTopic],
        learning_goals: List[str],
    ) -> str:
        """
        Use LLM to generate a unified search query covering all day topics.

        Args:
            course_topic: Main course topic (e.g., "Python Programming")
            skill_level: Beginner/Intermediate/Advanced
            day_topics: List of all day topics in 4-week block
            learning_goals: List of learning goals

        Returns:
            Optimized search query string for Tavily
        """
        # Build context from day topics
        topics_summary = "\n".join([
            f"  - Week {t.week_number}, Day {t.day_number}: {t.title}"
            for t in day_topics[:20]  # Limit to first 20 for context window
        ])

        goals_text = "\n".join([f"  - {goal}" for goal in learning_goals[:5]])

        prompt = f"""Generate a SINGLE comprehensive web search query for researching course content.

COURSE INFO:
- Topic: {course_topic}
- Level: {skill_level}
- Duration: 4 weeks (20 days)

LEARNING GOALS:
{goals_text}

WEEKLY TOPICS COVERED:
{topics_summary}

TASK:
Create ONE search query that will return 20-40 high-quality educational resources covering ALL the above topics.

QUERY REQUIREMENTS:
1. Include the main topic: {course_topic}
2. Include level indicator: "{skill_level} level" or "{skill_level} {course_topic}"
3. Include educational keywords: "tutorial", "guide", "best practices", "examples"
4. Keep it concise (10-20 words max)
5. Focus on comprehensive coverage, not specific subtopics

EXAMPLE GOOD QUERIES:
- "Python programming beginner tutorial guide best practices examples"
- "Machine learning intermediate course comprehensive tutorial examples"
- "React JS advanced development best practices tutorial guide"

Return ONLY the search query, no explanations."""

        llm = self._get_llm_client()
        query = llm.generate(prompt=prompt, max_tokens=100)

        # Clean up the query
        query = query.strip().strip('"').strip("'")
        if len(query) > 200:
            query = query[:200]  # Truncate if too long

        logger.info(f"Generated unified search query: {query}")
        return query

    def execute_search(self, query: str) -> Dict[str, Any]:
        """
        Execute Tavily search with retry logic.

        Args:
            query: Unified search query

        Returns:
            Raw search results from Tavily
        """
        client = self._get_tavily_client()
        logger.info(f"Executing course web search: {query[:80]}...")
        results = client.search_for_course(query)
        return results

    def distribute_results(
        self,
        search_results: Dict[str, Any],
        day_topics: List[DayTopic],
    ) -> CourseWebSearchData:
        """
        Distribute search results across all days.

        Strategy:
        - Score each result against each day topic (simple keyword matching)
        - Assign top 1-2 results to each day
        - Ensure all days get at least 1 result if possible

        Args:
            search_results: Raw Tavily search results
            day_topics: List of all day topics

        Returns:
            CourseWebSearchData with results distributed by day
        """
        from services.web_search.tavily_client import TavilyClient

        results_list = search_results.get('results', [])
        total_results = len(results_list)
        total_days = len(day_topics)

        logger.info(f"[WEB_SEARCH] Distributing {total_results} results across {total_days} days")

        # Format results for easier handling
        formatted_results = []
        client = TavilyClient(use_case='chat')  # Use chat client for formatting
        for r in results_list:
            formatted_results.append(WebSearchResult(
                title=r.get('title', 'No title'),
                url=r.get('url', '#'),
                content=r.get('content', ''),
                score=r.get('score', 0),
                domain=client._extract_domain(r.get('url', '')),
                published_date=r.get('published_date'),
            ))

        # Distribute results to days
        day_results = {}
        results_per_day = max(1, total_results // total_days)

        logger.info(f"[WEB_SEARCH] Target: ~{results_per_day}-{results_per_day + 1} results per day")

        # Simple distribution: assign results sequentially with overlap
        result_idx = 0
        for i, topic in enumerate(day_topics):
            day_key = (topic.week_number, topic.day_number)

            # Assign 1-2 results per day
            assigned = []
            for _ in range(min(2, results_per_day + 1)):
                if result_idx < len(formatted_results):
                    assigned.append(formatted_results[result_idx])
                    result_idx += 1
                else:
                    # Wrap around if we run out
                    result_idx = 0

            day_results[day_key] = assigned
            logger.debug(f"[WEB_SEARCH] Week {topic.week_number} Day {topic.day_number}: {len(assigned)} results")

        # Create result object
        search_data = CourseWebSearchData(
            day_results=day_results,
            unified_query=search_results.get('query', ''),
            total_results=total_results,
            success=search_results.get('success', total_results >= 20),
            retries=search_results.get('retries', 0),
            error=search_results.get('error'),
        )

        # Log distribution summary
        days_with_results = sum(1 for results in day_results.values() if len(results) > 0)
        total_assigned = sum(len(results) for results in day_results.values())
        
        logger.info(f"[WEB_SEARCH]  Distribution complete:")
        logger.info(f"[WEB_SEARCH]   - Total results: {total_results}")
        logger.info(f"[WEB_SEARCH]   - Days covered: {days_with_results}/{total_days}")
        logger.info(f"[WEB_SEARCH]   - Total assignments: {total_assigned}")
        logger.info(f"[WEB_SEARCH]   - Success: {search_data.success}")

        return search_data

    def format_results_for_day(
        self,
        day_results: List[WebSearchResult],
        day_topic: DayTopic,
    ) -> str:
        """
        Format web search results for injection into theory generation prompt.

        Args:
            day_results: List of results for this specific day
            day_topic: Topic info for this day

        Returns:
            Formatted string for LLM prompt
        """
        if not day_results:
            return ""

        formatted = [
            f"\n\n RESEARCH RESOURCES for {day_topic.title}:",
            "=" * 60,
        ]

        for i, result in enumerate(day_results, 1):
            formatted.append(f"\n[{i}] {result.title}")
            formatted.append(f"    Source: {result.domain}")
            formatted.append(f"    URL: {result.url}")
            if result.content:
                # Truncate long content
                content = result.content[:300] + "..." if len(result.content) > 300 else result.content
                formatted.append(f"    Summary: {content}")
            if result.published_date:
                formatted.append(f"    Published: {result.published_date}")

        formatted.append("\n" + "=" * 60)
        formatted.append("Use these resources to enhance the theory content with:")
        formatted.append("- Up-to-date information and best practices")
        formatted.append("- Real-world examples and applications")
        formatted.append("- Current industry standards and trends")
        formatted.append("- Common pitfalls and how to avoid them")

        return "\n".join(formatted)

    def run_full_search(
        self,
        course_topic: str,
        skill_level: str,
        duration_weeks: int,
        day_titles: Dict[tuple, str],
        week_themes: Dict[int, str],
        learning_goals: List[str],
    ) -> CourseWebSearchData:
        """
        Run complete web search workflow for a 4-week block.

        Args:
            course_topic: Main course topic
            skill_level: Beginner/Intermediate/Advanced
            duration_weeks: Number of weeks (typically 4)
            day_titles: Dict mapping (week, day) -> title
            week_themes: Dict mapping week -> theme
            learning_goals: List of learning goals

        Returns:
            CourseWebSearchData with distributed results
        """
        logger.info(f"Starting course web search for '{course_topic}' ({duration_weeks} weeks)")

        # Step 1: Collect all day topics
        day_topics = self.collect_day_topics(duration_weeks, day_titles, week_themes)
        logger.info(f"Collected {len(day_topics)} day topics")

        # Step 2: Generate unified search query
        unified_query = self.generate_unified_query(
            course_topic, skill_level, day_topics, learning_goals
        )

        # Step 3: Execute search
        search_results = self.execute_search(unified_query)

        # Step 4: Distribute results to days
        search_data = self.distribute_results(search_results, day_topics)
        search_data.unified_query = unified_query

        logger.info(
            f"Course web search complete: {search_data.total_results} results, "
            f"success={search_data.success}"
        )
        return search_data


# Singleton instance for reuse
_search_service: Optional[CourseWebSearchService] = None


def get_web_search_service() -> CourseWebSearchService:
    """Get or create web search service singleton"""
    global _search_service
    if _search_service is None:
        _search_service = CourseWebSearchService()
    return _search_service
