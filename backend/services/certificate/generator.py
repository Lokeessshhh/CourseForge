"""
Certificate generation service.
Generates PDF certificates using WeasyPrint.
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class CertificateGenerator:
    """
    Generates PDF certificates for completed courses.
    Uses WeasyPrint for PDF generation.
    """

    async def generate_certificate(
        self,
        user_id: str,
        course_id: str,
    ) -> Dict[str, Any]:
        """
        Generate a certificate for a completed course.

        Args:
            user_id: User ID
            course_id: Course ID

        Returns:
            Dict with certificate info and download URL
        """
        from apps.courses.models import Course, CourseProgress
        from apps.certificates.models import Certificate

        try:
            course = Course.objects.get(id=course_id)
            progress = CourseProgress.objects.get(user_id=user_id, course=course)

            # Calculate final stats
            final_score = round(
                (progress.avg_quiz_score + progress.avg_test_score) / 2, 1
            ) if progress.avg_test_score > 0 else progress.avg_quiz_score

            total_hours = round(progress.total_study_time / 60, 1)

            # Generate PDF
            pdf_url = await self._generate_pdf(
                user_name=course.user.name or course.user.email,
                course_topic=course.topic,
                completion_date=progress.completed_at or timezone.now(),
                final_score=final_score,
                total_hours=total_hours,
                user_id=user_id,
                course_id=course_id,
            )

            # Update or create certificate record
            cert, _ = Certificate.objects.update_or_create(
                user_id=user_id,
                course=course,
                defaults={
                    "is_unlocked": True,
                    "quiz_score_avg": progress.avg_quiz_score,
                    "test_score_avg": progress.avg_test_score,
                    "total_study_hours": total_hours,
                    "issued_at": timezone.now(),
                    "pdf_url": pdf_url,
                }
            )

            logger.info("Generated certificate for user %s course %s", user_id, course_id)

            return {
                "success": True,
                "certificate_id": str(cert.id),
                "download_url": pdf_url,
                "stats": {
                    "avg_quiz_score": progress.avg_quiz_score,
                    "avg_test_score": progress.avg_test_score,
                    "total_study_hours": total_hours,
                    "completion_days": progress.completed_days,
                }
            }

        except Exception as exc:
            logger.exception("Error generating certificate: %s", exc)
            return {"success": False, "error": str(exc)}

    async def _generate_pdf(
        self,
        user_name: str,
        course_topic: str,
        completion_date: datetime,
        final_score: float,
        total_hours: float,
        user_id: str,
        course_id: str,
    ) -> str:
        """
        Generate PDF certificate using WeasyPrint.

        Returns:
            URL path to the generated PDF
        """
        from services.external.weasyprint_cert import CertificateService

        try:
            # Create certificate service
            cert_service = CertificateService()

            # Generate certificate
            result = cert_service.generate_certificate(
                student_name=user_name,
                course_name=course_topic,
                completion_date=completion_date.strftime("%B %d, %Y"),
                final_score=final_score,
                total_hours=total_hours,
            )

            if result.get("success"):
                return result.get("download_url", "")

            # Fallback: generate simple HTML-based PDF
            return await self._generate_simple_pdf(
                user_name, course_topic, completion_date, final_score, total_hours,
                user_id, course_id
            )

        except Exception as exc:
            logger.warning("WeasyPrint failed, using fallback: %s", exc)
            return await self._generate_simple_pdf(
                user_name, course_topic, completion_date, final_score, total_hours,
                user_id, course_id
            )

    async def _generate_simple_pdf(
        self,
        user_name: str,
        course_topic: str,
        completion_date: datetime,
        final_score: float,
        total_hours: float,
        user_id: str,
        course_id: str,
    ) -> str:
        """
        Generate a simple HTML certificate as fallback.

        Returns:
            URL path to the generated HTML
        """
        # Create media directory
        cert_dir = os.path.join(settings.MEDIA_ROOT, "certificates", user_id)
        os.makedirs(cert_dir, exist_ok=True)

        # Generate unique filename
        filename = f"{course_id}.html"
        filepath = os.path.join(cert_dir, filename)

        # Generate HTML content
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Certificate of Completion</title>
    <style>
        body {{
            font-family: 'Georgia', serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 0;
            padding: 20px;
        }}
        .certificate {{
            background: white;
            padding: 60px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 800px;
        }}
        .title {{
            font-size: 36px;
            color: #333;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 3px;
        }}
        .subtitle {{
            font-size: 18px;
            color: #666;
            margin-bottom: 40px;
        }}
        .student-name {{
            font-size: 32px;
            color: #667eea;
            margin-bottom: 20px;
            font-weight: bold;
        }}
        .course-name {{
            font-size: 24px;
            color: #333;
            margin-bottom: 40px;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-bottom: 40px;
        }}
        .stat {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 28px;
            color: #667eea;
            font-weight: bold;
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
        }}
        .date {{
            font-size: 16px;
            color: #666;
            margin-top: 40px;
        }}
        .badge {{
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            color: white;
            font-size: 36px;
        }}
    </style>
</head>
<body>
    <div class="certificate">
        <div class="badge">✓</div>
        <div class="title">Certificate of Completion</div>
        <div class="subtitle">This certifies that</div>
        <div class="student-name">{user_name}</div>
        <div class="subtitle">has successfully completed the course</div>
        <div class="course-name">{course_topic}</div>
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{final_score}%</div>
                <div class="stat-label">Final Score</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_hours}h</div>
                <div class="stat-label">Study Time</div>
            </div>
        </div>
        <div class="date">Completed on {completion_date.strftime('%B %d, %Y')}</div>
    </div>
</body>
</html>"""

        # Write file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Return URL path
        return f"/media/certificates/{user_id}/{filename}"

    def get_certificate(self, user_id: str, course_id: str) -> Optional[Dict[str, Any]]:
        """
        Get certificate info for a course.

        Returns:
            Certificate data or None
        """
        from apps.certificates.models import Certificate

        try:
            cert = Certificate.objects.get(user_id=user_id, course_id=course_id)

            return {
                "is_unlocked": cert.is_unlocked,
                "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
                "download_url": cert.pdf_url,
                "stats": {
                    "avg_quiz_score": cert.quiz_score_avg,
                    "avg_test_score": cert.test_score_avg,
                    "total_study_hours": cert.total_study_hours,
                }
            }

        except Certificate.DoesNotExist:
            return None


# Singleton instance
_generator = None


def get_generator() -> CertificateGenerator:
    """Get the certificate generator instance."""
    global _generator
    if _generator is None:
        _generator = CertificateGenerator()
    return _generator
