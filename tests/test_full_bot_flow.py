import unittest

from app.bot import build_response_instruction
from app.gemini_client import GeminiClient


class FullBotBehaviorTests(unittest.TestCase):
    def test_language_detection_for_kurdish_text(self):
        self.assertEqual(GeminiClient.detect_language("سڵاو چۆنیت؟"), "kurdish")

    def test_language_detection_for_arabic_text(self):
        self.assertEqual(GeminiClient.detect_language("مرحبا كيف الحال؟"), "arabic")

    def test_language_detection_distinguishes_persian_from_arabic(self):
        self.assertEqual(GeminiClient.detect_language("سلام، حالت چطور است؟"), "persian")

    def test_kurdish_dialect_detection_and_prompt_preserve_dialect(self):
        sorani = "سڵاو، چۆنیت؟ ئەم کارە دەکات"
        badini = "سڵاو، چۆنی؟ ئەڤ کارە دکەم"
        self.assertEqual(GeminiClient.detect_kurdish_dialect(sorani), "sorani")
        self.assertEqual(GeminiClient.detect_kurdish_dialect(badini), "badini")
        prompt = build_response_instruction(sorani, "kurdish")
        self.assertIn("Sorani", prompt)
        self.assertIn("Do not mix languages", prompt)

    def test_system_prompt_requires_grammar_and_intent_awareness(self):
        prompt = GeminiClient.build_system_prompt("arabic")
        self.assertIn("Identify the user's intent", prompt)
        self.assertIn("correct spelling, grammar", prompt)
        self.assertIn("Do not mix languages", prompt)

    def test_build_system_prompt_contains_multilingual_hint(self):
        prompt = GeminiClient.build_system_prompt("kurdish")
        self.assertIn("Kurdish", prompt)
        self.assertIn("multilingual", prompt.lower())

    def test_candidate_model_list_prefers_supported_models(self):
        models = GeminiClient.get_fallback_models("gemini-2.0-flash")
        self.assertIn("gemini-2.5-flash", models)
        self.assertIn("gemini-3.6-flash", models)

    def test_ask_returns_safe_fallback_on_exception(self):
        client = GeminiClient("dummy-key")
        client.model = None
        client.client = None
        self.assertIn("temporarily unavailable", client.ask("hello").lower())


if __name__ == "__main__":
    unittest.main()
