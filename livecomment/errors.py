class LiveCommentError(Exception):
    """Base exception for user-facing LiveComment failures."""


class OAuthError(LiveCommentError):
    """Raised when OAuth authorization or token refresh fails."""

    def __init__(
        self,
        message: str,
        *,
        error: str | None = None,
        description: str | None = None,
    ) -> None:
        self.error = error
        self.description = description
        super().__init__(message)


class YouTubeApiError(LiveCommentError):
    """Raised when the YouTube API returns an error."""

    def __init__(self, status: int, reason: str, message: str) -> None:
        self.status = status
        self.reason = reason
        self.message = message
        super().__init__(f"YouTube API error {status} {reason}: {message}")
