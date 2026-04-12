"""Test certificate API response."""
import os, django, json
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from apps.courses.models import Course
from apps.certificates.models import Certificate
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(id="c3525eeb-2f66-49cb-be79-363d36a16eb2")
course = Course.objects.get(id="bca97e4f-38b4-4e1f-a06d-0115c6c1e6a7")

cert = Certificate.objects.filter(user=user, course=course).first()
print(f"Certificate found: {cert is not None}")
if cert:
    print(f"  is_unlocked: {cert.is_unlocked}")
    print(f"  quiz_score_avg: {cert.quiz_score_avg}")
    print(f"  test_score_avg: {cert.test_score_avg}")
    print(f"  total_study_hours: {cert.total_study_hours}")
    print(f"  issued_at: {cert.issued_at}")
    print(f"  pdf_url: {cert.pdf_url}")
    print(f"\nSimulated API response:")
    response = {
        "success": True,
        "data": {
            "is_unlocked": cert.is_unlocked,
            "certificate_id": str(cert.id),
            "course_name": f"{course.course_name} ({course.topic})",
            "student_name": user.name or user.email.split('@')[0],
            "final_score": cert.quiz_score_avg,
            "avg_test_score": cert.test_score_avg,
            "total_study_hours": cert.total_study_hours,
            "total_days": course.total_days,
            "completion_date": cert.issued_at.strftime("%Y-%m-%d") if cert.issued_at else None,
            "days_taken": 0,
            "download_url": cert.pdf_url,
            "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
            "status": "ready",
        },
        "error": None,
    }
    print(json.dumps(response, indent=2))
else:
    print("No certificate found for this user/course")
