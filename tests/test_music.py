import unittest
from unittest.mock import patch

from app.music import TrackPreview, find_track_preview


class MusicPreviewTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.music._search_itunes")
    async def test_search_runs_provider_and_returns_preview(self, search):
        expected = TrackPreview("Song", "Artist", "https://example.test/preview.m4a")
        search.return_value = expected

        result = await find_track_preview("Artist Song")

        self.assertEqual(result, expected)
        search.assert_called_once_with("Artist Song")

    async def test_empty_song_query_returns_none(self):
        self.assertIsNone(await find_track_preview("   "))


if __name__ == "__main__":
    unittest.main()