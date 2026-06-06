import unittest

from livecomment.cli import (
    MAX_ANNOUNCE_COUNT,
    MIN_ANNOUNCE_INTERVAL_SECONDS,
    build_parser,
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
                "--message",
                "공지 메시지",
                "--dry-run",
            ]
        )

        self.assertEqual(args.interval, MIN_ANNOUNCE_INTERVAL_SECONDS)
        self.assertEqual(args.count, MAX_ANNOUNCE_COUNT)

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
