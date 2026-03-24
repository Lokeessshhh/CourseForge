"""
LangGraph flows for multi-step agentic LLM operations.
Used for complex generation tasks that need validation and retry logic.
"""
import asyncio
import json
import logging
from typing import List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from django.conf import settings

logger = logging.getLogger(__name__)

# LLM Configuration
BASE_URL = getattr(settings, "VLLM_BASE_URL", "http://localhost:8000")
if not BASE_URL.rstrip("/").endswith("/v1"):
    BASE_URL = BASE_URL.rstrip("/") + "/v1"
MODEL_NAME = "qwen-coder"
API_KEY = "none"

# Initialize LangChain LLM
llm = ChatOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
    model=MODEL_NAME,
    temperature=0.3,
    max_tokens=3000,
)


# ═══════════════════════════════════════════════════════════════════════════
# FLOW 1: Course Generation Flow
# ═══════════════════════════════════════════════════════════════════════════

class CourseState(TypedDict):
    """State for course generation flow."""
    topic: str
    skill_level: str
    duration_weeks: int
    goals: List[str]
    week_skeletons: List[dict]
    filled_weeks: List[dict]
    validation_errors: List[str]
    retry_count: int
    final_course: Optional[dict]


def build_skeleton_node(state: CourseState) -> dict:
    """Create empty week/day structure."""
    duration_weeks = state["duration_weeks"]

    week_skeletons = []
    for week_num in range(1, duration_weeks + 1):
        days = []
        for day_num in range(1, 6):  # 5 days per week
            days.append({
                "day_number": day_num,
                "title": None,
                "tasks": {},
                "is_locked": not (week_num == 1 and day_num == 1),
            })
        week_skeletons.append({
            "week_number": week_num,
            "theme": None,
            "objectives": [],
            "days": days,
        })

    return {"week_skeletons": week_skeletons}


def generate_week_themes_node(state: CourseState) -> dict:
    """Generate theme and objectives for each week."""
    topic = state["topic"]
    skill_level = state["skill_level"]
    duration_weeks = state["duration_weeks"]
    goals = state["goals"]
    week_skeletons = state["week_skeletons"]

    system_prompt = """You are a senior curriculum designer specializing in technical education.
Generate week themes and learning objectives for a course.
Return ONLY valid JSON with this structure:
{
  "weeks": [
    {
      "week_number": 1,
      "theme": "Week theme title",
      "objectives": ["Objective 1", "Objective 2", "Objective 3"]
    }
  ]
}"""

    prompt = f"""Create themes and objectives for a {duration_weeks}-week {skill_level} course on {topic}.
Learning goals: {', '.join(goals) if goals else 'General proficiency'}

Ensure progressive difficulty - each week builds on the previous.
Return JSON only."""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])

        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        # Update skeletons with themes
        for week_data in data.get("weeks", []):
            week_num = week_data["week_number"]
            if week_num <= len(week_skeletons):
                week_skeletons[week_num - 1]["theme"] = week_data.get("theme")
                week_skeletons[week_num - 1]["objectives"] = week_data.get("objectives", [])

        return {"week_skeletons": week_skeletons}

    except Exception as e:
        logger.exception("Error generating week themes: %s", e)
        return {"validation_errors": [f"Week theme generation failed: {str(e)}"]}


def generate_day_titles_node(state: CourseState) -> dict:
    """Generate titles for all days in each week."""
    topic = state["topic"]
    skill_level = state["skill_level"]
    week_skeletons = state["week_skeletons"]

    system_prompt = """You are a curriculum designer.
Generate day titles for a week of learning.
Return ONLY valid JSON with this structure:
{
  "days": [
    {"day_number": 1, "title": "Day title"},
    {"day_number": 2, "title": "Day title"},
    {"day_number": 3, "title": "Day title"},
    {"day_number": 4, "title": "Day title"},
    {"day_number": 5, "title": "Day title"}
  ]
}"""

    for week in week_skeletons:
        week_num = week["week_number"]
        week_theme = week.get("theme", f"Week {week_num}")

        # Get previous days for context
        previous_titles = []
        for prev_week in week_skeletons[:week_num - 1]:
            for day in prev_week.get("days", []):
                if day.get("title"):
                    previous_titles.append(day["title"])

        prompt = f"""Create 5 day titles for Week {week_num} of a {skill_level} {topic} course.
Week theme: {week_theme}
Previous days covered: {', '.join(previous_titles[-5:]) if previous_titles else 'None - this is the first week'}

Each day should build on the previous. Titles should be specific and actionable.
Return JSON only."""

        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])

            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

            # Update days with titles
            for day_data in data.get("days", []):
                day_num = day_data["day_number"]
                if day_num <= len(week["days"]):
                    week["days"][day_num - 1]["title"] = day_data.get("title")

        except Exception as e:
            logger.warning("Error generating day titles for week %d: %s", week_num, e)

    return {"week_skeletons": week_skeletons}


