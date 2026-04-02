"""
LLM Client for vLLM server.
Uses AsyncOpenAI client compatible with vLLM/OpenAI API.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List

import httpx
from openai import AsyncOpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

# vLLM Server Configuration
BASE_URL = getattr(settings, "VLLM_BASE_URL", "http://localhost:8000")
if not BASE_URL.rstrip("/").endswith("/v1"):
    BASE_URL = BASE_URL.rstrip("/") + "/v1"
MODEL_NAME = "qwen-coder"
API_KEY = "none"

TIMEOUT_SECONDS = getattr(settings, "VLLM_TIMEOUT_SECONDS", 120)
SDK_MAX_RETRIES = getattr(settings, "VLLM_SDK_MAX_RETRIES", 0)

# Configure httpx client with proper connection limits
# Increased limits to handle concurrent weekly test generation tasks
# Each Celery task runs in its own thread with asyncio.run(), so we need enough connections
http_client = httpx.AsyncClient(
    timeout=TIMEOUT_SECONDS,
    limits=httpx.Limits(
        max_connections=100,      # Total connections across all hosts (increased from 50)
        max_keepalive_connections=50,  # Keep connections alive for reuse (increased from 20)
        keepalive_expiry=60,     # Close idle connections after 60s (increased from 30s)
    ),
)

# Initialize async client with custom http_client
client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
    http_client=http_client,
    max_retries=SDK_MAX_RETRIES,
)

# System prompts for different use cases
SYSTEM_PROMPTS = {
    "tutor": """You are an expert coding tutor on an AI learning platform.
Your job is to teach students clearly and effectively.
Rules:
- Always explain concepts simply before showing code
- Always include working code examples with explanations
- Point out common mistakes students make
- Be encouraging and patient
- If student is struggling, use analogies and simpler terms
- Format responses with markdown
- End with: "Try this yourself: [simple exercise]" """,

    "course_generator": """You are a senior curriculum designer specializing in technical education.
Your job is to create structured, progressive learning content.
Rules:
- Content must be appropriate for the specified skill level
- Each concept must build on the previous one
- Include practical examples for every concept
- Return ONLY valid JSON when asked for JSON
- No extra text outside JSON when JSON is requested
- Make content engaging and real-world focused""",

    "quiz_generator": """You are an expert at creating educational assessments.
Rules:
- Questions must test genuine understanding, not just memory
- Wrong options must be plausible (not obviously wrong)
- Explanations must teach, not just state the answer
- Mix conceptual and practical questions
- Return ONLY valid JSON, no extra text
- Never repeat the same question style twice in a row""",

    "code_teacher": """You are an expert programming instructor.
Your job is to teach code through examples.
Rules:
- Always show complete, runnable code examples
- Explain every line that might confuse a learner
- Show the output of the code
- Point out what NOT to do and why
- Include at least one real-world use case
- Format all code in proper markdown code blocks""",

    "weekly_test": """You are a senior technical examiner.
Your job is to create comprehensive weekly assessments.
Rules:
- Questions must cover ALL topics from the week
- Mix difficulty: 40% easy, 40% medium, 20% hard
- Each question tests a different concept
- Explanations must reference which day's content it covers
- Return ONLY valid JSON, no extra text""",

    "coding_test": """You are an expert at creating coding challenges.
Rules:
- Problems must test practical coding skills
- Include clear problem descriptions with examples
- Provide starter code with function signatures
- Test cases must cover edge cases
- Difficulty must match the specified level
- Return ONLY valid JSON, no extra text""",

    "chat": """You are a helpful AI tutor assistant.
You have access to the student's course materials and history.
Rules:
- Answer based on the course context provided
- Reference specific lessons when relevant
- If you don't know → say so honestly
- Keep responses concise but complete
- Always offer to elaborate if needed""",

    "topic_detector": """You are a topic extraction specialist.
