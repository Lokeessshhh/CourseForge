"""
Clerk JWT Authentication for Django REST Framework + Django Channels.

Flow:
  1. Client sends Authorization: Bearer <clerk_jwt>
  2. ClerkAuthentication.authenticate() verifies the JWT against Clerk's JWKS endpoint
  3. Returns (user_obj, token) where user_obj is fetched/created from our DB
  4. ClerkWebSocketMiddleware does the same for WebSocket connections

Webhook Verification:
  1. Clerk sends webhook with svix-id, svix-timestamp, svix-signature headers
  2. verify_clerk_webhook() validates signature using HMAC-SHA256
  3. Timestamp must be within 5 minutes (replay attack prevention)
"""
import logging
import threading
import time
from typing import Optional, Tuple

import httpx
from django.conf import settings
from django.core.cache import cache
from jose import jwt, JWTError
from svix.webhooks import Webhook
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


_CLERK_USER_CACHE: dict[str, tuple[float, dict]] = {}
_CLERK_USER_CACHE_LOCK = threading.Lock()
_CLERK_USER_CACHE_TTL_SECONDS = 300

# ──────────────────────────────────────────────
# JWKS cache (Redis-backed with 1-hour TTL)
# ──────────────────────────────────────────────
JWKS_CACHE_KEY = "clerk:jwks"
JWKS_CACHE_TTL = 3600  # 1 hour


def _fetch_jwks() -> dict:
    """Fetch Clerk JWKS and cache in Redis."""
    # Try cache first
    cached = cache.get(JWKS_CACHE_KEY)
    if cached:
        return cached

    # Fetch from Clerk
    url = settings.CLERK_JWKS_URL
    with httpx.Client(timeout=10) as client:
        resp = client.get(url)
        resp.raise_for_status()
        jwks = resp.json()

    # Cache for 1 hour
    cache.set(JWKS_CACHE_KEY, jwks, JWKS_CACHE_TTL)
    return jwks


def _clear_jwks_cache():
    """Clear JWKS cache (on key rotation)."""
    cache.delete(JWKS_CACHE_KEY)


def verify_clerk_jwt(token: str) -> dict:
    """
    Verify a Clerk-issued JWT.
    Returns the decoded payload on success, raises AuthenticationFailed on failure.
    """
    try:
        # Get JWKS
        jwks = _fetch_jwks()

        # Decode header to find kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # Find matching key in JWKS
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = key
                break

        if not rsa_key:
            # Key not found; JWKS might be stale — clear cache and retry once
            _clear_jwks_cache()
            jwks = _fetch_jwks()
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = key
                    break

        if not rsa_key:
            raise AuthenticationFailed("JWT signing key not found in JWKS.")

        # Verify and decode
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Clerk JWTs don't always have aud
        )
        return payload

    except JWTError as exc:
        logger.warning("Clerk JWT verification failed: %s", exc)
        raise AuthenticationFailed(f"Invalid token: {exc}")
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch Clerk JWKS: %s", exc)
        raise AuthenticationFailed("Authentication service unavailable.")


# ──────────────────────────────────────────────
# Auth Rate Limiting
# ──────────────────────────────────────────────
def check_auth_rate_limit(ip: str) -> bool:
    """
    Check if IP is within auth rate limit.
    Returns True if allowed, False if rate limited.
    Max 10 failed attempts per minute per IP.
    """
    key = f"auth:failures:{ip}"
    failures = cache.get(key, 0)
    return failures < 10


def record_auth_failure(ip: str):
    """Record an auth failure for rate limiting."""
    key = f"auth:failures:{ip}"
    failures = cache.get(key, 0)
    cache.set(key, failures + 1, timeout=60)  # 1 minute window

    if failures + 1 >= 10:
        # Block IP for 5 minutes
        block_key = f"auth:blocked:{ip}"
        cache.set(block_key, True, timeout=300)
        logger.warning("IP %s blocked for too many auth failures", ip)


