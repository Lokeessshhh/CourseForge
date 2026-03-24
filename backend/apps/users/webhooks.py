"""
Clerk webhook handler — POST /api/webhooks/clerk/
Handles user.created and user.updated events from Clerk.
"""
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.users.models import User

logger = logging.getLogger(__name__)


def _verify_clerk_signature(request) -> bool:
    """
    Verify Svix webhook signature (Clerk uses Svix).
    Headers: svix-id, svix-timestamp, svix-signature
    """
    secret = settings.CLERK_WEBHOOK_SECRET
    if not secret:
        logger.warning("CLERK_WEBHOOK_SECRET not set — skipping signature verification")
        return True  # dev mode

    svix_id = request.META.get("HTTP_SVIX_ID", "")
    svix_timestamp = request.META.get("HTTP_SVIX_TIMESTAMP", "")
    svix_signature = request.META.get("HTTP_SVIX_SIGNATURE", "")

    if not all([svix_id, svix_timestamp, svix_signature]):
        return False

    body = request.body.decode("utf-8")
    signed_content = f"{svix_id}.{svix_timestamp}.{body}"

    # Secret may be prefixed with "whsec_"
    raw_secret = secret
    if raw_secret.startswith("whsec_"):
        import base64
        raw_secret = base64.b64decode(raw_secret[6:])

    signature = hmac.new(
        raw_secret if isinstance(raw_secret, bytes) else raw_secret.encode(),
        signed_content.encode(),
        hashlib.sha256,
    ).digest()

    # Svix sends comma-separated signatures
    expected_sigs = [s.split(",", 1)[1] for s in svix_signature.split(" ") if "," in s]
    import base64
    computed = base64.b64encode(signature).decode()
    return computed in expected_sigs


@csrf_exempt
@require_POST
def clerk_webhook(request):
    """Clerk webhook endpoint."""
    if not _verify_clerk_signature(request):
        logger.warning("Clerk webhook signature verification failed")
        return JsonResponse({"error": "Invalid signature"}, status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    event_type = payload.get("type")
    data = payload.get("data", {})

    logger.info("Clerk webhook event: %s", event_type)

    if event_type == "user.created":
        _handle_user_created(data)
    elif event_type == "user.updated":
        _handle_user_updated(data)
    elif event_type == "user.deleted":
        _handle_user_deleted(data)

    return JsonResponse({"received": True})


def _extract_primary_email(data: dict) -> str:
    emails = data.get("email_addresses", [])
    primary_id = data.get("primary_email_address_id")
    for email_obj in emails:
        if email_obj.get("id") == primary_id:
            return email_obj.get("email_address", "")
    if emails:
        return emails[0].get("email_address", "")
    return ""


def _handle_user_created(data: dict):
    clerk_id = data.get("id", "")
    email = _extract_primary_email(data)
    first = data.get("first_name", "") or ""
    last = data.get("last_name", "") or ""
    name = f"{first} {last}".strip()

    user, created = User.objects.get_or_create(
        clerk_id=clerk_id,
        defaults={"email": email, "name": name},
    )
    if created:
        logger.info("Created user from Clerk webhook: %s", email)
    else:
        logger.info("User already exists for clerk_id=%s", clerk_id)


def _handle_user_updated(data: dict):
    clerk_id = data.get("id", "")
    email = _extract_primary_email(data)
    first = data.get("first_name", "") or ""
    last = data.get("last_name", "") or ""
    name = f"{first} {last}".strip()

    updated = User.objects.filter(clerk_id=clerk_id).update(email=email, name=name)
    if not updated:
        logger.warning("user.updated for unknown clerk_id=%s — creating", clerk_id)
        User.objects.create(clerk_id=clerk_id, email=email, name=name)


def _handle_user_deleted(data: dict):
    clerk_id = data.get("id", "")
    deleted_count, _ = User.objects.filter(clerk_id=clerk_id).delete()
    logger.info("Deleted %d user(s) for clerk_id=%s", deleted_count, clerk_id)
