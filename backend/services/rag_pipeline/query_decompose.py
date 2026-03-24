"""
Query decomposition service.
Breaks complex queries into sub-queries for better retrieval.
"""
import logging
from typing import List
import json

logger = logging.getLogger(__name__)


class QueryDecomposer:
    """
    Decomposes complex queries into simpler sub-queries.
    Uses LLM to identify and split multi-part questions.
    """

    DECOMPOSITION_PROMPT = """You are a query decomposition expert. Given a complex question, break it down into simpler, focused sub-questions that can be answered independently.

Rules:
1. Each sub-question should be answerable on its own
2. Sub-questions should cover all aspects of the original question
3. Keep sub-questions concise and clear
4. Return ONLY a JSON array of strings, no other text

Complex question: {query}

Return a JSON array of sub-questions. If the question is already simple, return it as a single-element array."""

    def __init__(self, llm_client=None):
        """
        Initialize the decomposer.
        
        Args:
            llm_client: Optional LLM client for decomposition.
                        Falls back to rule-based if not provided.
        """
        self.llm_client = llm_client

    def decompose(self, query: str, max_sub_queries: int = 4) -> List[str]:
        """
        Decompose a complex query into sub-queries.
        
        Args:
            query: The original complex query
            max_sub_queries: Maximum number of sub-queries to generate
            
        Returns:
            List of sub-query strings
        """
        # First, check if decomposition is needed
        if not self._needs_decomposition(query):
            return [query]

        # Try LLM-based decomposition
        if self.llm_client:
            try:
                return self._llm_decompose(query, max_sub_queries)
            except Exception as e:
                logger.warning("LLM decomposition failed, falling back to rules: %s", e)

        # Fallback to rule-based decomposition
        return self._rule_based_decompose(query, max_sub_queries)

    def _needs_decomposition(self, query: str) -> bool:
        """Check if query needs decomposition."""
        # Indicators of complex queries
        complex_indicators = [
            " and ", " or ", " also ", " as well as ",
            " compare ", " difference between ", " versus ", " vs ",
            "?",  # Multiple questions
        ]
        
        # Count question marks
        question_count = query.count("?")
        if question_count > 1:
            return True
            
        # Check for conjunctions that suggest multiple parts
        and_count = query.lower().count(" and ")
        if and_count >= 2:
            return True
            
        # Check for comparison keywords
        query_lower = query.lower()
        for indicator in complex_indicators:
            if indicator in query_lower and indicator not in ["?"]:
                return True
                
        return False

    def _llm_decompose(self, query: str, max_sub_queries: int) -> List[str]:
        """Use LLM to decompose the query."""
        prompt = self.DECOMPOSITION_PROMPT.format(query=query)
        
        response = self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.0,
        )
        
        content = response.get("content", "[]")
        
        # Parse JSON response
        try:
            sub_queries = json.loads(content)
            if isinstance(sub_queries, list):
                return [str(q).strip() for q in sub_queries[:max_sub_queries] if q]
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM decomposition response as JSON")
            
        return [query]

    def _rule_based_decompose(self, query: str, max_sub_queries: int) -> List[str]:
        """Rule-based query decomposition fallback."""
        sub_queries = []
        
        # Split on question marks for multiple questions
        if "?" in query:
            parts = query.split("?")
            for part in parts:
                part = part.strip()
                if part and len(part) > 5:
                    # Add question mark back
                    if not part.endswith("?"):
                        part += "?"
                    sub_queries.append(part)
        
        # Split on " and " for compound questions
        if len(sub_queries) <= 1 and " and " in query.lower():
            # Find the conjunction position
            lower_query = query.lower()
            and_positions = []
            pos = 0
            while True:
                pos = lower_query.find(" and ", pos)
                if pos == -1:
                    break
                and_positions.append(pos)
                pos += 1
            
            if and_positions:
                # Split at the first "and"
                split_pos = and_positions[0]
                part1 = query[:split_pos].strip()
                part2 = query[split_pos + 5:].strip()  # Skip " and "
                
                if len(part1) > 10 and len(part2) > 10:
                    sub_queries = [part1, part2]
        
        # If no decomposition found, return original
        if not sub_queries:
            return [query]
            
        return sub_queries[:max_sub_queries]


def decompose_query(query: str, llm_client=None, max_sub_queries: int = 4) -> List[str]:
    """
    Convenience function to decompose a query.
    
    Args:
        query: The query to decompose
        llm_client: Optional LLM client
        max_sub_queries: Maximum sub-queries to return
        
    Returns:
        List of sub-queries
    """
    decomposer = QueryDecomposer(llm_client=llm_client)
    return decomposer.decompose(query, max_sub_queries=max_sub_queries)