def validate_structure_node(state: CourseState) -> dict:
    """Validate the course structure."""
    week_skeletons = state["week_skeletons"]
    errors = []

    for week in week_skeletons:
        week_num = week["week_number"]

        # Check week has theme
        if not week.get("theme"):
            errors.append(f"Week {week_num} missing theme")

        # Check week has objectives
        if not week.get("objectives"):
            errors.append(f"Week {week_num} missing objectives")

        # Check all days have titles
        for day in week.get("days", []):
            if not day.get("title"):
                errors.append(f"Week {week_num} Day {day['day_number']} missing title")

    # Check for duplicate titles
    all_titles = []
    for week in week_skeletons:
        for day in week.get("days", []):
            title = day.get("title")
            if title:
                if title in all_titles:
                    errors.append(f"Duplicate title: {title}")
                all_titles.append(title)

    return {
        "validation_errors": errors,
        "retry_count": state.get("retry_count", 0),
    }


def fix_structure_node(state: CourseState) -> dict:
    """Fix validation errors by regenerating failed parts."""
    errors = state["validation_errors"]
    week_skeletons = state["week_skeletons"]
    retry_count = state.get("retry_count", 0) + 1

    if retry_count > 3:
        return {"retry_count": retry_count}

    # Re-generate themes for weeks with errors
    for week in week_skeletons:
        week_num = week["week_number"]
        week_errors = [e for e in errors if f"Week {week_num}" in e]

        if any("missing theme" in e for e in week_errors):
            # Regenerate theme
            prompt = f"""Generate a theme for Week {week_num} of a {state['skill_level']} {state['topic']} course.
Return only the theme title as plain text, no JSON."""

            try:
                response = llm.invoke([HumanMessage(content=prompt)])
                week["theme"] = response.content.strip().strip('"')
            except Exception:
                pass

        if any("missing title" in e for e in week_errors):
            # Regenerate day titles
            generate_day_titles_node({"week_skeletons": [week], "topic": state["topic"], "skill_level": state["skill_level"]})

    return {"week_skeletons": week_skeletons, "retry_count": retry_count}


def finalize_course_node(state: CourseState) -> dict:
    """Assemble final course dict."""
    return {
        "final_course": {
            "topic": state["topic"],
            "skill_level": state["skill_level"],
            "duration_weeks": state["duration_weeks"],
            "goals": state["goals"],
            "weeks": state["week_skeletons"],
        }
    }


def should_continue(state: CourseState) -> str:
    """Determine next node after validation."""
    errors = state.get("validation_errors", [])
    retry_count = state.get("retry_count", 0)

    if not errors:
        return "finalize"
    if retry_count >= 3:
        return "end"
    return "fix"


# Build Course Generation Graph
course_graph = StateGraph(CourseState)
course_graph.add_node("build_skeleton", build_skeleton_node)
course_graph.add_node("generate_week_themes", generate_week_themes_node)
course_graph.add_node("generate_day_titles", generate_day_titles_node)
course_graph.add_node("validate_structure", validate_structure_node)
course_graph.add_node("fix_structure", fix_structure_node)
course_graph.add_node("finalize_course", finalize_course_node)

course_graph.set_entry_point("build_skeleton")
course_graph.add_edge("build_skeleton", "generate_week_themes")
course_graph.add_edge("generate_week_themes", "generate_day_titles")
course_graph.add_edge("generate_day_titles", "validate_structure")
course_graph.add_conditional_edges("validate_structure", should_continue, {
    "finalize": "finalize_course",
    "fix": "fix_structure",
    "end": END,
})
course_graph.add_edge("fix_structure", "validate_structure")
course_graph.add_edge("finalize_course", END)

