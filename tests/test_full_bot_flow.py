import unittest

from app.gemini_client import GeminiClient


class FullBotBehaviorTests(unittest.TestCase):
    def test_language_detection_for_kurdish_text(self):
        self.assertEqual(GeminiClient.detect_language("سڵاو چۆنیت؟"), "kurdish")

    def test_language_detection_for_arabic_text(self):
        self.assertEqual(GeminiClient.detect_language("مرحبا كيف الحال؟"), "arabic")

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
