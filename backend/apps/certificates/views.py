"""
Certificates app — views.
Endpoints:
  GET  /api/certificates/
  GET  /api/courses/{id}/certificate/
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
    """All certificates for the current user."""
    certs = Certificate.objects.filter(user=request.user, is_unlocked=True).select_related("course", "user")
    return _ok(CertificateSerializer(certs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_certificate(request, course_id):
    """Get certificate info for a specific course."""
    from services.certificate.generator import CertificateGenerator

    try:
        generator = CertificateGenerator()
        cert_data = generator.get_certificate(str(request.user.id), course_id)

        if not cert_data:
            return _ok({
                "is_unlocked": False,
                "issued_at": None,
                "download_url": None,
                "stats": None,
            })

        return _ok(cert_data)

    except Exception as exc:
        logger.exception("Error getting certificate: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
