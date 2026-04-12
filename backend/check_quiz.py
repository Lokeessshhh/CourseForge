import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from apps.quizzes.models import QuizQuestion

# Filter for Week 2, Day 2
questions = QuizQuestion.objects.filter(week_number=2, day_number=2).order_by('id')

print(f"Found {questions.count()} questions for Week 2, Day 2")
for i, q in enumerate(questions):
    print(f"\n--- Q{i+1} (ID: {q.id}) ---")
    print(f"Question: {q.question_text[:80]}")
    print(f"Correct Answer (DB): {repr(q.correct_answer)}")
    # Print options if they are a dict
    if isinstance(q.options, dict):
        for k, v in q.options.items():
            print(f"  {k}: {v[:40]}...")
    else:
        print(f"  Options: {q.options}")
