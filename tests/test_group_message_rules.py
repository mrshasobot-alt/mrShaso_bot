import unittest

from app.bot import detect_greeting_language, greeting_response, is_greeting_message, is_reply_to_bot_message


class GroupMessageRulesTests(unittest.TestCase):
    def test_greeting_messages_are_detected_in_multiple_languages(self):
        for text in ["hello", "hi", "hey", "سلام", "سڵاو", "مرحبا", "اهلا", "hallo"]:
            self.assertTrue(is_greeting_message(text), msg=text)

    def test_non_greeting_text_is_not_treated_as_greeting(self):
        self.assertFalse(is_greeting_message("what is the weather today"))
        self.assertFalse(is_greeting_message("this is a hi example"))

    def test_greeting_language_and_response_are_localized(self):
        expected = {
            "سلام دوستان": ("persian", "سلام! خوش آمدید. 👋"),
            "سڵاو هاوڕێیان": ("kurdish", "سڵاو! بەخێربێیت. 👋"),
            "مرحبا بالجميع": ("arabic", "مرحبًا! أهلًا وسهلًا. 👋"),
            "Merhaba herkes": ("turkish", "Merhaba! Hoş geldiniz. 👋"),
            "hello everyone": ("english", "Hello! Welcome. 👋"),
            "good morning everyone": ("english", "Hello! Welcome. 👋"),
            "السلام عليكم جميعًا": ("arabic", "مرحبًا! أهلًا وسهلًا. 👋"),
        }
        for text, (language, response) in expected.items():
            self.assertEqual(detect_greeting_language(text), language, msg=text)
            self.assertEqual(greeting_response(language), response)

    def test_persian_greeting_has_only_the_short_welcome(self):
        self.assertEqual(greeting_response(detect_greeting_language("سلام")), "سلام! خوش آمدید. 👋")

    def test_reply_to_bot_message_is_detected_by_bot_id(self):
        class FakeUser:
            def __init__(self, user_id):
                self.id = user_id

        class FakeReply:
            def __init__(self, user_id):
                self.from_user = FakeUser(user_id)

        self.assertTrue(is_reply_to_bot_message(FakeReply(42), 42))
        self.assertFalse(is_reply_to_bot_message(FakeReply(99), 42))


if __name__ == "__main__":
    unittest.main()
