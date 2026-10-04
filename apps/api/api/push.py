"""Device-scoped Web Push API and bounded, destination-restricted transport."""
from __future__ import annotations

import base64
import ipaddress
import json
import logging
import socket
from urllib.parse import urlsplit
from uuid import UUID

import requests
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, EllipticCurvePublicKey
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from pywebpush import WebPushException, webpush

from api.auth import CurrentUser, get_current_user
from api.config import get_settings
from api.supabase_clients import admin_client

router = APIRouter(prefix="/notifications/push", tags=["push"])
logger = logging.getLogger("uvicorn.error")


def configured() -> bool:
    s = get_settings()
    return bool(s.web_push_public_key and s.web_push_private_key and s.web_push_subject and s.supabase_service_role_key)


def validate_endpoint(endpoint: str) -> str:
    try:
        url = urlsplit(endpoint)
        host = url.hostname or ""
        allowed = host in {"fcm.googleapis.com", "updates.push.services.mozilla.com"} or host.endswith(".push.apple.com")
        if (not allowed or url.scheme != "https" or url.port not in (None, 443)
                or url.username or url.password or url.fragment or not url.path or len(endpoint) > 2048):
            raise ValueError
    except ValueError:
        raise ValueError("Unsupported push service endpoint.") from None
    return endpoint


def decode_key(value: str, length: int) -> bytes:
    try:
        data = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        if len(data) != length:
            raise ValueError
        return data
    except (ValueError, TypeError):
        raise ValueError("Invalid push subscription key.") from None


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(max_length=100)
    auth: str = Field(max_length=30)

    @field_validator("p256dh")
    @classmethod
    def valid_public_key(cls, value: str) -> str:
        try:
            EllipticCurvePublicKey.from_encoded_point(SECP256R1(), decode_key(value, 65))
        except ValueError:
            raise ValueError("Invalid push subscription key.") from None
        return value

    @field_validator("auth")
    @classmethod
    def valid_auth(cls, value: str) -> str:
        decode_key(value, 16)
        return value


class SubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=2048)
    keys: SubscriptionKeys
    binding_id: UUID

    @field_validator("endpoint")
    @classmethod
    def valid_endpoint(cls, value: str) -> str:
        return validate_endpoint(value)


def browser_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.is_api_key:
        raise HTTPException(403, "Use a signed-in browser to manage notifications.")
    return user


def require_config() -> None:
    if not configured():
        raise HTTPException(503, "Push notifications are not configured on this server.")


def owned_subscription(subscription_id: UUID | str, user_id: str) -> dict:
    rows = admin_client().table("push_subscriptions").select("*").eq("id", str(subscription_id)).eq("user_id", user_id).execute().data
    if not rows:
        raise HTTPException(404, "Notification registration not found. Enable notifications again.")
    return rows[0]


class RestrictedSession(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.trust_env = False

    def request(self, method, url, **kwargs):
        validate_endpoint(url)
        # Only browser-operated domains are allowed; additionally fail closed on
        # private/local DNS results. Never follow a provider redirect.
        host = urlsplit(url).hostname
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise ValueError("Push service resolved to a non-public address.")
        kwargs.update(allow_redirects=False, timeout=(3, 5))
        return super().request(method, url, **kwargs)


def send_push(subscription: dict, payload: dict, ttl: int) -> tuple[str, int]:
    """Return sanitized category and retry delay; never expose provider bodies."""
    settings = get_settings()
    try:
        with RestrictedSession() as session:
            response = webpush(
                subscription_info={"endpoint": subscription["endpoint"], "keys": {
                    "p256dh": subscription["p256dh"], "auth": subscription["auth"],
                }},
                data=json.dumps({**payload, "binding_id": subscription["binding_id"]}),
                vapid_private_key=settings.web_push_private_key,
                vapid_claims={"sub": settings.web_push_subject},
                ttl=max(0, min(ttl, 600)), timeout=5, requests_session=session,
            )
        code = response.status_code
    except WebPushException as exc:
        response = exc.response
        code = response.status_code if response is not None else 0
    except (requests.RequestException, OSError):
        return "retry", 60
    except Exception as exc:
        logger.warning("push failure category=configuration type=%s", type(exc).__name__)
        return "failed", 0
    if 200 <= code < 300:
        return "accepted", 0
    if code in (404, 410):
        return "expired", 0
    if code == 0 or code == 429 or code >= 500:
        retry = 60
        if response is not None:
            try:
                retry = max(60, min(600, int(response.headers.get("Retry-After", "60"))))
            except ValueError:
                pass
        return "retry", retry
    return "failed", 0


@router.get("/config")
def push_config(user: CurrentUser = Depends(browser_user)):
    enabled = configured()
    return {"enabled": enabled, "public_key": get_settings().web_push_public_key if enabled else None}


@router.post("/subscriptions")
def register(payload: SubscriptionIn, user: CurrentUser = Depends(browser_user)):
    require_config()
    rows = admin_client().rpc("register_push", {
        "p_user": user.id, "p_endpoint": payload.endpoint, "p_key": payload.keys.p256dh,
        "p_auth": payload.keys.auth, "p_binding": str(payload.binding_id),
    }).execute().data
    if not rows:
        raise HTTPException(409, "This browser subscription belongs to a different enrollment. Disable it before enabling again.")
    return {"id": rows[0]["id"], "binding_id": rows[0]["binding_id"]}


@router.get("/subscriptions/{subscription_id}")
def subscription_status(subscription_id: UUID, user: CurrentUser = Depends(browser_user)):
    row = owned_subscription(subscription_id, user.id)
    return {"id": row["id"], "binding_id": row["binding_id"]}


@router.delete("/subscriptions/{subscription_id}", status_code=204)
def revoke(subscription_id: UUID, user: CurrentUser = Depends(browser_user)):
    admin_client().table("push_subscriptions").delete().eq("id", str(subscription_id)).eq("user_id", user.id).execute()
    return Response(status_code=204)


@router.post("/subscriptions/{subscription_id}/test")
def test_notification(subscription_id: UUID, user: CurrentUser = Depends(browser_user)):
    require_config()
    row = owned_subscription(subscription_id, user.id)
    if not admin_client().rpc("reserve_push_test", {"p_user": user.id, "p_subscription": str(subscription_id)}).execute().data:
        raise HTTPException(429, "Wait one minute before sending another test.")
    outcome, _ = send_push(row, {"title": "Sway notifications are ready", "body": "This is a test notification.", "tag": "sway-test"}, 60)
    if outcome == "expired":
        revoke(subscription_id, user)
        raise HTTPException(410, "This subscription expired. Disable and enable notifications again.")
    if outcome != "accepted":
        raise HTTPException(503, "The push service could not accept the test. Try again later.")
    return {"message": "Test accepted by the push service. Check your device; delivery depends on its notification settings."}