course_app = course_graph.compile()


async def run_course_flow(inputs: dict) -> dict:
    """Run the course generation flow."""
    try:
        result = await course_app.ainvoke(inputs)
        return result
    except Exception as e:
        logger.exception("Course flow failed: %s", e)
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# FLOW 2: RAG Chat Flow
# ═══════════════════════════════════════════════════════════════════════════

class ChatState(TypedDict):
    """State for RAG chat flow."""
    user_message: str
    course_id: str
    user_id: str
    conversation_history: List[dict]
    retrieved_chunks: List[str]
    memory_context: str
    knowledge_state: dict
    cache_hit: bool
    cached_response: Optional[str]
    final_response: str
    should_stream: bool


def cache_check_node(state: ChatState) -> dict:
    """Check semantic cache for similar queries."""
    import hashlib

    user_message = state["user_message"]
    course_id = state["course_id"]

    # Simple MD5 cache check (in production, use pgvector cosine similarity)
    cache_key = hashlib.md5(f"{course_id}:{user_message}".encode()).hexdigest()

    try:
        import redis
        from django.conf import settings

        r = redis.Redis.from_url(settings.REDIS_URL)
        cached = r.get(f"chat_cache:{cache_key}")

        if cached:
            return {
                "cache_hit": True,
                "cached_response": cached.decode("utf-8"),
            }
    except Exception:
        pass

    return {"cache_hit": False}


def memory_inject_node(state: ChatState) -> dict:
    """Inject 4-tier memory context."""
    user_id = state["user_id"]
    course_id = state["course_id"]

    memory_parts = []

    try:
        # Tier 1: Last 10 messages from DB
        from apps.chat.models import Conversation
        conversations = Conversation.objects.filter(
            user_id=user_id,
            course_id=course_id,
        ).order_by("-created_at")[:10]

        if conversations:
            history = list(reversed(list(conversations.values_list("content", flat=True))))
            memory_parts.append(f"Recent conversation:\n{chr(10).join(history[:5])}")

        # Tier 4: User knowledge state (weak concepts)
        from apps.users.models import UserKnowledgeState
        weak_concepts = UserKnowledgeState.objects.filter(
            user_id=user_id,
            confidence_score__lt=0.5,
        ).values_list("concept_tag", flat=True)[:5]

        if weak_concepts:
            memory_parts.append(f"Student's weak areas: {', '.join(weak_concepts)}")

    except Exception as e:
        logger.warning("Memory injection failed: %s", e)

    return {"memory_context": "\n\n".join(memory_parts)}


def retrieve_chunks_node(state: ChatState) -> dict:
    """Retrieve relevant chunks using hybrid retrieval."""
    user_message = state["user_message"]
    course_id = state["course_id"]

    chunks = []

    try:
        # Simple retrieval (in production, use HyDE + pgvector + BM25 + RRF)
        from apps.rag.models import DocumentChunk
        from pgvector.django import CosineDistance

        # Get course documents
        course_chunks = DocumentChunk.objects.filter(
            document__course_id=course_id,
        ).annotate(
            similarity=CosineDistance("embedding", user_message)
        ).order_by("similarity")[:10]

        chunks = [chunk.content for chunk in course_chunks]

    except Exception as e:
        logger.warning("Chunk retrieval failed: %s", e)

    return {"retrieved_chunks": chunks}


def rerank_node(state: ChatState) -> dict:
    """Rerank retrieved chunks."""
    # In production, use bge-reranker-v2-m3
    # For now, return top chunks as-is
    return {"retrieved_chunks": state["retrieved_chunks"][:10]}


