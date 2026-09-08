import unittest
from types import SimpleNamespace

from app.bot import should_answer_identity
from app.gemini_client import GeminiClient


class GeminiClientTests(unittest.TestCase):
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
