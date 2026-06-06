from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from livecomment.cli import (
    MAX_ANNOUNCE_COUNT,
    MIN_ANNOUNCE_INTERVAL_SECONDS,
    build_parser,
    load_announce_messages,
    validate_announce_schedule,
)
from livecomment.errors import LiveCommentError


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


if __name__ == "__main__":
    unittest.main()
