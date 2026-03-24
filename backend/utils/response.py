"""
Standardized response helpers for Django REST Framework views.
All API responses use consistent format.
"""
from rest_framework import status
from rest_framework.response import Response
from typing import Any, Optional, Union, Dict, List


def success_response(
    data: Union[Dict, List, Any],
    status_code: int = status.HTTP_200_OK,
    message: Optional[str] = None,
) -> Response:
    """
    Return a standardized success response.
    
    Format:
    {
        "success": true,
        "data": {...},
        "message": "Optional message"  # Only if message is provided
    }
    """
    response_data = {
        "success": True,
        "data": data,
    }
    if message:
        response_data["message"] = message
    
    return Response(response_data, status=status_code)


def error_response(
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    errors: Optional[Dict] = None,
) -> Response:
    """
    Return a standardized error response.
    
    Format:
    {
        "success": false,
        "error": "Error message",
        "code": 400,
        "errors": {...}  # Only if errors is provided
    }
    """
    response_data = {
        "success": False,
        "error": message,
        "code": status_code,
    }
    if errors:
        response_data["errors"] = errors
    
    return Response(response_data, status=status_code)


def paginated_response(
    data: List,
    total: int,
    page: int,
    page_size: int,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    """
    Return a paginated response with metadata.
    
    Format:
    {
        "success": true,
        "data": [...],
        "pagination": {
            "total": 100,
            "page": 1,
            "page_size": 20,
            "total_pages": 5
        }
    }
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    
    return Response(
        {
            "success": True,
            "data": data,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            },
        },
        status=status_code,
    )


def created_response(
    data: Union[Dict, List, Any],
    message: str = "Resource created successfully",
) -> Response:
    """Return a 201 Created response."""
    return success_response(data, status.HTTP_201_CREATED, message)


def no_content_response() -> Response:
    """Return a 204 No Content response."""
    return Response(status=status.HTTP_204_NO_CONTENT)


def accepted_response(
    data: Union[Dict, List, Any],
    message: str = "Request accepted for processing",
) -> Response:
    """Return a 202 Accepted response for async operations."""
    return success_response(data, status.HTTP_202_ACCEPTED, message)


# Shorthand aliases
_ok = success_response
_err = error_response
_created = created_response
_no_content = no_content_response
_accepted = accepted_response