def generate_response_node(state: ChatState) -> dict:
    """Generate response using LLM."""
    user_message = state["user_message"]
    memory_context = state.get("memory_context", "")
    retrieved_chunks = state.get("retrieved_chunks", [])
    history = state.get("conversation_history", [])

    system_prompt = """You are a helpful AI tutor assistant.
You have access to the student's course materials and history.
Rules:
- Answer based on the course context provided
- Reference specific lessons when relevant
- If you don't know → say so honestly
- Keep responses concise but complete
- Always offer to elaborate if needed"""

    context_parts = []
    if memory_context:
        context_parts.append(f"Memory context:\n{memory_context}")
    if retrieved_chunks:
        context_parts.append(f"Course materials:\n{chr(10).join(retrieved_chunks[:5])}")

    messages = [SystemMessage(content=system_prompt)]

    if context_parts:
        messages.append(SystemMessage(content="\n\n".join(context_parts)))

    # Add conversation history
    for msg in history[-5:]:
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=user_message))

    try:
        response = llm.invoke(messages)
        return {"final_response": response.content}
    except Exception as e:
        logger.exception("Response generation failed: %s", e)
        return {"final_response": "I apologize, I encountered an error. Please try again."}


def save_and_update_node(state: ChatState) -> dict:
    """Save conversation and update caches."""
    user_id = state["user_id"]
    course_id = state["course_id"]
    user_message = state["user_message"]
    final_response = state["final_response"]

    try:
        # Save to DB
        from apps.chat.models import Conversation
        Conversation.objects.create(
            user_id=user_id,
            course_id=course_id,
            role="user",
            content=user_message,
        )
        Conversation.objects.create(
            user_id=user_id,
            course_id=course_id,
            role="assistant",
            content=final_response,
        )

        # Update cache
        import hashlib
        cache_key = hashlib.md5(f"{course_id}:{user_message}".encode()).hexdigest()

        import redis
        from django.conf import settings
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.setex(f"chat_cache:{cache_key}", 3600, final_response)  # 1 hour TTL

    except Exception as e:
        logger.warning("Save failed: %s", e)

    return {}


def return_cache_node(state: ChatState) -> dict:
    """Return cached response."""
    return {"final_response": state["cached_response"]}


def check_cache(state: ChatState) -> str:
    """Route based on cache hit."""
    if state.get("cache_hit"):
        return "cache"
    return "retrieve"


# Build Chat Graph
chat_graph = StateGraph(ChatState)
chat_graph.add_node("cache_check", cache_check_node)
chat_graph.add_node("memory_inject", memory_inject_node)
chat_graph.add_node("retrieve_chunks", retrieve_chunks_node)
chat_graph.add_node("rerank", rerank_node)
chat_graph.add_node("generate_response", generate_response_node)
chat_graph.add_node("save_and_update", save_and_update_node)
chat_graph.add_node("return_cache", return_cache_node)

chat_graph.set_entry_point("cache_check")
chat_graph.add_conditional_edges("cache_check", check_cache, {
    "cache": "return_cache",
    "retrieve": "memory_inject",
})
chat_graph.add_edge("memory_inject", "retrieve_chunks")
chat_graph.add_edge("retrieve_chunks", "rerank")
chat_graph.add_edge("rerank", "generate_response")
chat_graph.add_edge("generate_response", "save_and_update")
chat_graph.add_edge("save_and_update", END)
chat_graph.add_edge("return_cache", END)

chat_app = chat_graph.compile()


async def run_chat_flow(inputs: dict) -> dict:
    """Run the RAG chat flow."""
    try:
        result = await chat_app.ainvoke(inputs)
        return result
    except Exception as e:
        logger.exception("Chat flow failed: %s", e)
        return {"final_response": "Error processing request", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# FLOW 3: Quiz Generation Flow
# ═══════════════════════════════════════════════════════════════════════════

class QuizState(TypedDict):
    """State for quiz generation flow."""
    topic: str
    day_title: str
    theory_content: str
    code_content: str
    difficulty: int
    generated_questions: List[dict]
    validation_passed: bool
    retry_count: int
    error_message: Optional[str]


def generate_questions_node(state: QuizState) -> dict:
    """Generate quiz questions."""
    topic = state["topic"]
    day_title = state["day_title"]
    theory_content = state.get("theory_content", "")
    code_content = state.get("code_content", "")

    system_prompt = """You are an expert at creating educational assessments.
Generate 3 MCQ questions for a day's learning content.
Return ONLY valid JSON with this structure:
{
  "quizzes": [
    {
      "question_number": 1,
      "question_text": "Question here?",
      "options": {
        "a": "Option A",
        "b": "Option B",
        "c": "Option C",
        "d": "Option D"
      },
      "correct_answer": "a",
      "explanation": "Why the answer is correct..."
    }
  ]
}"""

    prompt = f"""Create 3 MCQ questions for Day: {day_title}
Topic: {topic}

Theory content covered:
{theory_content[:1000] if theory_content else 'N/A'}

Code examples covered:
{code_content[:500] if code_content else 'N/A'}

Questions should test understanding of the concepts. Wrong options should be plausible.
Return JSON only."""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])

        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        questions = data.get("quizzes", [])

        return {"generated_questions": questions, "retry_count": 0}

    except Exception as e:
        logger.exception("Quiz generation failed: %s", e)
        return {"error_message": str(e), "generated_questions": []}


