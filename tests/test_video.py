import unittest

from livecomment.errors import LiveCommentError
from livecomment.video import extract_video_id


class ExtractVideoIdTests(unittest.TestCase):
    def test_plain_video_id(self):
        self.assertEqual(extract_video_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_watch_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1"),
            "dQw4w9WgXcQ",
        )

    def test_short_url(self):
        self.assertEqual(
            extract_video_id("https://youtu.be/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_live_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/live/dQw4w9WgXcQ?feature=share"),
            "dQw4w9WgXcQ",
        )

    def test_embed_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_invalid_value(self):
        with self.assertRaises(LiveCommentError):
            extract_video_id("not a video")


if __name__ == "__main__":
    unittest.main()
