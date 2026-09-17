from __future__ import annotations

from google_auth_oauthlib.flow import Flow
from starlette.requests import Request

from app.config import settings

SCOPES = [
    "https://mail.google.com/",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def redirect_uri() -> str:
    return settings.public_base_url.rstrip("/") + "/api/v1/mail/accounts/gmail/callback"


def redirect_uri_for_request(request: Request) -> str:
    host = (request.url.hostname or "").lower()
    if host in _LOOPBACK_HOSTS:
        return str(request.base_url).rstrip("/") + "/api/v1/mail/accounts/gmail/callback"
    return redirect_uri()


def _client_config(callback: str) -> dict:
    return {
        "web": {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [callback],
        }
    }


def build_flow(state: str | None = None, callback: str | None = None) -> Flow:
    uri = callback or redirect_uri()
    flow = Flow.from_client_config(_client_config(uri), scopes=SCOPES, state=state)
    flow.redirect_uri = uri
    return flow


def authorization_url(state: str, callback: str) -> str:
    flow = build_flow(state, callback)
    url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    return url
