import unittest
from types import SimpleNamespace

from app.bot import (
    SUPPORTED_CONVERSION_OPERATIONS,
    build_main_menu,
    extract_media_url,
    identity_response,
    is_identity_question,
    media_url_matches_mode,
    should_answer_identity,
)
from app.gemini_client import GeminiClient


class GeminiClientTests(unittest.TestCase):
    def test_extract_media_url_ignores_trailing_punctuation(self):
        self.assertEqual(
            extract_media_url("download https://example.com/video?id=1."),
            "https://example.com/video?id=1",
        )
        self.assertIsNone(extract_media_url("this is not a link"))

    def test_social_media_urls_only_match_their_own_section(self):
        self.assertTrue(media_url_matches_mode("https://www.tiktok.com/@user/video/1", "media:tiktok"))
        self.assertFalse(media_url_matches_mode("https://www.tiktok.com/@user/video/1", "media:facebook"))
        self.assertTrue(media_url_matches_mode("https://www.instagram.com/reel/1", "media:instagram"))
        self.assertFalse(media_url_matches_mode("https://www.instagram.com/reel/1", "media:snapchat"))
        self.assertTrue(media_url_matches_mode("https://example.com/media", "media:upload"))

    def test_main_menu_exposes_all_requested_actions(self):
        callbacks = {
            button.callback_data
            for row in build_main_menu("kurdish").inline_keyboard
            for button in row
            if button.callback_data
        }
        self.assertTrue({
            "language:kurdish", "language:persian", "language:arabic",
            "language:english", "language:turkish", "menu:chat",
            "menu:converter:mp3_voice", "menu:converter:voice_mp3",
            "menu:converter:video_mp3", "menu:converter:video_voice",
            "menu:media:facebook", "menu:media:tiktok",
            "menu:media:instagram", "menu:media:snapchat", "menu:media:upload",
            "menu:main",
        }.issubset(callbacks))
        self.assertNotIn("menu:files:archive", callbacks)
        self.assertIn("menu:media:upload", callbacks)

    def test_converter_operations_are_explicitly_supported(self):
        self.assertEqual(
            SUPPORTED_CONVERSION_OPERATIONS,
            {"mp3_voice", "voice_mp3", "video_mp3", "video_voice"},
        )

    def test_identity_keywords_cover_requested_languages(self):
        for question in ["اصل بده", "ناسنامە", "عرفني", "who are you", "adın ne"]:
            self.assertTrue(is_identity_question(question), msg=question)

    def test_identity_response_is_localized(self):
        self.assertIn("سن من", identity_response("اصل بده"))
        self.assertIn("تەمەنم", identity_response("ناسنامە"))
        self.assertIn("عمري", identity_response("عرفني"))
        self.assertIn("I am 36", identity_response("who are you"))
        self.assertIn("yaşındayım", identity_response("adın ne"))

    def test_identity_question_is_allowed_in_private_chat(self):
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(type="private"),
            effective_message=SimpleNamespace(text="who are you", reply_to_message=None),
        )
        self.assertTrue(should_answer_identity(update, 42))

    def test_identity_question_in_group_requires_reply_to_bot(self):
        bot_reply = SimpleNamespace(from_user=SimpleNamespace(id=42))
        user_reply = SimpleNamespace(from_user=SimpleNamespace(id=99))
        bot_update = SimpleNamespace(
            effective_chat=SimpleNamespace(type="supergroup"),
            effective_message=SimpleNamespace(text="who are you", reply_to_message=bot_reply),
        )
        user_update = SimpleNamespace(
            effective_chat=SimpleNamespace(type="group"),
            effective_message=SimpleNamespace(text="who are you", reply_to_message=user_reply),
        )
        no_reply_update = SimpleNamespace(
            effective_chat=SimpleNamespace(type="group"),
            effective_message=SimpleNamespace(text="who are you", reply_to_message=None),
        )
        self.assertTrue(should_answer_identity(bot_update, 42))
        self.assertFalse(should_answer_identity(user_update, 42))
        self.assertFalse(should_answer_identity(no_reply_update, 42))

    def test_extract_text_from_text_property(self):
        response = SimpleNamespace(text="Answer text")
        self.assertEqual(GeminiClient._extract_text(response), "Answer text")

    def test_detect_language_supports_arabic_and_kurdish(self):
        detected = GeminiClient.detect_language("سڵاو چۆنیت؟")
        self.assertIn(detected.lower(), ["arabic", "kurdish", "persian", "multilingual"])

    def test_build_system_prompt_includes_multilingual_behavior(self):
        prompt = GeminiClient.build_system_prompt("kurdish")
        self.assertIn("kurdish", prompt.lower())
        self.assertIn("multilingual", prompt.lower())


if __name__ == "__main__":
    unittest.main()