def is_ip_blocked(ip: str) -> bool:
    """Check if IP is blocked."""
    return bool(cache.get(f"auth:blocked:{ip}"))


# ──────────────────────────────────────────────
# DRF Authentication class
# ──────────────────────────────────────────────
class ClerkAuthentication(BaseAuthentication):
    """
    DRF authentication backend that validates Clerk JWTs.
    Returns the local User model instance corresponding to the Clerk user.
    """

    def authenticate(self, request: Request) -> Optional[Tuple]:
        # Get client IP for rate limiting
        ip = self._get_client_ip(request)

        # Check if blocked
        if is_ip_blocked(ip):
            raise AuthenticationFailed("Too many failed attempts. Please try again later.")

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None  # Let next authenticator try

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return None

        try:
            payload = verify_clerk_jwt(token)
            user = self._get_or_create_user(payload)
            return (user, token)
        except AuthenticationFailed:
            # Record failure for rate limiting
            record_auth_failure(ip)
            raise

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"

    @staticmethod
    def _get_or_create_user(payload: dict):
        """Retrieve or lazily create our DB user from a Clerk payload."""
        from apps.users.models import User  # avoid circular import

        clerk_user_id = payload.get("sub", "")
        email = payload.get("email", "") or _extract_email(payload)
        name = _extract_name(payload)

        if (not email or not name) and clerk_user_id:
            try:
                profile = _fetch_clerk_user_profile(clerk_user_id)
                email = email or _extract_email_from_clerk_user(profile)
                name = name or _extract_name_from_clerk_user(profile)
            except Exception:
                # Don't break auth if Clerk lookup fails; fall back to blank fields.
                logger.exception("Failed fetching Clerk profile for %s", clerk_user_id)

        logger.info("JWT payload keys: %s", list(payload.keys()))
        logger.info("Extracted email: %s, name: %s for clerk_id: %s", email, name, clerk_user_id)

        # Clerk user ID stored in the `clerk_id` field (added to our User model)
        user, created = User.objects.get_or_create(
            clerk_id=clerk_user_id,
            defaults={"email": email, "name": name, "skill_level": "beginner"},
        )
        if not created and (user.email != email or user.name != name):
            # Keep in sync with Clerk
            user.email = email
            user.name = name
            user.save(update_fields=["email", "name"])

        if created:
            logger.info("Auto-created user from JWT: %s (email: %s)", clerk_user_id, email)

        return user

    def get_user(self, user_id):
        from apps.users.models import User
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


def _extract_email(payload: dict) -> str:
    """Try various Clerk payload structures for email."""
    # Clerk often includes email in nested dict
    for key in ("email_address", "primary_email_address", "email"):
        if key in payload:
            val = payload[key]
            if isinstance(val, str):
                return val
            if isinstance(val, list) and val:
                return val[0].get("email_address", "")
    return ""


def _extract_name(payload: dict) -> str:
    first = payload.get("first_name", "") or ""
    last = payload.get("last_name", "") or ""
    return f"{first} {last}".strip()


