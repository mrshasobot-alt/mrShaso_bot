import unittest
from types import SimpleNamespace

from app.gemini_client import GeminiClient


class GeminiClientTests(unittest.TestCase):
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
