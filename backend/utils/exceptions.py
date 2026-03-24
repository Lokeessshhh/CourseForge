"""
Custom exception handler for Django REST Framework.
All errors return a consistent JSON format with detailed information.
"""
import logging
import traceback
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns consistent JSON format.

    Error response format:
    {
        "success": false,
        "error": "Human readable message",
        "code": 400,
        "details": {} // optional field-level errors
    }

    Never exposes:
    - Stack traces in production
    - Internal file paths
    - Database errors
    - Model/field names
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        error_message = _extract_error_message(response.data)
        details = _extract_details(response.data)
        error_code = _map_error_code(exc, response.status_code)

        response.data = {
            "success": False,
            "error": error_message,
            "code": error_code,
        }

        if details:
            response.data["details"] = details

        # Log the error with context
        request = context.get("request")
        path = request.path if request else "unknown"

        logger.error(
            "API Error [%d]: %s %s - %s",
            response.status_code,
            request.method if request else "?",
            path,
            error_message,
        )

    return response


def _extract_error_message(data) -> str:
    """Extract human-readable error message from response data."""
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"])
        if "message" in data:
            return str(data["message"])
        # Join all error messages
        messages = []
        for key, value in data.items():
            if key in ("success", "code", "details"):
                continue
            if isinstance(value, list):
                messages.extend([str(v) for v in value])
            else:
                messages.append(str(value))
        return "; ".join(messages) if messages else "An error occurred."
    elif isinstance(data, list):
        return "; ".join(str(item) for item in data)
    return str(data)


def _extract_details(data) -> dict:
    """Extract field-level error details."""
    if not isinstance(data, dict):
        return {}

    details = {}
    for key, value in data.items():
        if key in ("detail", "message", "success", "code"):
            continue
        if isinstance(value, list):
            details[key] = value
        elif isinstance(value, dict):
            details[key] = value
        else:
            details[key] = [str(value)]

    return details if details else {}


def _map_error_code(exc, status_code: int) -> int:
    """Map exception to appropriate HTTP status code."""
    # Already have the status code from DRF
    return status_code


# ─────────────────────────────────────────────────────────────
# Custom Exceptions
# ─────────────────────────────────────────────────────────────

class ServiceException(APIException):
    """Base exception for service-layer errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A service error occurred."
    default_code = "service_error"


class BadRequestException(ServiceException):
    """400 Bad Request - validation or input errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid request parameters."
    default_code = "bad_request"


class UnauthorizedException(ServiceException):
    """401 Unauthorized - missing or invalid authentication."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Authentication required."
    default_code = "unauthorized"


class ForbiddenException(ServiceException):
    """403 Forbidden - ownership violation or permission denied."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to access this resource."
    default_code = "forbidden"


class NotFoundException(ServiceException):
    """404 Not Found - resource not found."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "The requested resource was not found."
    default_code = "not_found"


class RateLimitException(ServiceException):
    """429 Too Many Requests - rate limit exceeded."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Rate limit exceeded. Please try again later."
    default_code = "rate_limited"


class LLMServiceException(ServiceException):
    """503 Service Unavailable - LLM service down."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "AI service is temporarily unavailable. Please try again."
    default_code = "llm_unavailable"


class RAGServiceException(ServiceException):
    """500 Internal Server Error - RAG pipeline error."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "An internal error occurred."
    default_code = "rag_error"


class CourseGenerationException(ServiceException):
    """500 Internal Server Error - course generation failed."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Course generation failed. Please try again."
    default_code = "course_generation_error"


class CertificateException(ServiceException):
    """500 Internal Server Error - certificate generation failed."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Certificate generation failed."
    default_code = "certificate_error"


class DatabaseException(ServiceException):
    """500 Internal Server Error - database error."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "A database error occurred. Please try again."
    default_code = "database_error"


class WebhookVerificationException(ServiceException):
    """400 Bad Request - webhook signature verification failed."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Webhook verification failed."
    default_code = "webhook_verification_failed"


# ─────────────────────────────────────────────────────────────
# Exception Handler for Non-DRF Exceptions
# ─────────────────────────────────────────────────────────────

def handle_unexpected_exception(exc, context=None):
    """
    Handle unexpected exceptions not caught by DRF.
    Returns a safe error response without exposing internals.
    """
    # Log full traceback for debugging
    logger.exception(
        "Unexpected exception: %s\nContext: %s\nTraceback:\n%s",
        str(exc),
        context,
        traceback.format_exc()
    )

    # Return safe error message
    return {
        "success": False,
        "error": "An unexpected error occurred. Please try again.",
        "code": 500,
    }