def validate_questions_node(state: QuizState) -> dict:
    """Validate generated questions."""
    questions = state.get("generated_questions", [])
    errors = []

    if not questions:
        return {"validation_passed": False, "error_message": "No questions generated"}

    for i, q in enumerate(questions):
        # Check all 4 options exist
        options = q.get("options", {})
        if len(options) != 4:
            errors.append(f"Question {i+1}: Must have exactly 4 options")
        if set(options.keys()) != {"a", "b", "c", "d"}:
            errors.append(f"Question {i+1}: Options must be a, b, c, d")

        # Check correct_answer is valid
        correct = q.get("correct_answer", "").lower()
        if correct not in ["a", "b", "c", "d"]:
            errors.append(f"Question {i+1}: Invalid correct_answer '{correct}'")

        # Check explanation exists
        if not q.get("explanation"):
            errors.append(f"Question {i+1}: Missing explanation")

        # Check question text
        if not q.get("question_text"):
            errors.append(f"Question {i+1}: Missing question text")

    # Check for duplicates
    question_texts = [q.get("question_text", "") for q in questions]
    if len(set(question_texts)) != len(question_texts):
        errors.append("Duplicate questions detected")

    if errors:
        return {
            "validation_passed": False,
            "error_message": "; ".join(errors),
            "retry_count": state.get("retry_count", 0),
        }

    return {"validation_passed": True}


def retry_node(state: QuizState) -> dict:
    """Handle retry logic."""
    retry_count = state.get("retry_count", 0) + 1

    if retry_count > 3:
        return {
            "retry_count": retry_count,
            "error_message": "Max retries exceeded",
        }

    return {"retry_count": retry_count}


def save_questions_node(state: QuizState) -> dict:
    """Save validated questions."""
    # In production, save to database
    return {"validation_passed": True}


def should_retry(state: QuizState) -> str:
    """Determine next action after validation."""
    if state.get("validation_passed"):
        return "save"
    if state.get("retry_count", 0) >= 3:
        return "end"
    return "retry"


# Build Quiz Graph
quiz_graph = StateGraph(QuizState)
quiz_graph.add_node("generate_questions", generate_questions_node)
quiz_graph.add_node("validate_questions", validate_questions_node)
quiz_graph.add_node("retry", retry_node)
quiz_graph.add_node("save_questions", save_questions_node)

quiz_graph.set_entry_point("generate_questions")
quiz_graph.add_edge("generate_questions", "validate_questions")
quiz_graph.add_conditional_edges("validate_questions", should_retry, {
    "save": "save_questions",
    "retry": "retry",
    "end": END,
})
quiz_graph.add_edge("retry", "generate_questions")
quiz_graph.add_edge("save_questions", END)

quiz_app = quiz_graph.compile()


async def run_quiz_flow(inputs: dict) -> dict:
    """Run the quiz generation flow."""
    try:
        result = await quiz_app.ainvoke(inputs)
        return result
    except Exception as e:
        logger.exception("Quiz flow failed: %s", e)
        return {"error": str(e), "generated_questions": []}


# ═══════════════════════════════════════════════════════════════════════════
# Synchronous wrappers for Celery
# ═══════════════════════════════════════════════════════════════════════════

def run_course_flow_sync(inputs: dict) -> dict:
    """Synchronous wrapper for course flow."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(run_course_flow(inputs))


def run_quiz_flow_sync(inputs: dict) -> dict:
    """Synchronous wrapper for quiz flow."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(run_quiz_flow(inputs))
