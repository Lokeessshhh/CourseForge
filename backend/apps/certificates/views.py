"""
Certificates app — views.
Endpoints:
  GET  /api/certificates/              - List all certificates (locked & unlocked)
  GET  /api/certificates/locked/       - List locked certificates
  GET  /api/certificates/unlocked/     - List earned certificates
  GET  /api/courses/{id}/certificate/  - Get certificate for specific course
  POST /api/certificates/{id}/verify/  - Verify certificate authenticity
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Certificate
from .serializers import CertificateSerializer

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def certificate_list(request):
    """All certificates for the current user (both locked and unlocked) with progress data."""
    from apps.courses.models import Course, CourseProgress

    # Get all courses for this user
    courses = Course.objects.filter(user_id=request.user.id).order_by('-created_at')

    logger.info("Found %d courses for user %s", courses.count(), request.user.id)

    certs = []
    for course in courses:
        # Get course progress
        progress = CourseProgress.objects.filter(
            user=request.user,
            course=course
        ).first()

        completion_percentage = progress.overall_percentage if progress else 0

        cert = Certificate.objects.filter(user=request.user, course=course).first()

        if cert and cert.is_unlocked:
            # Certificate unlocked (course complete)
            certs.append({
                "id": str(cert.id),
                "course_id": str(course.id),
                "course_name": course.course_name,
                "topic": course.topic[:50] + "..." if len(course.topic) > 50 else course.topic,
                "is_unlocked": True,
                "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
                "quiz_score_avg": cert.quiz_score_avg,
                "test_score_avg": cert.test_score_avg,
                "total_study_hours": cert.total_study_hours,
                "completion_percentage": 100,
            })
        else:
            # Certificate locked (course in progress)
            certs.append({
                "id": str(cert.id) if cert else None,
                "course_id": str(course.id),
                "course_name": course.course_name,
                "topic": course.topic[:50] + "..." if len(course.topic) > 50 else course.topic,
                "is_unlocked": False,
                "issued_at": None,
                "quiz_score_avg": 0,
                "test_score_avg": 0,
                "total_study_hours": 0,
                "completion_percentage": completion_percentage,
            })

    logger.info("Returning %d certificates for user %s", len(certs), request.user.id)
    return _ok(certs)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def locked_certificates(request):
    """List locked certificates (courses not yet completed)."""
    from apps.courses.models import Course
    
    courses = Course.objects.filter(user=request.user).order_by('-created_at')
    locked = []
    
    for course in courses:
        cert = Certificate.objects.filter(user=request.user, course=course).first()
        
        if not cert or not cert.is_unlocked:
            locked.append({
                "course_id": str(course.id),
                "course_name": course.course_name,
                "topic": course.topic,
                "progress": "in_progress",
            })
    
    return _ok(locked)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unlocked_certificates(request):
    """List earned (unlocked) certificates."""
    certs = Certificate.objects.filter(user=request.user, is_unlocked=True).select_related("course")
    return _ok(CertificateSerializer(certs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_certificate(request, course_id):
    """Get certificate info for a specific course."""
    from apps.courses.models import Course, CourseProgress
    from apps.certificates.models import Certificate

    try:
        user_id = str(request.user.id)
        logger.info(f"Certificate view: user={user_id}, course={course_id}")

        course = Course.objects.get(id=course_id)
        cert = Certificate.objects.filter(user_id=user_id, course=course).first()

        logger.info(f"Certificate found: {cert is not None}, unlocked={cert.is_unlocked if cert else None}")

        if cert and cert.is_unlocked:
            user_full_name = getattr(request.user, "name", None) or ""
            email_name = request.user.email.split('@')[0] if request.user.email else ""
            student_name = user_full_name or email_name

            # If PDF hasn't been generated yet, trigger generation
            if not cert.pdf_url:
                from apps.courses.tasks import generate_certificate_task
                generate_certificate_task.delay(user_id, course_id)
                logger.info(f"Triggered PDF generation for certificate {cert.id}")
                return _ok({
                    "is_unlocked": True,
                    "certificate_id": str(cert.id),
                    "course_name": course.course_name,
                    "student_name": student_name,
                    "final_score": cert.quiz_score_avg,
                    "avg_test_score": cert.test_score_avg,
                    "total_study_hours": cert.total_study_hours,
                    "total_days": course.total_days,
                    "completion_date": cert.issued_at.strftime("%Y-%m-%d") if cert.issued_at else None,
                    "days_taken": 0,
                    "download_url": None,
                    "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
                    "status": "generating",
                    "message": "Certificate PDF is being generated. Please refresh in a moment.",
                    "instructor_name": "Dr. AURA (AI Unified Research Assistant)",
                    "director_name": "Prof. COGNITO (Cognitive Optimization & Guidance Intelligence)",
                })

            return _ok({
                "is_unlocked": True,
                "certificate_id": str(cert.id),
                "course_name": course.course_name,
                "student_name": student_name,
                "final_score": cert.quiz_score_avg,
                "avg_test_score": cert.test_score_avg,
                "total_study_hours": cert.total_study_hours,
                "total_days": course.total_days,
                "completion_date": cert.issued_at.strftime("%Y-%m-%d") if cert.issued_at else None,
                "days_taken": 0,
                "download_url": cert.pdf_url,
                "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
                "status": "ready",
                "instructor_name": "Dr. AURA (AI Unified Research Assistant)",
                "director_name": "Prof. COGNITO (Cognitive Optimization & Guidance Intelligence)",
            })

        # Certificate not unlocked yet
        progress = CourseProgress.objects.filter(user_id=user_id, course=course).first()

        if progress and progress.is_completed:
            # Eligible but cert not generated yet
            from apps.courses.tasks import generate_certificate_task
            generate_certificate_task.delay(user_id, course_id)
            return _ok({
                "is_unlocked": True,
                "status": "generating",
                "message": "Certificate is being generated. Please refresh in a moment."
            })

        return _ok({
            "is_unlocked": False,
            "issued_at": None,
            "download_url": None,
            "stats": None,
            "completion_progress": progress.completion_percentage if progress else 0,
            "completed_weeks": progress.completed_weeks if progress else 0,
            "total_weeks": progress.total_weeks if progress else 0,
            "is_completed": progress.is_completed if progress else False,
        })

    except Exception as exc:
        logger.exception("Error getting certificate: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([])  # Public endpoint for verification
def verify_certificate(request, certificate_id):
    """Verify certificate authenticity (public endpoint)."""
    from apps.certificates.models import Certificate
    import uuid
    
    try:
        # Try to find certificate by ID
        cert_uuid = uuid.UUID(certificate_id)
        cert = Certificate.objects.select_related('user', 'course').get(id=cert_uuid)
        
        return _ok({
            "valid": True,
            "certificate_id": str(cert.id),
            "student_name": f"{cert.user.first_name} {cert.user.last_name}".strip() or cert.user.email.split('@')[0],
            "course_name": cert.course.course_name,
            "course_topic": cert.course.topic,
            "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
            "final_score": round((cert.quiz_score_avg + cert.test_score_avg) / 2, 1) if cert.test_score_avg > 0 else cert.quiz_score_avg,
            "total_study_hours": cert.total_study_hours,
            "is_unlocked": cert.is_unlocked,
        })
        
    except (uuid.UUIDError, Certificate.DoesNotExist):
        return _ok({
            "valid": False,
            "message": "Certificate not found or invalid"
        })
    except Exception as exc:
        logger.exception("Error verifying certificate: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
