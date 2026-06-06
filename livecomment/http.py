from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .errors import OAuthError, YouTubeApiError


def post_form(url: str, data: dict[str, str], timeout: int = 30) -> dict[str, Any]:
    encoded = urlencode(data).encode("utf-8")
    request = Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = _read_error_body(exc)
        error = body.get("error", "unknown_error")
        description = body.get("error_description", body.get("message", "No detail"))
        raise OAuthError(f"OAuth request failed: {error}: {description}") from exc
    except URLError as exc:
        raise OAuthError(f"OAuth request failed: {exc.reason}") from exc


def api_json(
    method: str,
    url: str,
    access_token: str,
    *,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(params)}"

    data = None
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = _read_error_body(exc)
        error = payload.get("error", {})
        if isinstance(error, dict):
            reason = _first_reason(error)
            message = str(error.get("message", "No detail"))
        else:
            reason = str(error)
            message = str(payload)
        raise YouTubeApiError(exc.code, reason, message) from exc
    except URLError as exc:
        raise YouTubeApiError(0, "networkError", str(exc.reason)) from exc


def _read_error_body(exc: HTTPError) -> dict[str, Any]:
    raw = exc.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"message": raw}


def _first_reason(error: dict[str, Any]) -> str:
    errors = error.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict) and first.get("reason"):
            return str(first["reason"])
    return str(error.get("status") or error.get("code") or "apiError")
