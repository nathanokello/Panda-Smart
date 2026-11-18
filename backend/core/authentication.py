"""Token sign-in with an expiry, and a login limit per phone number.

DRF's tokens never expire on their own. A token copied from a shared phone or
a lost device would work for ever, so tokens older than TOKEN_TTL_HOURS are
deleted and the user signs in again.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.throttling import SimpleRateThrottle

from core.phone import normalize_phone


def token_is_expired(token: Token) -> bool:
    ttl = int(getattr(settings, "TOKEN_TTL_HOURS", 0) or 0)
    return bool(ttl) and token.created < timezone.now() - timedelta(hours=ttl)


def issue_token(user) -> Token:
    """Return the user's token, replacing it first if it has expired."""
    token = Token.objects.filter(user=user).first()
    if token and token_is_expired(token):
        token.delete()
        token = None
    return token or Token.objects.create(user=user)


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if token_is_expired(token):
            token.delete()
            raise AuthenticationFailed("Your session has expired. Please sign in again.")
        return user, token


class LoginPhoneThrottle(SimpleRateThrottle):
    """Limit sign-in attempts per phone number, not only per IP address.

    Uses Django's cache. The default in-memory cache is per process; use a
    shared cache (database or Redis) when running several server processes.
    """

    scope = "login_phone"

    def get_cache_key(self, request, view):
        data = getattr(request, "data", None)
        phone = normalize_phone(data.get("phone", "")) if hasattr(data, "get") else ""
        if not phone:
            return None
        return self.cache_format % {"scope": self.scope, "ident": phone}
