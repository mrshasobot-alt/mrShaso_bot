import unittest
from types import SimpleNamespace

from app.bot import (
    MENU_MODE_KEY,
    SUPPORTED_CONVERSION_OPERATIONS,
    create_application,
    build_download_options,
    build_main_menu,
    build_converter_menu,
    build_language_menu,
    build_media_menu,
    extract_media_url,
    identity_response,
    is_identity_question,
    media_url_matches_mode,
    social_media_kind,
    should_answer_identity,
)
from app.config import Settings
from app.gemini_client import GeminiClient


class GeminiClientTests(unittest.TestCase):
    def test_download_options_are_fast_and_single_item(self):
        options = build_download_options("work")
        self.assertTrue(options["noplaylist"])
        self.assertEqual(options["concurrent_fragment_downloads"], 4)
        self.assertEqual(options["socket_timeout"], 20)
        self.assertEqual(options["retries"], 3)

    def test_language_buttons_are_translated_for_selected_language(self):
        expected = {
            "english": {"Kurdish", "Persian", "Arabic", "English", "Turkish"},
            "arabic": {"الكردية", "الفارسية", "العربية", "الإنجليزية", "التركية"},
            "turkish": {"Kürtçe", "Farsça", "Arapça", "İngilizce", "Türkçe"},
        }
        for language, labels in expected.items():
            main_labels = {
                button.text
                for row in build_main_menu(language).inline_keyboard
                for button in row
            }
            language_labels = {
                button.text
                for row in build_language_menu(language).inline_keyboard
                for button in row
            }
            self.assertTrue(labels.issubset(main_labels))
            self.assertTrue(labels.issubset(language_labels))

    def test_converter_and_media_menus_are_localized(self):
        expected_labels = {
            "kurdish": "MP3 → Voice",
            "persian": "MP3 → صدا",
            "arabic": "فيديو ← MP3",
            "english": "MP3 → Voice",
            "turkish": "MP3 → Ses",
        }
        for language, expected in expected_labels.items():
            converter_text = " ".join(
                button.text
                for row in build_converter_menu(language).inline_keyboard
                for button in row
            )
            media_text = " ".join(
                button.text
                for row in build_media_menu(language).inline_keyboard
                for button in row
            )
            self.assertIn(expected, converter_text)
            self.assertTrue(media_text)

    def test_back_button_resets_menu_mode_to_main_without_clearing_state(self):
        app = create_application(Settings(bot_token="test-token", gemini_api_key="test-key", gemini_model="gemini-2.0-flash"))
        menu_handler = next(
            handler for group in app.handlers.values() for handler in group
            if getattr(getattr(handler, "callback", None), "__name__", "") == "handle_menu_callback"
        )

        context = SimpleNamespace(user_data={MENU_MODE_KEY: "media:upload"})
        update = SimpleNamespace(
            callback_query=SimpleNamespace(
                data="menu:main",
                answer=lambda *args, **kwargs: None,
                edit_message_text=lambda *args, **kwargs: None,
            ),
            effective_chat=SimpleNamespace(type="private"),
        )

        asyncio.run(menu_handler.callback(update, context))

        self.assertEqual(context.user_data[MENU_MODE_KEY], "main")
        self.assertIn(MENU_MODE_KEY, context.user_data)

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

    def test_social_media_gallery_accepts_only_media_types(self):
        from pathlib import Path

        self.assertEqual(social_media_kind(Path("track.mp3")), "audio")
        self.assertEqual(social_media_kind(Path("clip.ogg")), "voice")
        self.assertEqual(social_media_kind(Path("video.mp4")), "video")
        self.assertIsNone(social_media_kind(Path("file.pdf")))

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
