import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from livecomment.cli import (
    DEFAULT_ANNOUNCE_PREFIX,
    MAX_ANNOUNCE_COUNT,
    MIN_ANNOUNCE_INTERVAL_SECONDS,
    authed_youtube,
    build_parser,
    cmd_announce,
    is_auth_error,
    is_youtube_quota_error,
    load_announce_messages,
    prefix_announce_messages,
    send_text_message_with_auth_retry,
    validate_announce_schedule,
)
from livecomment.errors import LiveCommentError, YouTubeApiError


class FakeYouTubeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def send_text_message(self, live_chat_id, message):
        self.calls.append((live_chat_id, message))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class AnnounceScheduleTests(unittest.TestCase):
    def test_parser_defaults_to_announce_limits(self):
        args = build_parser().parse_args(
            [
                "announce",
                "--live-chat-id",
                "CHAT_ID",
                "--message-file",
                "messages.txt",
                "--dry-run",
            ]
        )

        self.assertEqual(args.interval, MIN_ANNOUNCE_INTERVAL_SECONDS)
        self.assertEqual(args.count, MAX_ANNOUNCE_COUNT)
        self.assertEqual(args.message_file, Path("messages.txt"))
        self.assertEqual(args.prefix, DEFAULT_ANNOUNCE_PREFIX)

    def test_loads_single_inline_announcement(self):
        self.assertEqual(
            load_announce_messages(message=" 공지 메시지 ", message_file=None, max_length=200),
            ["공지 메시지"],
        )

    def test_loads_announcement_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "messages.txt"
            path.write_text(
                "# comment\n\n첫 번째 공지\n두 번째 공지\n",
                encoding="utf-8",
            )

            self.assertEqual(
                load_announce_messages(message=None, message_file=path, max_length=200),
                ["첫 번째 공지", "두 번째 공지"],
            )

    def test_rejects_empty_announcement_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "messages.txt"
            path.write_text("# comment\n\n", encoding="utf-8")

            with self.assertRaises(LiveCommentError):
                load_announce_messages(message=None, message_file=path, max_length=200)

    def test_rejects_too_long_file_message(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "messages.txt"
            path.write_text("너무 긴 메시지\n", encoding="utf-8")

            with self.assertRaises(LiveCommentError):
                load_announce_messages(message=None, message_file=path, max_length=3)

    def test_valid_schedule(self):
        self.assertEqual(validate_announce_schedule(120.0, 3, 10.0), (120.0, 3, 10.0))

    def test_rejects_short_interval(self):
        with self.assertRaises(LiveCommentError):
            validate_announce_schedule(MIN_ANNOUNCE_INTERVAL_SECONDS - 1, 3, 0.0)

    def test_rejects_zero_count(self):
        with self.assertRaises(LiveCommentError):
            validate_announce_schedule(120.0, 0, 0.0)

    def test_rejects_too_many_announcements(self):
        with self.assertRaises(LiveCommentError):
            validate_announce_schedule(120.0, MAX_ANNOUNCE_COUNT + 1, 0.0)

    def test_rejects_negative_start_delay(self):
        with self.assertRaises(LiveCommentError):
            validate_announce_schedule(120.0, 3, -1.0)

    def test_prefixes_every_announcement(self):
        self.assertEqual(
            prefix_announce_messages(
                ["첫 번째 문장", "두 번째 문장"],
                prefix="후원자업",
                max_length=200,
            ),
            ["후원자업 첫 번째 문장", "후원자업 두 번째 문장"],
        )

    def test_empty_prefix_keeps_messages_unchanged(self):
        messages = ["첫 번째 문장", "두 번째 문장"]

        self.assertIs(
            prefix_announce_messages(messages, prefix="  ", max_length=200),
            messages,
        )

    def test_rejects_too_long_prefixed_announcement(self):
        with self.assertRaises(LiveCommentError):
            prefix_announce_messages(["사랑해"], prefix="후원자업", max_length=5)

    def test_announce_sends_every_message_with_default_prefix(self):
        youtube = FakeYouTubeClient([{"id": "first"}, {"id": "second"}])
        args = build_parser().parse_args(
            [
                "announce",
                "--live-chat-id",
                "CHAT_ID",
                "--message-file",
                "messages.txt",
                "--count",
                "2",
            ]
        )

        with (
            patch("livecomment.cli.load_announce_messages", return_value=["첫 문장", "둘째 문장"]),
            patch("livecomment.cli.authed_youtube", return_value=youtube),
            patch("livecomment.cli.resolve_target_chat_id", return_value="CHAT_ID"),
            patch("livecomment.cli.time.sleep"),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            result = cmd_announce(args)

        self.assertEqual(result, 0)
        self.assertEqual(
            youtube.calls,
            [("CHAT_ID", "후원자업 첫 문장"), ("CHAT_ID", "후원자업 둘째 문장")],
        )


class AuthRetryTests(unittest.TestCase):
    def test_builds_youtube_client_from_access_token(self):
        args = build_parser().parse_args(
            [
                "send",
                "--live-chat-id",
                "CHAT_ID",
                "--message",
                "공지 메시지",
            ]
        )

        with (
            patch("livecomment.cli.load_oauth_client", return_value=object()),
            patch("livecomment.cli.get_access_token", return_value="access-token") as get_token,
        ):
            youtube = authed_youtube(args)

        self.assertEqual(youtube.access_token, "access-token")
        get_token.assert_called_once()

    def test_detects_auth_error(self):
        self.assertTrue(is_auth_error(YouTubeApiError(401, "authError", "bad token")))

    def test_detects_youtube_quota_error(self):
        self.assertTrue(
            is_youtube_quota_error(YouTubeApiError(403, "quotaExceeded", "quota exceeded"))
        )

    def test_refreshes_and_retries_once_on_auth_error(self):
        stale = FakeYouTubeClient([YouTubeApiError(401, "authError", "bad token")])
        refreshed = FakeYouTubeClient([{"id": "message-id"}])

        with (
            patch("livecomment.cli.refresh_youtube", return_value=refreshed) as refresh,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            response, youtube = send_text_message_with_auth_retry(
                object(),
                stale,
                "CHAT_ID",
                "공지 메시지",
            )

        self.assertEqual(response, {"id": "message-id"})
        self.assertIs(youtube, refreshed)
        self.assertEqual(stale.calls, [("CHAT_ID", "공지 메시지")])
        self.assertEqual(refreshed.calls, [("CHAT_ID", "공지 메시지")])
        refresh.assert_called_once()

    def test_does_not_retry_non_auth_errors(self):
        youtube = FakeYouTubeClient([YouTubeApiError(403, "forbidden", "nope")])

        with patch("livecomment.cli.refresh_youtube") as refresh:
            with self.assertRaises(YouTubeApiError):
                send_text_message_with_auth_retry(object(), youtube, "CHAT_ID", "공지 메시지")

        refresh.assert_not_called()

    def test_retries_youtube_quota_error_after_wait(self):
        youtube = FakeYouTubeClient(
            [
                YouTubeApiError(403, "quotaExceeded", "quota exceeded"),
                {"id": "message-id"},
            ]
        )
        args = build_parser().parse_args(
            [
                "send",
                "--live-chat-id",
                "CHAT_ID",
                "--message",
                "공지 메시지",
                "--quota-retry-delay",
                "1",
                "--quota-max-retries",
                "2",
            ]
        )

        with (
            patch("livecomment.cli.time.sleep") as sleep,
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            response, returned_youtube = send_text_message_with_auth_retry(
                args,
                youtube,
                "CHAT_ID",
                "공지 메시지",
            )

        self.assertEqual(response, {"id": "message-id"})
        self.assertIs(returned_youtube, youtube)
        self.assertEqual(youtube.calls, [("CHAT_ID", "공지 메시지"), ("CHAT_ID", "공지 메시지")])
        sleep.assert_called_once_with(1.0)

    def test_stops_after_youtube_quota_retry_limit(self):
        youtube = FakeYouTubeClient(
            [
                YouTubeApiError(403, "quotaExceeded", "quota exceeded"),
                YouTubeApiError(403, "quotaExceeded", "quota exceeded"),
            ]
        )
        args = build_parser().parse_args(
            [
                "send",
                "--live-chat-id",
                "CHAT_ID",
                "--message",
                "공지 메시지",
                "--quota-retry-delay",
                "1",
                "--quota-max-retries",
                "1",
            ]
        )

        with (
            patch("livecomment.cli.time.sleep") as sleep,
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            with self.assertRaises(YouTubeApiError):
                send_text_message_with_auth_retry(args, youtube, "CHAT_ID", "공지 메시지")

        self.assertEqual(youtube.calls, [("CHAT_ID", "공지 메시지"), ("CHAT_ID", "공지 메시지")])
        sleep.assert_called_once_with(1.0)


if __name__ == "__main__":
    unittest.main()