Your job is to identify the main subject from course names.
Rules:
- Return ONLY a short topic phrase (2-4 words)
- No explanations, no extra text
- Focus on the core technical subject""",
}

# Generation parameters for different use cases
GENERATION_PARAMS = {
    "course":   {"temperature": 0.3, "max_tokens": 3000, "top_p": 0.9},
    "quiz":     {"temperature": 0.4, "max_tokens": 2000, "top_p": 0.85},
    "content":  {"temperature": 0.5, "max_tokens": 3000, "top_p": 0.9},
    "chat":     {"temperature": 0.7, "max_tokens": 1000, "top_p": 0.95},
    "code":     {"temperature": 0.2, "max_tokens": 2000, "top_p": 0.85},
    "test":     {"temperature": 0.3, "max_tokens": 3000, "top_p": 0.85},
    "topic":    {"temperature": 0.1, "max_tokens": 50, "top_p": 0.9},
}


async def generate(
    prompt: str,
    system_type: str = "tutor",
    param_type: str = "content",
    extra_context: str = "",
    conversation_history: List[Dict] = None,
) -> str:
    """
    Generate a response from the LLM.

    Args:
        prompt: User prompt/question
        system_type: Key from SYSTEM_PROMPTS
        param_type: Key from GENERATION_PARAMS
        extra_context: Additional context to inject
        conversation_history: List of previous messages

    Returns:
        Generated response string
    """
    params = GENERATION_PARAMS.get(param_type, GENERATION_PARAMS["content"])
    system_prompt = SYSTEM_PROMPTS.get(system_type, SYSTEM_PROMPTS["tutor"])

    messages = [{"role": "system", "content": system_prompt}]

    if extra_context:
        messages.append({
            "role": "system",
            "content": f"Context:\n{extra_context}"
        })

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": prompt})

    # Increased retries from 3 to 5 for better reliability with longer backoff
    for attempt in range(5):
        try:
            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                **params
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.warning("LLM generation attempt %d/5 failed: %s", attempt + 1, e)
            if attempt == 4:
                logger.exception("LLM generation failed after 5 attempts")
                raise
            # Exponential backoff with longer delays (2, 4, 8, 16 seconds)
            await asyncio.sleep(2 ** (attempt + 1))


async def stream_generate(
    prompt: str,
    system_type: str = "chat",
    extra_context: str = "",
    conversation_history: List[Dict] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream generate a response from the LLM.

    Yields tokens as they arrive.
    """
    params = GENERATION_PARAMS.get("chat", GENERATION_PARAMS["chat"])
    system_prompt = SYSTEM_PROMPTS.get(system_type, SYSTEM_PROMPTS["chat"])

    messages = [{"role": "system", "content": system_prompt}]

    if extra_context:
        messages.append({
            "role": "system",
            "content": f"Course context:\n{extra_context}"
        })

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": prompt})

    try:
        stream = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            stream=True,
            **params
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    except Exception as e:
        logger.exception("Stream generation failed: %s", e)
        yield f"[Error: {str(e)}]"


