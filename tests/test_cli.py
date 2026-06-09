import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from livecomment.cli import (
    MAX_ANNOUNCE_COUNT,
    MIN_ANNOUNCE_INTERVAL_SECONDS,
    build_parser,
    is_auth_error,
    is_stream_auth_error,
    load_announce_messages,
    send_text_message_with_auth_retry,
    validate_announce_schedule,
)
from livecomment.errors import LiveCommentError, YouTubeApiError
from livecomment.streaming import build_prefixed_message, extract_up_trigger


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

    def test_parser_defaults_watch_up_to_message_file(self):
        args = build_parser().parse_args(
            [
                "watch-up",
                "--live-chat-id",
                "CHAT_ID",
                "--dry-run",
            ]
        )

        self.assertEqual(args.message_file, Path("messages.txt"))
        self.assertEqual(args.interval, MIN_ANNOUNCE_INTERVAL_SECONDS)


class UpTriggerTests(unittest.TestCase):
    def test_extracts_up_trigger(self):
        self.assertEqual(extract_up_trigger("모카업 ❤❤❤"), "모카업")

    def test_extracts_last_up_trigger(self):
        self.assertEqual(extract_up_trigger("초코업 모카업!!"), "모카업")

    def test_returns_none_without_up_trigger(self):
        self.assertIsNone(extract_up_trigger("그냥 채팅"))

    def test_builds_prefixed_message(self):
        self.assertEqual(
            build_prefixed_message("모카업", "사랑해 ❤❤❤", max_length=200),
            "모카업 사랑해 ❤❤❤",
        )

    def test_rejects_too_long_prefixed_message(self):
        with self.assertRaises(LiveCommentError):
            build_prefixed_message("모카업", "사랑해", max_length=5)


class AuthRetryTests(unittest.TestCase):
    def test_detects_auth_error(self):
        self.assertTrue(is_auth_error(YouTubeApiError(401, "authError", "bad token")))

    def test_detects_stream_auth_error(self):
        self.assertTrue(is_stream_auth_error(LiveCommentError("streamList failed: UNAUTHENTICATED")))

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


if __name__ == "__main__":
    unittest.main()
