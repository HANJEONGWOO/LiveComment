class LiveCommentError(Exception):
    """Base exception for user-facing LiveComment failures."""


class OAuthError(LiveCommentError):
    """Raised when OAuth authorization or token refresh fails."""


class YouTubeApiError(LiveCommentError):
    """Raised when the YouTube API returns an error."""

    def __init__(self, status: int, reason: str, message: str) -> None:
        self.status = status
        self.reason = reason
        self.message = message
        super().__init__(f"YouTube API error {status} {reason}: {message}")
