import unittest

from app.bot import (
    detect_lock_action,
    detect_moderation_action,
    detect_unlock_action,
    detect_unmute_action,
    extract_target_username,
    is_clear_chat_command,
        parse_clear_chat_count,
        build_command_guide,
        is_command_guide_request,
    permissions_for_lock,
    permissions_for_locks,
)


class ModerationKeywordDetectionTests(unittest.TestCase):
    def test_mute_keywords_include_persian_slang(self):
        for value in ["صامت", "سکوت", "samit", "sokot", "mute", "silent"]:
            self.assertEqual(detect_moderation_action(value), "mute")

    def test_ban_keywords_include_persian_slang(self):
        for value in ["بن", "ریمو", "remo", "ban", "kick", "remove"]:
            self.assertEqual(detect_moderation_action(value), "ban")

    def test_moderation_recognizes_replied_admin_commands(self):
        self.assertEqual(detect_moderation_action("admin says سکوت"), "mute")
        self.assertEqual(detect_moderation_action("بن این کاربر"), "ban")

    def test_lock_commands_are_detected_without_replies(self):
        commands = {
            "قفل گیف": "gif",
            "قفڵ موزیک": "music",
            "قفڵ فیلم": "video",
            "قفل عکس": "photo",
            "قفل استیکر": "sticker",
            "قفل فایل": "file",
            "هەمووی قفڵ بکە": "all",
            "قفل الموسيقى": "music",
            "قفل الفيديو": "video",
            "قفل الصور": "photo",
            "قفل الملصقات": "sticker",
            "قفل الملفات": "file",
            "قفل الكل": "all",
            "lock music": "music",
            "lock all": "all",
        }
        for command, action in commands.items():
            self.assertEqual(detect_lock_action(command), action, msg=command)

    def test_lock_permissions_disable_only_the_requested_media_type(self):
        self.assertFalse(permissions_for_lock("music").can_send_audios)
        self.assertTrue(permissions_for_lock("music").can_send_photos)
        self.assertFalse(permissions_for_lock("video").can_send_videos)
        self.assertFalse(permissions_for_lock("photo").can_send_photos)
        self.assertFalse(permissions_for_lock("file").can_send_documents)
        self.assertFalse(permissions_for_lock("gif").can_send_other_messages)
        self.assertFalse(permissions_for_lock("all").can_send_messages)

    def test_unlock_commands_are_detected_without_replies(self):
        commands = {
            "کردنەوەی گیف": "gif",
            "کردنەوەی موزیک": "music",
            "کردنەوەی فیلم": "video",
            "کردنەوەی وێنە": "photo",
            "کردنەوەی استیکر": "sticker",
            "کردنەوەی فایل": "file",
            "هەمووی بکەرەوە": "all",
            "باز کردن عکس": "photo",
            "باز کردن همه": "all",
            "فتح المتحركة": "gif",
            "فتح الكل": "all",
            "unlock sticker": "sticker",
            "unlock all": "all",
        }
        for command, action in commands.items():
            self.assertEqual(detect_unlock_action(command), action, msg=command)

    def test_unlock_permissions_preserve_other_locks(self):
        permissions = permissions_for_locks({"music", "photo"})
        self.assertFalse(permissions.can_send_audios)
        self.assertFalse(permissions.can_send_photos)
        self.assertTrue(permissions.can_send_videos)

    def test_unmute_commands_are_multilingual(self):
        for command in [
            "دەرهێنان لە بێدەنگی", "لادانی بێدەنگی", "بێدەنگ نەکردن",
            "لغو سکوت", "برداشتن سکوت", "صامت برداشتن", "آزاد کردن",
            "إلغاء الكتم", "رفع الكتم", "إلغاء الصامت", "unmute", "lift mute",
        ]:
            self.assertTrue(detect_unmute_action(command), msg=command)

    def test_unmute_target_must_be_reply_or_known_username(self):
        self.assertIsNone(extract_target_username("لغو سکوت"))
        self.assertEqual(extract_target_username("لغو سکوت @Example_User"), "example_user")
        self.assertTrue(detect_unmute_action("unmute @Example_User"))

    def test_clear_chat_commands_are_multilingual(self):
        for command in [
            "سڕینەوەی چاتەکان", "ڕەش کردنەوەی چاتەکان", "پاککردنەوەی چات",
            "حذف چت", "پاک کردن چت", "مسح المحادثة", "حذف الرسائل",
            "clear chat", "delete chat", "purge chat",
        ]:
            self.assertTrue(is_clear_chat_command(command), msg=command)

    def test_clear_chat_commands_accept_custom_counts(self):
        commands = {
            "پاکسازی 40": 40,
            "پاکسازی 150": 150,
            "clean 300": 300,
            "حذف 50": 50,
            "clear chat 25": 25,
        }
        for command, count in commands.items():
            self.assertEqual(parse_clear_chat_count(command), count, msg=command)
        self.assertEqual(parse_clear_chat_count("پاکسازی"), 500)
        self.assertIsNone(parse_clear_chat_count("پاکسازی abc"))

    def test_private_command_guide_requests_are_detected(self):
        for request in ["commands", "فەرمانەکان", "دستورات", "أوامر", "how to use"]:
            self.assertTrue(is_command_guide_request(request), msg=request)

    def test_command_guide_mentions_group_permissions_and_targets(self):
        guide = build_command_guide()
        self.assertIn("Admin/Manager", guide)
        self.assertIn("پاکسازی 50", guide)
        self.assertIn("@username", guide)


if __name__ == "__main__":
    unittest.main()
