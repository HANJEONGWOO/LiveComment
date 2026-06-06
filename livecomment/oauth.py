from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from .errors import LiveCommentError, OAuthError
from .http import post_form

DEFAULT_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
DEFAULT_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


@dataclass(frozen=True)
class OAuthClient:
    client_id: str
    client_secret: str | None
    auth_uri: str
    token_uri: str


class TokenStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save(self, token: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(token, file, indent=2, sort_keys=True)
            file.write("\n")
        os.chmod(tmp_path, 0o600)
        tmp_path.replace(self.path)


def default_token_path() -> Path:
    return Path(os.environ.get("LIVECOMMENT_TOKEN", ".livecomment/token.json"))


def default_client_secrets_path() -> Path:
    return Path(os.environ.get("LIVECOMMENT_CLIENT_SECRETS", "client_secret.json"))


def load_oauth_client(path: Path) -> OAuthClient:
    if not path.exists():
        raise LiveCommentError(f"OAuth client secrets file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    config = payload.get("installed") or payload.get("web")
    if not isinstance(config, dict):
        raise LiveCommentError("Client secrets JSON must contain an 'installed' or 'web' object.")

    client_id = config.get("client_id")
    if not client_id:
        raise LiveCommentError("Client secrets JSON is missing client_id.")

    return OAuthClient(
        client_id=client_id,
        client_secret=config.get("client_secret"),
        auth_uri=config.get("auth_uri") or DEFAULT_AUTH_URI,
        token_uri=config.get("token_uri") or DEFAULT_TOKEN_URI,
    )


def authorize(
    client: OAuthClient,
    token_store: TokenStore,
    *,
    scope: str = DEFAULT_SCOPE,
    force: bool = False,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    if not force:
        existing = token_store.load()
        if existing and existing.get("refresh_token"):
            return existing

    state = secrets.token_urlsafe(24)
    verifier = _new_code_verifier()
    challenge = _code_challenge(verifier)

    server = _CallbackServer(("127.0.0.1", 0), _OAuthCallbackHandler, state)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/callback"

    params = {
        "client_id": client.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{client.auth_uri}?{urlencode(params)}"

    print("Open this URL in your browser to authorize LiveComment:")
    print(auth_url)
    try:
        webbrowser.open(auth_url)
    except webbrowser.Error:
        pass

    server.timeout = timeout_seconds
    server.handle_request()
    server.server_close()

    if server.error:
        raise OAuthError(server.error)
    if not server.code:
        raise OAuthError("Timed out waiting for OAuth callback.")

    form = {
        "client_id": client.client_id,
        "code": server.code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    if client.client_secret:
        form["client_secret"] = client.client_secret

    token = post_form(client.token_uri, form)
    token = _with_expiry(token)
    token["scope"] = scope
    token_store.save(token)
    return token


def get_access_token(
    client: OAuthClient,
    token_store: TokenStore,
    *,
    scope: str = DEFAULT_SCOPE,
) -> str:
    token = token_store.load()
    if not token:
        token = authorize(client, token_store, scope=scope)

    if _is_valid(token):
        return str(token["access_token"])

    return refresh_access_token(client, token_store, scope=scope)


def refresh_access_token(
    client: OAuthClient,
    token_store: TokenStore,
    *,
    scope: str = DEFAULT_SCOPE,
) -> str:
    token = token_store.load()
    if not token:
        token = authorize(client, token_store, scope=scope)
        return str(token["access_token"])

    refresh_token = token.get("refresh_token")
    if not refresh_token:
        token = authorize(client, token_store, scope=scope, force=True)
        return str(token["access_token"])

    form = {
        "client_id": client.client_id,
        "grant_type": "refresh_token",
        "refresh_token": str(refresh_token),
    }
    if client.client_secret:
        form["client_secret"] = client.client_secret

    refreshed = post_form(client.token_uri, form)
    refreshed = _with_expiry(refreshed)
    refreshed["refresh_token"] = refresh_token
    refreshed["scope"] = token.get("scope", scope)
    token_store.save(refreshed)
    return str(refreshed["access_token"])


def _new_code_verifier() -> str:
    return secrets.token_urlsafe(96)[:128]


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _with_expiry(token: dict[str, Any]) -> dict[str, Any]:
    expires_in = int(token.get("expires_in", 3600))
    token["expires_at"] = int(time.time()) + expires_in
    return token


def _is_valid(token: dict[str, Any]) -> bool:
    access_token = token.get("access_token")
    expires_at = int(token.get("expires_at", 0))
    return bool(access_token) and expires_at - 60 > int(time.time())


class _CallbackServer(HTTPServer):
    def __init__(self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler], state: str):
        super().__init__(server_address, handler)
        self.expected_state = state
        self.code: str | None = None
        self.error: str | None = None


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    server: _CallbackServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        state = params.get("state", [""])[0]
        if state != self.server.expected_state:
            self.server.error = "OAuth state mismatch."
            self._reply(400, "Authorization failed. You can close this tab.")
            return

        error = params.get("error", [None])[0]
        if error:
            self.server.error = f"OAuth authorization denied: {error}"
            self._reply(400, "Authorization denied. You can close this tab.")
            return

        code = params.get("code", [None])[0]
        if not code:
            self.server.error = "OAuth callback did not include a code."
            self._reply(400, "Authorization failed. You can close this tab.")
            return

        self.server.code = code
        self._reply(200, "LiveComment is authorized. You can close this tab.")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _reply(self, status: int, message: str) -> None:
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
