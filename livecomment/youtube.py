from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import LiveCommentError
from .http import api_json
from .video import extract_video_id

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


@dataclass(frozen=True)
class LiveChat:
    video_id: str
    live_chat_id: str
    title: str | None = None


class YouTubeClient:
    def __init__(self, access_token: str) -> None:
        self.access_token = access_token

    def resolve_live_chat(self, video_ref: str) -> LiveChat:
        video_id = extract_video_id(video_ref)
        payload = api_json(
            "GET",
            f"{YOUTUBE_API_BASE}/videos",
            self.access_token,
            params={"part": "snippet,liveStreamingDetails", "id": video_id},
        )

        items = payload.get("items", [])
        if not items:
            raise LiveCommentError(f"YouTube video not found: {video_id}")

        item = items[0]
        details = item.get("liveStreamingDetails") or {}
        live_chat_id = details.get("activeLiveChatId")
        if not live_chat_id:
            raise LiveCommentError(
                "This video does not have an active live chat. "
                "It may not be live, chat may be disabled, or the broadcast may have ended."
            )

        snippet = item.get("snippet") or {}
        return LiveChat(
            video_id=video_id,
            live_chat_id=str(live_chat_id),
            title=snippet.get("title"),
        )

    def send_text_message(self, live_chat_id: str, message: str) -> dict[str, Any]:
        return api_json(
            "POST",
            f"{YOUTUBE_API_BASE}/liveChat/messages",
            self.access_token,
            params={"part": "snippet"},
            body={
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {"messageText": message},
                }
            },
        )