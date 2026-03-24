"""
WeasyPrint certificate generation service.
Generates PDF certificates for course completion.
"""
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime
import base64

from django.utils import timezone

logger = logging.getLogger(__name__)


class CertificateService:
    """
    Certificate generation service using WeasyPrint.
    Creates professional PDF certificates for course completion.
    """

    DEFAULT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: A4 landscape;
            margin: 0;
        }
        
        body {
            font-family: 'Georgia', serif;
            margin: 0;
            padding: 40px;
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
        }
        
        .certificate {
            border: 15px double #2c5282;
            padding: 40px;
            text-align: center;
            background: white;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            min-height: 500px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        
        .header {
            font-size: 14px;
            color: #666;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-bottom: 20px;
        }
        
        .title {
            font-size: 48px;
            color: #2c5282;
            font-weight: bold;
            margin-bottom: 30px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        }
        
        .recipient {
            font-size: 36px;
            color: #1a365d;
            font-style: italic;
            margin-bottom: 20px;
            border-bottom: 2px solid #2c5282;
            padding-bottom: 10px;
            display: inline-block;
        }
        
        .course-name {
            font-size: 24px;
            color: #4a5568;
            margin-bottom: 30px;
        }
        
        .completion-text {
            font-size: 16px;
            color: #666;
            line-height: 1.8;
            margin-bottom: 40px;
        }
        
        .details {
            display: flex;
            justify-content: space-around;
            margin-top: 30px;
        }
        
        .detail-item {
            text-align: center;
        }
        
        .detail-label {
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .detail-value {
            font-size: 18px;
            color: #2c5282;
            font-weight: bold;
            margin-top: 5px;
        }
        
        .signature {
            margin-top: 50px;
            font-style: italic;
            color: #666;
        }
        
        .certificate-id {
            font-size: 10px;
            color: #999;
            margin-top: 30px;
        }
        
        .badge {
            width: 80px;
            height: 80px;
            margin: 0 auto 20px;
            background: linear-gradient(135deg, #2c5282, #4299e1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 40px;
        }
    </style>
</head>
<body>
    <div class="certificate">
        <div class="header">Certificate of Completion</div>
        <div class="badge">✓</div>
        <div class="title">LearnAI Academy</div>
        
        <p class="completion-text">
            This is to certify that
        </p>
        
        <div class="recipient">{{ user_name }}</div>
        
        <p class="completion-text">
            has successfully completed the course
        </p>
        
        <div class="course-name">{{ course_name }}</div>
        
        <p class="completion-text">
            with an average score of {{ average_score }}%<br>
            demonstrating proficiency in the subject matter.
        </p>
        
        <div class="details">
            <div class="detail-item">
                <div class="detail-label">Issue Date</div>
                <div class="detail-value">{{ issue_date }}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Duration</div>
                <div class="detail-value">{{ duration }} weeks</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">Skill Level</div>
                <div class="detail-value">{{ skill_level }}</div>
            </div>
        </div>
        
        <div class="signature">
            Authorized by LearnAI Academy
        </div>
        
        <div class="certificate-id">
            Certificate ID: {{ certificate_id }}
        </div>
    </div>
</body>
</html>
    """

    def __init__(self, template: Optional[str] = None):
        """
        Initialize certificate service.
        
        Args:
            template: Optional custom HTML template
        """
        self.template = template or self.DEFAULT_TEMPLATE
        self._weasyprint = None

    def _get_weasyprint(self):
        """Lazy import WeasyPrint."""
        if self._weasyprint is None:
            try:
                from weasyprint import HTML, CSS
                self._weasyprint = (HTML, CSS)
            except ImportError:
                logger.error("WeasyPrint not installed. Install with: pip install weasyprint")
                raise RuntimeError("WeasyPrint not installed")
        return self._weasyprint

    def generate_certificate(
        self,
        user_name: str,
        course_name: str,
        certificate_id: str,
        average_score: float,
        duration: int,
        skill_level: str = "Beginner",
        issue_date: Optional[datetime] = None,
        output_path: Optional[str] = None,
    ) -> bytes:
        """
        Generate a PDF certificate.
        
        Args:
            user_name: Name of the certificate recipient
            course_name: Name of the completed course
            certificate_id: Unique certificate identifier
            average_score: Average quiz score percentage
            duration: Course duration in weeks
            skill_level: Course skill level
            issue_date: Certificate issue date (defaults to now)
            output_path: Optional path to save PDF
            
        Returns:
            PDF content as bytes
        """
        HTML, CSS = self._get_weasyprint()
        
        if issue_date is None:
            issue_date = timezone.now()
        
        # Render template
        html_content = self.template.replace("{{ user_name }}", user_name)
        html_content = html_content.replace("{{ course_name }}", course_name)
        html_content = html_content.replace("{{ certificate_id }}", certificate_id)
        html_content = html_content.replace("{{ average_score }}", str(round(average_score)))
        html_content = html_content.replace("{{ duration }}", str(duration))
        html_content = html_content.replace("{{ skill_level }}", skill_level)
        html_content = html_content.replace("{{ issue_date }}", issue_date.strftime("%B %d, %Y"))
        
        # Generate PDF
        html = HTML(string=html_content)
        pdf = html.write_pdf()
        
        # Save to file if path provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(pdf)
            logger.info("Certificate saved to %s", output_path)
        
        return pdf

    def generate_certificate_base64(
        self,
        user_name: str,
        course_name: str,
        certificate_id: str,
        average_score: float,
        duration: int,
        skill_level: str = "Beginner",
        issue_date: Optional[datetime] = None,
    ) -> str:
        """
        Generate certificate and return as base64 string.
        
        Args:
            user_name: Name of the certificate recipient
            course_name: Name of the completed course
            certificate_id: Unique certificate identifier
            average_score: Average quiz score percentage
            duration: Course duration in weeks
            skill_level: Course skill level
            issue_date: Certificate issue date
            
        Returns:
            Base64 encoded PDF string
        """
        pdf_bytes = self.generate_certificate(
            user_name=user_name,
            course_name=course_name,
            certificate_id=certificate_id,
            average_score=average_score,
            duration=duration,
            skill_level=skill_level,
            issue_date=issue_date,
        )
        
        return base64.b64encode(pdf_bytes).decode("utf-8")

    def generate_certificate_for_course(
        self,
        user_id: str,
        course_id: str,
    ) -> Dict[str, Any]:
        """
        Generate certificate for a completed course.
        
        Args:
            user_id: User ID
            course_id: Course ID
            
        Returns:
            Dict with certificate data
        """
        from apps.users.models import User
        from apps.courses.models import Course
        from apps.certificates.models import Certificate
        
        try:
            user = User.objects.get(id=user_id)
            course = Course.objects.get(id=course_id)
            
            # Check if certificate already exists
            cert, created = Certificate.objects.get_or_create(
                user=user,
                course=course,
                defaults={"certificate_url": ""},
            )
            
            # Generate certificate ID
            certificate_id = f"LA-{course_id[:8].upper()}-{user_id[:8].upper()}"
            
            # Calculate average score from course progress
            total_score = 0
            quiz_count = 0
            for week in course.weeks.all():
                for day in week.days.all():
                    if day.quiz_score is not None:
                        total_score += day.quiz_score
                        quiz_count += 1
            
            average_score = round(total_score / quiz_count) if quiz_count else 0
            
            # Generate PDF
            pdf_base64 = self.generate_certificate_base64(
                user_name=user.name or user.email,
                course_name=course.name,
                certificate_id=certificate_id,
                average_score=average_score,
                duration=course.total_weeks,
                skill_level=course.skill_level or "Beginner",
            )
            
            # Update certificate URL
            cert.certificate_url = f"data:application/pdf;base64,{pdf_base64}"
            cert.save()
            
            return {
                "success": True,
                "certificate_id": certificate_id,
                "pdf_base64": pdf_base64,
                "issued_at": cert.issued_at.isoformat(),
            }
            
        except Exception as e:
            logger.exception("Certificate generation failed: %s", e)
            return {
                "success": False,
                "error": str(e),
            }


def generate_certificate(
    user_name: str,
    course_name: str,
    certificate_id: str,
    average_score: float,
    duration: int,
    **kwargs,
) -> bytes:
    """
    Convenience function for certificate generation.
    
    Args:
        user_name: Recipient name
        course_name: Course name
        certificate_id: Unique ID
        average_score: Score percentage
        duration: Duration in weeks
        **kwargs: Additional arguments
        
    Returns:
        PDF bytes
    """
    service = CertificateService()
    return service.generate_certificate(
        user_name=user_name,
        course_name=course_name,
        certificate_id=certificate_id,
        average_score=average_score,
        duration=duration,
        **kwargs,
    )