def _fetch_clerk_user_profile(clerk_user_id: str) -> dict:
    """Fetch Clerk user profile via Clerk Backend API.

    This is used when the session JWT doesn't include email/name claims.
    """
    cached = None
    now = time.time()
    with _CLERK_USER_CACHE_LOCK:
        cached = _CLERK_USER_CACHE.get(clerk_user_id)
        if cached and (now - cached[0]) < _CLERK_USER_CACHE_TTL_SECONDS:
            return cached[1]

    secret = getattr(settings, "CLERK_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("CLERK_SECRET_KEY not configured")

    url = f"https://api.clerk.com/v1/users/{clerk_user_id}"
    headers = {"Authorization": f"Bearer {secret}"}
    timeout = 10
    resp = httpx.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    with _CLERK_USER_CACHE_LOCK:
        _CLERK_USER_CACHE[clerk_user_id] = (now, data)

    return data


def _extract_email_from_clerk_user(user: dict) -> str:
    primary_id = user.get("primary_email_address_id")
    emails = user.get("email_addresses") or []
    if isinstance(emails, list):
        if primary_id:
            for item in emails:
                if item.get("id") == primary_id:
                    return item.get("email_address", "") or ""
        if emails:
            return emails[0].get("email_address", "") or ""
    return ""


def _extract_name_from_clerk_user(user: dict) -> str:
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    full = f"{first} {last}".strip()
    if full:
        return full
    username = user.get("username") or ""
    return username


# ──────────────────────────────────────────────
# Django Channels WebSocket middleware
# ──────────────────────────────────────────────
class ClerkWebSocketMiddleware(BaseMiddleware):
    """
    Channels middleware that authenticates the WebSocket handshake via a
    Clerk JWT passed as a query-string parameter: ?token=<jwt>
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = _parse_token_from_qs(query_string)

        if token:
            try:
                payload = verify_clerk_jwt(token)
                user = await database_sync_to_async(
                    ClerkAuthentication._get_or_create_user
                )(payload)
                scope["user"] = user
                scope["clerk_payload"] = payload
            except AuthenticationFailed as exc:
                scope["user"] = None
                scope["auth_error"] = str(exc)
        else:
            scope["user"] = None

        return await super().__call__(scope, receive, send)


def _parse_token_from_qs(qs: str) -> Optional[str]:
    """Extract `token` from URL query string."""
    for part in qs.split("&"):
        if part.startswith("token="):
            return part[6:]
    return None


# ──────────────────────────────────────────────
# Webhook Verification (Svix)
# ──────────────────────────────────────────────
def verify_clerk_webhook(request) -> dict:
    """
    Verify a Clerk webhook request using Svix signature.

    Headers required:
    - svix-id: Unique message ID
    - svix-timestamp: Unix timestamp
    - svix-signature: HMAC-SHA256 signature

    Returns payload dict on success.
    Raises WebhookVerificationException on failure.
    """
    from utils.exceptions import WebhookVerificationException

    # Get webhook secret
    secret = settings.CLERK_WEBHOOK_SECRET
    if not secret:
        logger.error("CLERK_WEBHOOK_SECRET not configured")
        raise WebhookVerificationException("Webhook secret not configured")

    # Build headers dict (Svix expects lowercase header keys)
    headers = {
        "svix-id": request.META.get("HTTP_SVIX_ID", ""),
        "svix-timestamp": request.META.get("HTTP_SVIX_TIMESTAMP", ""),
        "svix-signature": request.META.get("HTTP_SVIX_SIGNATURE", ""),
    }

    if not all(headers.values()):
        logger.warning("Webhook missing required Svix headers")
        raise WebhookVerificationException("Missing webhook verification headers")

    # Get raw payload
    payload_bytes = getattr(request, "body", b"")
    if not payload_bytes and hasattr(request, "data"):
        import json

        payload_bytes = json.dumps(request.data).encode("utf-8")
    if not payload_bytes:
        raise WebhookVerificationException("Cannot read request body")

    # Verify using Svix SDK
    try:
        wh = Webhook(secret)
        verified_payload = wh.verify(payload_bytes, headers)
    except Exception as exc:
        logger.warning("Webhook signature verification failed: %s", exc)
        raise WebhookVerificationException("Invalid webhook signature")

    # Svix returns the JSON payload (dict)
    if isinstance(verified_payload, (dict, list)):
        return verified_payload

    # Fallback: attempt JSON decode
    import json

    try:
        if isinstance(verified_payload, (bytes, bytearray)):
            return json.loads(verified_payload.decode("utf-8"))
        return json.loads(str(verified_payload))
    except Exception as exc:
        raise WebhookVerificationException("Invalid JSON payload") from exc


def verify_clerk_webhook_view(request):
    """
    Wrapper for webhook verification in views.
    Returns (success: bool, payload: dict or None, error: str or None)
    """
    try:
        payload = verify_clerk_webhook(request)
        return True, payload, None
    except Exception as e:
        return False, None, str(e)