async def safe_json_generate(
    prompt: str,
    system_type: str = "course_generator",
    param_type: str = "course",
    expected_keys: List[str] = None,
    max_retries: int = 5,  # Increased from 3 to 5 for better reliability
) -> Dict:
    """
    Generate JSON response with validation and retry logic.
    Uses json-repair to handle malformed JSON from LLM.

    Args:
        prompt: User prompt
        system_type: System prompt key
        param_type: Generation params key
        expected_keys: Keys that must exist in response
        max_retries: Number of retry attempts

    Returns:
        Parsed JSON dict or error dict
    """
    if expected_keys is None:
        expected_keys = []

    raw = ""

    for attempt in range(max_retries):
        try:
            raw = await generate(prompt, system_type, param_type)

            # Clean up response
            cleaned = raw.strip()

            # Extract JSON from markdown code blocks
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                parts = cleaned.split("```")
                if len(parts) >= 2:
                    cleaned = parts[1]
                    # Remove language identifier if present
                    if cleaned.startswith("json\n"):
                        cleaned = cleaned[5:]
                    elif cleaned.startswith("json"):
                        cleaned = cleaned[4:]

            cleaned = cleaned.strip()

            # Remove any trailing text after the JSON object
            # Find the last closing brace and truncate there
            if cleaned.endswith("}"):
                # Find matching braces
                brace_count = 0
                last_valid_pos = -1
                for i, char in enumerate(cleaned):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            last_valid_pos = i
                            break
                
                if last_valid_pos > 0 and last_valid_pos < len(cleaned) - 1:
                    cleaned = cleaned[:last_valid_pos + 1]
            
            # Try standard json.loads first (faster)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                # Fall back to json-repair for malformed JSON
                try:
                    from json_repair import repair_json
                    logger.info("Standard JSON parse failed, attempting repair...")
                    repaired = repair_json(cleaned)
                    parsed = json.loads(repaired)
                    logger.info("JSON repair successful!")
                except ImportError:
                    logger.warning("json-repair not installed, using standard parser only")
                    raise
                except Exception as repair_error:
                    logger.warning("JSON repair also failed: %s", repair_error)
                    raise

            # Validate expected keys
            for key in expected_keys:
                if key not in parsed:
                    raise ValueError(f"Missing required key: {key}")

            return parsed

        except json.JSONDecodeError as e:
            logger.warning("JSON parse error (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt == max_retries - 1:
                return {"error": f"JSON parse error: {str(e)}", "raw": raw}
            await asyncio.sleep(1.5)  # Slightly longer delay for retry

        except ValueError as e:
            logger.warning("Validation error (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt == max_retries - 1:
                return {"error": str(e), "raw": raw}
            await asyncio.sleep(1.5)

        except Exception as e:
            logger.exception("Unexpected error in safe_json_generate: %s", e)
            if attempt == max_retries - 1:
                return {"error": str(e), "raw": raw}
            await asyncio.sleep(1.5)

    return {"error": "Max retries exceeded", "raw": raw}


async def generate_with_retry(
    prompt: str,
    system_type: str = "tutor",
    param_type: str = "content",
    max_retries: int = 3,
    validate_fn: callable = None,
) -> str:
    """
    Generate with custom validation and retry logic.

    Args:
        prompt: User prompt
        system_type: System prompt key
        param_type: Generation params key
        max_retries: Number of retry attempts
        validate_fn: Optional validation function

    Returns:
        Generated response string
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            response = await generate(prompt, system_type, param_type)

            if validate_fn:
                is_valid, error = validate_fn(response)
                if not is_valid:
                    raise ValueError(error)

            return response

        except Exception as e:
            last_error = e
            logger.warning("Generation attempt %d failed: %s", attempt + 1, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

    raise last_error


def get_system_prompt(system_type: str) -> str:
    """Get system prompt by type."""
    return SYSTEM_PROMPTS.get(system_type, SYSTEM_PROMPTS["tutor"])


def get_generation_params(param_type: str) -> Dict:
    """Get generation params by type."""
    return GENERATION_PARAMS.get(param_type, GENERATION_PARAMS["content"])


# Synchronous wrapper for Celery tasks
def generate_sync(
    prompt: str,
    system_type: str = "tutor",
    param_type: str = "content",
    extra_context: str = "",
) -> str:
    """
    Synchronous wrapper for use in Celery tasks.
    ALWAYS creates a fresh event loop to avoid "loop is closed" errors.
    """
    # Always create a fresh event loop for Celery tasks
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            generate(prompt, system_type, param_type, extra_context)
        )
    finally:
        loop.close()


def safe_json_generate_sync(
    prompt: str,
    system_type: str = "course_generator",
    param_type: str = "course",
    expected_keys: List[str] = None,
) -> Dict:
    """
    Synchronous JSON generation for Celery tasks.
    ALWAYS creates a fresh event loop to avoid "loop is closed" errors.
    """
    # Always create a fresh event loop for Celery tasks
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            safe_json_generate(prompt, system_type, param_type, expected_keys)
        )
    finally:
        loop.close()
