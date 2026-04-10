"""
Qwen LLM client via OpenRouter API (OpenAI-compatible).
Uses OpenRouter for qwen/qwen-2.5-7b-instruct model.
Supports both sync (generate) and async streaming (stream_generate).
"""
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

# System prompt for coding tutor
DEFAULT_SYSTEM_PROMPT = """You are an expert coding tutor. Explain clearly and include code examples."""


class QwenClient:
    """Client for Qwen running on OpenRouter (OpenAI-compatible API)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: int = 120,
    ):
        base = base_url or getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        base = base.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        self.base_url = base
        self.model = model or getattr(settings, "OPENROUTER_LLM_MODEL", "qwen/qwen-2.5-7b-instruct")
        self.max_tokens = max_tokens or getattr(settings, "OPENROUTER_MAX_TOKENS", 2000)
        self.temperature = temperature or getattr(settings, "VLLM_TEMPERATURE", 0.7)
        self.timeout = timeout
        self.api_key = getattr(settings, "OPENROUTER_API_KEY", "")

    def _build_messages(
        self,
        prompt: str,
        context: str = "",
        knowledge_state: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Build messages array for chat completion."""
        messages = []

        # System prompt
        system_parts = [system_prompt or DEFAULT_SYSTEM_PROMPT]

        # Add context if provided
        if context:
            system_parts.append(f"\n## Relevant Context\n{context}")

        # Add knowledge state if provided
        if knowledge_state:
            ks_str = json.dumps(knowledge_state, indent=2)
            system_parts.append(f"\n## User Knowledge State\n{ks_str}")

        messages.append({"role": "system", "content": "\n".join(system_parts)})

        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)

        # Add user prompt
        messages.append({"role": "user", "content": prompt})

        return messages

    def _log_call(self, prompt_len: int, response_len: int, latency_ms: float, endpoint: str):
        """Log LLM call details."""
        logger.info(
            "LLM call to %s | prompt_len=%d | response_len=%d | latency=%.2fms",
            endpoint,
            prompt_len,
            response_len,
            latency_ms,
        )

    async def stream_generate(
        self,
        prompt: str,
        context: str = "",
        knowledge_state: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async streaming generation for WebSocket chat.
        Yields tokens one by one as they arrive from vLLM.

        Args:
            prompt: User's input prompt
            context: Relevant context from RAG
            knowledge_state: User's current knowledge/confidence levels
            conversation_history: Previous messages in the conversation

        Yields:
            Individual tokens as strings
        """
        start_time = time.time()
        prompt_len = 0
        response_len = 0

        messages = self._build_messages(prompt, context, knowledge_state, conversation_history)
        prompt_len = sum(len(m["content"]) for m in messages)

        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
            "reasoning": {"enabled": False},  # Disable Qwen thinking/reasoning
        }

        try:
            # OpenRouter requires specific headers
            headers = {
                "HTTP-Referer": "https://github.com/your-org/ai-course-generator",
                "X-Title": "AI Course Generator",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                headers=headers,
            ) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error("OpenRouter stream error: %d - %s", response.status_code, error_text)
                        yield f"\n\n[Error: OpenRouter returned status {response.status_code}]"
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    response_len += len(content)
                                    yield content
                            except json.JSONDecodeError:
                                continue

        except httpx.TimeoutException:
            logger.error("OpenRouter stream_generate timed out after %ds", self.timeout)
            yield "\n\n[Error: Request timed out]"
        except Exception as exc:
            logger.exception("OpenRouter stream_generate failed: %s", exc)
            yield f"\n\n[Error: {exc}]"
        finally:
            latency_ms = (time.time() - start_time) * 1000
            try:
                self._log_call(prompt_len, response_len, latency_ms, "stream_generate")
            except Exception:
                logger.exception("Failed to log LLM call metrics")

    def generate(
        self,
        prompt: str,
        context: str = "",
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Synchronous non-streaming generation.
        Used for course generation, quiz generation, certificate text.

        Args:
            prompt: User's input prompt
            context: Relevant context
            max_tokens: Maximum tokens to generate
            system_prompt: Custom system prompt

        Returns:
            Full response string
        """
        start_time = time.time()
        prompt_len = 0
        response_len = 0

        messages = self._build_messages(prompt, context, system_prompt=system_prompt)
        prompt_len = sum(len(m["content"]) for m in messages)

        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
            "reasoning": {"enabled": False},  # Disable Qwen thinking/reasoning
        }

        try:
            # OpenRouter requires specific headers
            headers = {
                "HTTP-Referer": "https://github.com/your-org/ai-course-generator",
                "X-Title": "AI Course Generator",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            with httpx.Client(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                headers=headers,
            ) as client:
                response = client.post(url, json=payload, headers=headers)

                if response.status_code != 200:
                    logger.error("OpenRouter generate error: %d - %s", response.status_code, response.text)
                    return f"[Error: OpenRouter returned status {response.status_code}]"

                data = response.json()
                
                # Debug: Log the response structure if content is missing
                if "choices" not in data or not data.get("choices"):
                    logger.warning("OpenRouter response missing 'choices': %s", str(data)[:500])
                    return "[Error: Invalid response from OpenRouter]"
                
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                
                # Qwen models may return reasoning in a separate field
                # Try content first, then reasoning, then empty string
                content = message.get("content")
                if not content:
                    reasoning = message.get("reasoning")
                    if reasoning:
                        logger.info("Using reasoning field as fallback for response")
                        content = reasoning
                    else:
                        content = ""
                
                response_len = len(content) if content else 0

                if not content:
                    logger.warning("OpenRouter returned empty content. Finish reason: %s", choice.get("finish_reason"))
                    return "[Error: Empty response from OpenRouter - model may have hit token limit]"

                return content

        except httpx.TimeoutException:
            logger.error("OpenRouter generate timed out after %ds", self.timeout)
            return "[Error: Request timed out]"
        except Exception as exc:
            logger.exception("OpenRouter generate failed: %s", exc)
            return f"[Error: {exc}]"
        finally:
            latency_ms = (time.time() - start_time) * 1000
            try:
                self._log_call(prompt_len, response_len, latency_ms, "generate")
            except Exception:
                logger.exception("Failed to log LLM call metrics")

    def _generate_json(
        self,
        prompt: str,
        context: str = "",
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate and parse JSON response with retry on failure.

        Returns:
            Parsed JSON dict or error dict
        """
        for attempt in range(2):  # Retry once
            response = self.generate(prompt, context, max_tokens, system_prompt)

            if response.startswith("[Error:"):
                return {"error": response, "valid": False}

            try:
                # Try to extract JSON from response
                json_str = response.strip()
                # Handle markdown code blocks
                if "```json" in json_str:
                    start = json_str.find("```json") + 7
                    end = json_str.find("```", start)
                    json_str = json_str[start:end].strip()
                elif "```" in json_str:
                    start = json_str.find("```") + 3
                    end = json_str.find("```", start)
                    json_str = json_str[start:end].strip()

                data = json.loads(json_str)
                return data

            except json.JSONDecodeError as e:
                logger.warning("JSON parse failed (attempt %d): %s", attempt + 1, e)
                if attempt == 0:
                    # Retry with explicit JSON instruction
                    prompt = f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON, no markdown, no explanation."
                else:
                    return {"error": f"Failed to parse JSON: {e}", "raw_response": response, "valid": False}

        return {"error": "Unknown error", "valid": False}

    def generate_course_outline(
        self,
        topic: str,
        duration_weeks: int,
        hours_per_day: int,
        skill_level: str,
        goals: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a structured course outline.

        Args:
            topic: Course topic
            duration_weeks: Number of weeks
            hours_per_day: Study hours per day
            skill_level: Beginner/Intermediate/Advanced
            goals: Learning goals

        Returns:
            JSON: {weeks: [{week_number, theme, objectives, days: [{day_number, title, tasks}]}]}
        """
        goals_str = "\n".join(f"- {g}" for g in goals) if goals else "Not specified"

        prompt = f"""Generate a structured course outline for the following:

Topic: {topic}
Duration: {duration_weeks} weeks
Hours per day: {hours_per_day}
Skill Level: {skill_level}
Learning Goals:
{goals_str}

Return a JSON object with this exact structure:
{{
    "weeks": [
        {{
            "week_number": 1,
            "theme": "Week theme",
            "objectives": ["Objective 1", "Objective 2"],
            "days": [
                {{
                    "day_number": 1,
                    "title": "Day title",
                    "tasks": ["Task 1", "Task 2"]
                }}
            ]
        }}
    ]
}}

Return ONLY valid JSON, no markdown, no explanation."""

        result = self._generate_json(prompt, max_tokens=4000)

        # Validate structure
        if "weeks" not in result:
            return {"error": "Invalid course outline: missing 'weeks' key", "valid": False, "raw": result}

        for week in result.get("weeks", []):
            if "week_number" not in week or "days" not in week:
                return {"error": "Invalid course outline: missing required week fields", "valid": False, "raw": result}

        result["valid"] = True
        return result

    def generate_quiz_questions(
        self,
        topic: str,
        day_content: str,
        difficulty: str = "medium",
        num_questions: int = 5,
    ) -> Dict[str, Any]:
        """
        Generate quiz questions for a day's content.

        Args:
            topic: Quiz topic
            day_content: The lesson content to quiz on
            difficulty: easy/medium/hard
            num_questions: Number of questions to generate

        Returns:
            JSON: [{question_text, question_type, options, correct_answer, explanation, difficulty, concept_tags}]
        """
        prompt = f"""Generate {num_questions} quiz questions based on the following content:

Topic: {topic}
Difficulty: {difficulty}

Content:
{day_content[:3000]}

Return a JSON array with this exact structure:
[
    {{
        "question_text": "The question?",
        "question_type": "multiple_choice",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_answer": 0,
        "explanation": "Why this answer is correct",
        "difficulty": "{difficulty}",
        "concept_tags": ["concept1", "concept2"]
    }}
]

Return ONLY valid JSON array, no markdown, no explanation."""

        result = self._generate_json(prompt, max_tokens=3000)

        # Validate structure
        if not isinstance(result, list):
            if "error" in result:
                return result
            return {"error": "Invalid quiz format: expected array", "valid": False, "raw": result}

        for i, q in enumerate(result):
            required = ["question_text", "options", "correct_answer"]
            missing = [k for k in required if k not in q]
            if missing:
                return {"error": f"Question {i} missing fields: {missing}", "valid": False, "raw": result}

        return {"questions": result, "valid": True}

    def generate_day_content(
        self,
        topic: str,
        day_title: str,
        week_theme: str,
        skill_level: str,
    ) -> str:
        """
        Generate structured lesson content for a day.

        Args:
            topic: Course topic
            day_title: Title for this day's lesson
            week_theme: Theme of the current week
            skill_level: Beginner/Intermediate/Advanced

        Returns:
            Structured lesson content string (markdown)
        """
        system_prompt = """You are an expert educational content creator.
Create clear, engaging lesson content with:
- Learning objectives at the start
- Code examples where relevant
- Practical exercises
- Summary at the end
Use markdown formatting for better readability."""

        prompt = f"""Create a lesson for the following:

Topic: {topic}
Week Theme: {week_theme}
Day Title: {day_title}
Skill Level: {skill_level}

Create comprehensive lesson content (400-600 words) that includes:
1. Learning objectives
2. Main content with explanations
3. Code examples (if relevant)
4. Practical exercises
5. Summary

Format using markdown with headers, bullet points, and code blocks."""

        return self.generate(prompt, max_tokens=2000, system_prompt=system_prompt)

    def check_health(self) -> bool:
        """
        Check if OpenRouter API is accessible.

        Returns:
            True if healthy, False otherwise
        """
        # OpenRouter doesn't have a health endpoint, just check if we can reach it
        url = f"{self.base_url}/models"
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            with httpx.Client(timeout=5.0, headers=headers) as client:
                response = client.get(url)
                return response.status_code in [200, 401]  # 401 means API key issue but server is up
        except Exception as exc:
            logger.warning("OpenRouter health check failed: %s", exc)
            return False


# Convenience function for quick access
_client = None


def get_client() -> QwenClient:
    """Get or create QwenClient singleton."""
    global _client
    if _client is None:
        _client = QwenClient()
    return _client
