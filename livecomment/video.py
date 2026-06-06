from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from .errors import LiveCommentError

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(value: str) -> str:
    candidate = value.strip()
    if VIDEO_ID_RE.fullmatch(candidate):
        return candidate

    parsed = urlparse(candidate)
    if not parsed.netloc:
        raise LiveCommentError(f"Invalid YouTube video ID or URL: {value}")

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path_parts = [part for part in parsed.path.split("/") if part]

    if host == "youtu.be" and path_parts:
        return _validate_video_id(path_parts[0], value)

    if host.endswith("youtube.com"):
        query_video_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_video_id:
            return _validate_video_id(query_video_id, value)

        if len(path_parts) >= 2 and path_parts[0] in {"live", "embed", "shorts"}:
            return _validate_video_id(path_parts[1], value)

    raise LiveCommentError(f"Could not find a YouTube video ID in: {value}")


def _validate_video_id(video_id: str, original: str) -> str:
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise LiveCommentError(f"Invalid YouTube video ID in URL: {original}")
    return video_id
