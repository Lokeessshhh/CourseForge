"""
Security and utility middleware for Django.
Includes security headers, request logging, and rate limiting.
"""
import json
import logging
import time
from typing import Callable

from django.http import HttpRequest, HttpResponse
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """
    Add security headers to every response.
    Must be placed early in MIDDLEWARE.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # Security headers
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        return response


class RequestLoggingMiddleware:
    """
    Log all requests with structured JSON format.
    Skip logging for health endpoint.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Skip health endpoint
        if request.path == "/api/health/":
            return self.get_response(request)

        start_time = time.time()

        # Get user info
        user_id = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user_id = str(request.user.id)

        # Get client IP
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "")

        # Process request
        response = self.get_response(request)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Log as structured JSON
        log_data = {
            "method": request.method,
            "path": request.path,
            "query": dict(request.GET),
            "user_id": user_id,
            "ip": ip,
            "status": response.status_code,
            "latency_ms": round(latency_ms, 2),
            "content_length": len(response.content) if hasattr(response, "content") else 0,
        }

        if response.status_code >= 400:
            logger.warning("Request: %s", json.dumps(log_data))
        else:
            logger.info("Request: %s", json.dumps(log_data))

        return response


class RateLimitMiddleware:
    """
    Global rate limiting middleware using Redis.
    Limits: 1000 requests per hour per IP.
    Returns 429 with Retry-After header when exceeded.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.enabled = getattr(settings, "RATE_LIMIT_ENABLED", True)
        self.requests_per_hour = getattr(settings, "RATE_LIMIT_REQUESTS_PER_HOUR", 1000)
        self.block_duration_seconds = getattr(settings, "RATE_LIMIT_BLOCK_DURATION", 3600)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Skip if rate limiting disabled (development)
        if not self.enabled:
            return self.get_response(request)

        # Skip health endpoint
        if request.path == "/api/health/":
            return self.get_response(request)

        # Get client IP
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "")

        # Check if IP is blocked
        block_key = f"ratelimit:blocked:{ip}"
        if cache.get(block_key):
            return self._rate_limit_response()

        # Check request count
        count_key = f"ratelimit:count:{ip}"
        count = cache.get_or_set(count_key, 0, timeout=3600)

        if count >= self.requests_per_hour:
            # Block the IP
            cache.set(block_key, True, timeout=self.block_duration_seconds)
            logger.warning("Rate limit exceeded for IP: %s", ip)
            return self._rate_limit_response()

        # Increment count
        cache.incr(count_key)

        return self.get_response(request)

    def _rate_limit_response(self) -> JsonResponse:
        """Return 429 Too Many Requests."""
        response = JsonResponse(
            {
                "success": False,
                "error": "Rate limit exceeded. Please try again later.",
                "code": 429,
            },
            status=429,
        )
        response["Retry-After"] = "3600"
        return response


class AuthRateLimitMiddleware:
    """
    Rate limiting specifically for authentication failures.
    Max 10 failed auth attempts per IP per minute.
    Block IP for 5 minutes after 10 failures.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.enabled = getattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
        self.max_failures = getattr(settings, "AUTH_RATE_LIMIT_MAX_FAILURES", 10)
        self.window_seconds = getattr(settings, "AUTH_RATE_LIMIT_WINDOW", 60)
        self.block_duration = getattr(settings, "AUTH_RATE_LIMIT_BLOCK_DURATION", 300)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Skip if disabled
        if not self.enabled:
            return self.get_response(request)

        # Only check auth endpoints
        auth_paths = ["/api/auth/", "/api/login/", "/api/token/"]
        if not any(request.path.startswith(p) for p in auth_paths):
            return self.get_response(request)

        # Get client IP
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "")

        # Check if blocked
        block_key = f"auth:blocked:{ip}"
        if cache.get(block_key):
            logger.warning("Auth rate limit: IP %s is blocked", ip)
            return JsonResponse(
                {
                    "success": False,
                    "error": "Too many failed authentication attempts. Please try again later.",
                    "code": 429,
                },
                status=429,
            )

        response = self.get_response(request)

        # Track failures (401 responses)
        if response.status_code == 401:
            fail_key = f"auth:failures:{ip}"
            failures = cache.get_or_set(fail_key, 0, timeout=self.window_seconds)
            failures = cache.incr(fail_key) if failures > 0 else 1

            if failures >= self.max_failures:
                cache.set(block_key, True, timeout=self.block_duration)
                cache.delete(fail_key)
                logger.warning(
                    "Auth rate limit: IP %s blocked after %d failures",
                    ip, failures
                )

        return response
