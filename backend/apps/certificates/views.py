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
    """All certificates for the current user (both locked and unlocked)."""
    from apps.courses.models import Course
    
    # Get all courses for this user - use filter with user_id
    courses = Course.objects.filter(user_id=request.user.id).order_by('-created_at')
    
    logger.info("Found %d courses for user %s", courses.count(), request.user.id)
    
    certs = []
    for course in courses:
        cert = Certificate.objects.filter(user=request.user, course=course).first()
        
        if cert:
            certs.append({
                "id": str(cert.id),
                "course_id": str(course.id),
                "course_name": course.course_name,
                "topic": course.topic[:50] + "..." if len(course.topic) > 50 else course.topic,
                "is_unlocked": cert.is_unlocked,
                "issued_at": cert.issued_at.isoformat() if cert.issued_at else None,
                "quiz_score_avg": cert.quiz_score_avg,
                "test_score_avg": cert.test_score_avg,
                "total_study_hours": cert.total_study_hours,
            })
        else:
            # No certificate record yet - course in progress
            certs.append({
                "id": None,
                "course_id": str(course.id),
                "course_name": course.course_name,
                "topic": course.topic[:50] + "..." if len(course.topic) > 50 else course.topic,
                "is_unlocked": False,
                "issued_at": None,
                "quiz_score_avg": 0,
                "test_score_avg": 0,
                "total_study_hours": 0,
                "status": "in_progress"
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
    from services.certificate.generator import CertificateGenerator
    from apps.courses.models import Course

    try:
        generator = CertificateGenerator()
        cert_data = generator.get_certificate(str(request.user.id), course_id)

        if not cert_data:
            # Check if user is eligible but cert hasn't been created yet
            from apps.courses.models import CourseProgress
            
            progress = CourseProgress.objects.filter(
                user=request.user, 
                course_id=course_id
            ).first()
            
            if progress and progress.is_completed:
                # Eligible! Generate it now.
                from apps.courses.tasks import generate_certificate_task
                generate_certificate_task.delay(str(request.user.id), course_id)
                return _ok({
                    "is_unlocked": True,
                    "status": "generating",
                    "message": "Certificate is being generated. Please refresh in a moment."
                })
            
            # Not eligible yet
            return _ok({
                "is_unlocked": False,
                "issued_at": None,
                "download_url": None,
                "stats": None,
                "completion_progress": progress.completion_percentage if progress else 0,
            })

        # Add more fields expected by frontend
        course = Course.objects.get(id=course_id)

        cert_data.update({
            "certificate_id": cert_data.get("download_url", "").split("/")[-1].split(".")[0] if cert_data.get("download_url") else "CERT-" + str(course_id)[:8],
            "course_name": course.course_name,
            "student_name": f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email.split('@')[0],
            "final_score": cert_data["stats"]["avg_quiz_score"],
            "avg_test_score": cert_data["stats"]["avg_test_score"],
            "total_study_hours": cert_data["stats"]["total_study_hours"],
            "total_days": course.total_days,
            "completion_date": cert_data["issued_at"][:10] if cert_data.get("issued_at") else None,
            "days_taken": 0,
        })

        return _ok(cert_data)

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
