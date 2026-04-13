"""Quizzes — Background task: auto-generate quiz questions for a day."""
import json
import logging
import time

logger = logging.getLogger(__name__)


def generate_quiz_for_day(day_plan_id: str):
    """Call Qwen 7B to generate quiz questions for a given DayPlan."""
    MAX_RETRIES = 2
    RETRY_DELAY = 30

    for attempt in range(MAX_RETRIES):
        try:
            from apps.courses.models import DayPlan
            from apps.quizzes.models import QuizQuestion
            from services.llm.qwen_client import QwenClient

            day = DayPlan.objects.select_related("week_plan__course").get(id=day_plan_id)
            course = day.week_plan.course
            tasks = day.tasks or {}
            study_content = tasks.get("study_content", "")

            client = QwenClient()
            prompt = f"""Generate 5 quiz questions for this study content.
Return ONLY valid JSON array, no explanation:
[
  {{
    "question_text": "...",
    "question_type": "mcq",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct_answer": "A",
    "explanation": "...",
    "difficulty": 2,
    "concept_tags": ["tag1", "tag2"]
  }}
]

Study Content:
{study_content[:3000]}"""

            raw = client.generate(prompt, max_tokens=3000)
            questions_data = _parse_json(raw)

            for q_data in questions_data:
                QuizQuestion.objects.create(
                    course=course,
                    week_number=day.week_plan.week_number,
                    day_number=day.day_number,
                    question_text=q_data.get("question_text", ""),
                    question_type=q_data.get("question_type", "mcq"),
                    options=q_data.get("options"),
                    correct_answer=q_data.get("correct_answer", ""),
                    explanation=q_data.get("explanation", ""),
                    difficulty=q_data.get("difficulty", 2),
                    concept_tags=q_data.get("concept_tags", []),
                )

            logger.info("Generated %d quiz questions for day %s", len(questions_data), day_plan_id)
            break  # Success
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                logger.exception("generate_quiz_for_day failed after %d retries: %s", MAX_RETRIES, exc)
                raise
            logger.warning("generate_quiz_for_day attempt %d failed, retrying in %ds: %s", attempt + 1, RETRY_DELAY, exc)
            time.sleep(RETRY_DELAY)


def _parse_json(raw: str) -> list:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return []
