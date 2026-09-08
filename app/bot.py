from __future__ import annotations

import asyncio
import importlib
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from telegram import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import Settings
from app.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

MEDIA_URL_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
SOCIAL_MEDIA_DIRECTORY = Path("social_media_files")
SUPPORTED_CONVERSION_OPERATIONS = frozenset({
    "mp3_voice", "voice_mp3", "video_mp3", "video_voice",
})
SOCIAL_AUDIO_SUFFIXES = frozenset({".mp3", ".m4a", ".wav", ".flac"})
SOCIAL_VOICE_SUFFIXES = frozenset({".ogg"})
SOCIAL_VIDEO_SUFFIXES = frozenset({".mp4", ".mkv", ".webm", ".mov", ".avi"})

BOT_PROFILE_NAME = "🦋𝄟⃝ ᴠͥɪͣᴘͫ Ｓｈａ"
START_MESSAGE_DELETE_DELAY = 30
SELECTED_LANGUAGE_KEY = "selected_language"
MENU_MODE_KEY = "menu_mode"

LANGUAGE_OPTIONS = (
    ("کوردی", "kurdish"),
    ("فارسی", "persian"),
    ("عەرەبی", "arabic"),
    ("English", "english"),
    ("Türkçe", "turkish"),
)

LANGUAGE_BUTTON_TEXT = {
    "kurdish": {
        "kurdish": "کوردی", "persian": "فارسی", "arabic": "عەرەبی",
        "english": "ئینگلیزی", "turkish": "تورکی",
    },
    "persian": {
        "kurdish": "کردی", "persian": "فارسی", "arabic": "عربی",
        "english": "انگلیسی", "turkish": "ترکی",
    },
    "arabic": {
        "kurdish": "الكردية", "persian": "الفارسية", "arabic": "العربية",
        "english": "الإنجليزية", "turkish": "التركية",
    },
    "english": {
        "kurdish": "Kurdish", "persian": "Persian", "arabic": "Arabic",
        "english": "English", "turkish": "Turkish",
    },
    "turkish": {
        "kurdish": "Kürtçe", "persian": "Farsça", "arabic": "Arapça",
        "english": "İngilizce", "turkish": "Türkçe",
    },
}

MENU_TEXT = {
    "kurdish": {"title": "🦋 مینیوی سەرەکی MrShaso", "language": "🌐 زمان", "chat": "💬 چات / گفتوگۆ", "converter": "🛠️ کۆنفێرتەر", "media": "داگرتنی لێنکی میدیا", "social_files": "فایلەکانی سۆشیال میدیا", "refresh": "🔄 نوێکردنەوەی menu", "back": "🔙 گەڕانەوە بۆ پەڕەی سەرەکی", "choose": "تکایە بەشێک هەڵبژێرە:", "language_chosen": "زمان هەڵبژێردرا: کوردی", "converter_prompt": "📥 تکایە فایلەکە بنێرە بۆ دەستپێکردنی گۆڕین.", "media_prompt": "🔗 تکایە لینکی میدیا بنێرە یان فایلەکە ڕاستەوخۆ upload بکە."},
    "persian": {"title": "🦋 منوی اصلی MrShaso", "language": "🌐 زبان", "chat": "💬 گفتگو", "converter": "🛠️ تبدیل‌کننده", "media": "دانلود لینک رسانه", "social_files": "فایل‌های شبکه‌های اجتماعی", "refresh": "🔄 تازه‌سازی منو", "back": "🔙 بازگشت به منوی اصلی", "choose": "یک بخش را انتخاب کنید:", "language_chosen": "زبان انتخاب شد: فارسی", "converter_prompt": "📥 لطفاً فایل را برای تبدیل ارسال کنید.", "media_prompt": "🔗 لطفاً لینک رسانه یا فایل را ارسال کنید."},
    "arabic": {"title": "🦋 القائمة الرئيسية MrShaso", "language": "🌐 اللغة", "chat": "💬 الدردشة", "converter": "🛠️ المحوّل", "media": "تنزيل رابط الوسائط", "social_files": "ملفات التواصل الاجتماعي", "refresh": "🔄 تحديث القائمة", "back": "🔙 العودة إلى القائمة الرئيسية", "choose": "اختر قسمًا:", "language_chosen": "تم اختيار العربية", "converter_prompt": "📥 أرسل الملف لبدء التحويل.", "media_prompt": "🔗 أرسل رابط الوسائط أو الملف مباشرة."},
    "english": {"title": "", "language": "🌐 Language", "chat": "💬 Chat", "converter": "🛠️ Converter", "media": "Media Link Downloader", "social_files": "Social Media Files", "refresh": "🔄 Refresh menu", "back": "🔙 Back to Main Menu", "choose": "", "language_chosen": "Language selected: English", "converter_prompt": "📥 Send a file to start conversion.", "media_prompt": "🔗 Send a media link or upload a file."},
    "turkish": {"title": "🦋 MrShaso Ana Menü", "language": "🌐 Dil", "chat": "💬 Sohbet", "converter": "🛠️ Dönüştürücü", "media": "Medya bağlantısı indirici", "social_files": "Sosyal medya dosyaları", "refresh": "🔄 Menüyü yenile", "back": "🔙 Ana menüye dön", "choose": "Bir bölüm seçin:", "language_chosen": "Dil seçildi: Türkçe", "converter_prompt": "📥 Dönüştürmek için bir dosya gönderin.", "media_prompt": "🔗 Bir medya bağlantısı veya dosya gönderin."},
}

RUNTIME_TEXT = {
    "kurdish": {
        "error": "⚠️ هەڵەیەک ڕوویدا. تکایە دووبارە هەوڵ بدەرەوە.", "thinking": "بیر دەکەمەوە...", "usage_ask": "بەکارهێنان: /ask <پرسیار>", "cleared": "✅ کۆنتێکستی گفتوگۆ پاککرایەوە.", "online": "✅ بۆتەکە چالاکە", "language_support": "پشتیوانی زمان: کوردی، فارسی، عەرەبی، ئینگلیزی و زیاتر", "searching": "⏳ بەدوای میدیا دەگەڕێم و دایدەگرم...", "download_error": "⚠️ نەتوانرا ئەم لینکە جێبەجێ بکرێت: {error}", "stored": "✅ فایلەکە بە سەرکەوتوویی لە فایلەکانی سۆشیال میدیا هەڵگیرا.", "file_error": "⚠️ نەتوانرا فایلەکە جێبەجێ بکرێت: {error}", "wrong_link": "⚠️ ئەم لینکە هی بەشی {platform} نییە. تکایە لە بەشی تایبەتی خۆیدا بەکاری بهێنە.", "locked": "🔒 {action_label} داخرا.", "unlocked": "🔓 {action_label} کرایەوە.", "failed_restriction": "⚠️ نەتوانرا سنووردارییەکە نوێ بکرێتەوە.", "unmuted": "🔊 بەکارهێنەر {name} لە بێدەنگی دەرکرا.", "muted": "🔇 بەکارهێنەر {name} بێدەنگ کرا.", "banned": "⛔ بەکارهێنەر {name} ڕاگیرا.", "failed_moderation": "⚠️ فەرمانی چاودێری جێبەجێ نەکرا.", "upload": "🔗 تکایە لینک یان فایلێکی میدیا بنێرە."},
    "persian": {
        "error": "⚠️ خطایی رخ داد. دوباره تلاش کنید.", "thinking": "در حال فکر کردن...", "usage_ask": "نحوه استفاده: /ask <سؤال>", "cleared": "✅ زمینه گفتگو پاک شد.", "online": "✅ ربات فعال است", "language_support": "پشتیبانی زبان: کردی، فارسی، عربی، انگلیسی و بیشتر", "searching": "⏳ در حال دریافت رسانه...", "download_error": "⚠️ لینک اجرا نشد: {error}", "stored": "✅ فایل در فایل‌های شبکه‌های اجتماعی ذخیره شد.", "file_error": "⚠️ فایل پردازش نشد: {error}", "wrong_link": "⚠️ این لینک مربوط به بخش {platform} نیست.", "locked": "🔒 {action_label} قفل شد.", "unlocked": "🔓 {action_label} باز شد.", "failed_restriction": "⚠️ محدودیت به‌روزرسانی نشد.", "unmuted": "🔊 کاربر {name} از سکوت خارج شد.", "muted": "🔇 کاربر {name} بی‌صدا شد.", "banned": "⛔ کاربر {name} مسدود شد.", "failed_moderation": "⚠️ فرمان مدیریت اجرا نشد.", "upload": "🔗 لطفاً لینک یا فایل رسانه‌ای ارسال کنید."},
    "arabic": {
        "error": "⚠️ حدث خطأ. حاول مرة أخرى.", "thinking": "جارٍ التفكير...", "usage_ask": "الاستخدام: /ask <سؤالك>", "cleared": "✅ تم مسح سياق المحادثة.", "online": "✅ البوت يعمل", "language_support": "اللغات المدعومة: الكردية والفارسية والعربية والإنجليزية وغيرها", "searching": "⏳ جارٍ تنزيل الوسائط...", "download_error": "⚠️ تعذر تنفيذ الرابط: {error}", "stored": "✅ تم حفظ الملف في ملفات التواصل الاجتماعي.", "file_error": "⚠️ تعذر معالجة الملف: {error}", "wrong_link": "⚠️ هذا الرابط ليس لقسم {platform}.", "locked": "🔒 تم قفل {action_label}.", "unlocked": "🔓 تم فتح {action_label}.", "failed_restriction": "⚠️ تعذر تحديث القيد.", "unmuted": "🔊 تم إلغاء كتم {name}.", "muted": "🔇 تم كتم {name}.", "banned": "⛔ تم حظر {name}.", "failed_moderation": "⚠️ تعذر تنفيذ أمر الإدارة.", "upload": "🔗 أرسل رابط وسائط أو ملفًا."},
    "english": {
        "error": "⚠️ Something went wrong. Please try again.", "thinking": "Thinking...", "usage_ask": "Usage: /ask <your question>", "cleared": "✅ Conversation context cleared.", "online": "✅ Bot is online", "language_support": "Language support: Kurdish, Persian, Arabic, English, and more", "searching": "⏳ Downloading media...", "download_error": "⚠️ Could not process this link: {error}", "stored": "✅ File saved in Social Media Files.", "file_error": "⚠️ Could not process this file: {error}", "wrong_link": "⚠️ This link does not belong to the {platform} section.", "locked": "🔒 {action_label} locked.", "unlocked": "🔓 {action_label} unlocked.", "failed_restriction": "⚠️ Could not update the restriction.", "unmuted": "🔊 User {name} unmuted.", "muted": "🔇 User {name} muted.", "banned": "⛔ User {name} banned.", "failed_moderation": "⚠️ Could not apply the moderation command.", "upload": "🔗 Send a media link or upload a file."},
    "turkish": {
        "error": "⚠️ Bir hata oluştu. Lütfen tekrar deneyin.", "thinking": "Düşünüyorum...", "usage_ask": "Kullanım: /ask <sorunuz>", "cleared": "✅ Konuşma bağlamı temizlendi.", "online": "✅ Bot çevrimiçi", "language_support": "Dil desteği: Kürtçe, Farsça, Arapça, İngilizce ve daha fazlası", "searching": "⏳ Medya indiriliyor...", "download_error": "⚠️ Bu bağlantı işlenemedi: {error}", "stored": "✅ Dosya Sosyal Medya Dosyaları'na kaydedildi.", "file_error": "⚠️ Dosya işlenemedi: {error}", "wrong_link": "⚠️ Bu bağlantı {platform} bölümüne ait değil.", "locked": "🔒 {action_label} kilitlendi.", "unlocked": "🔓 {action_label} açıldı.", "failed_restriction": "⚠️ Kısıtlama güncellenemedi.", "unmuted": "🔊 {name} kullanıcısının sessizliği kaldırıldı.", "muted": "🔇 {name} susturuldu.", "banned": "⛔ {name} kullanıcısı engellendi.", "failed_moderation": "⚠️ Yönetim komutu uygulanamadı.", "upload": "🔗 Bir medya bağlantısı veya dosya gönderin."},
}


def localized_message(language: str | None, key: str, **values: object) -> str:
    selected = _menu_language(language)
    return RUNTIME_TEXT[selected][key].format(**values)

CHAT_WELCOME_TEXT = {
    "kurdish": "بەخێربێی بەڕێزم چۆن دەتوانم هاوکاریت بکەم ؟☺️",
    "persian": "خوش آمدی عزیزم، چطور می‌توانم کمکت کنم؟ ☺️",
    "arabic": "أهلًا بك عزيزي، كيف يمكنني مساعدتك؟ ☺️",
    "english": "Welcome, dear. How can I help you? ☺️",
    "turkish": "Hoş geldin, nasıl yardımcı olabilirim? ☺️",
}

PRIVATE_CHAT_HEADER_TEXT = {
    "kurdish": "💬 چاتی تایبەت",
    "persian": "💬 گفتگوی خصوصی",
    "arabic": "💬 الدردشة الخاصة",
    "english": "💬 Private Chat",
    "turkish": "💬 Özel Sohbet",
}

MENU_ACTION_TEXT = {
    "kurdish": {
        "mp3_voice": "🎵 MP3 → Voice", "voice_mp3": "🎙️ Voice → MP3",
        "video_mp3": "🎬 Video → MP3", "video_voice": "📹 Video → Voice",
        "facebook": "📘 فەیسبووک", "tiktok": "🎵 تیک تۆک",
        "instagram": "📸 اینستاگرام", "snapchat": "👻 سناپ چات",
        "social_files": "📱 فایلەکانی سۆشیال میدیا",
    },
    "persian": {
        "mp3_voice": "🎵 MP3 → صدا", "voice_mp3": "🎙️ صدا → MP3",
        "video_mp3": "🎬 ویدیو → MP3", "video_voice": "📹 ویدیو → صدا",
        "facebook": "📘 فیسبوک", "tiktok": "🎵 تیک‌تاک",
        "instagram": "📸 اینستاگرام", "snapchat": "👻 اسنپ‌چت",
        "social_files": "📱 فایل‌های شبکه‌های اجتماعی",
    },
    "arabic": {
        "mp3_voice": "🎵 MP3 ← صوت", "voice_mp3": "🎙️ صوت ← MP3",
        "video_mp3": "🎬 فيديو ← MP3", "video_voice": "📹 فيديو ← صوت",
        "facebook": "📘 فيسبوك", "tiktok": "🎵 تيك توك",
        "instagram": "📸 إنستغرام", "snapchat": "👻 سناب شات",
        "social_files": "📱 ملفات التواصل الاجتماعي",
    },
    "english": {
        "mp3_voice": "🎵 MP3 → Voice", "voice_mp3": "🎙️ Voice → MP3",
        "video_mp3": "🎬 Video → MP3", "video_voice": "📹 Video → Voice",
        "facebook": "📘 Facebook", "tiktok": "🎵 TikTok",
        "instagram": "📸 Instagram", "snapchat": "👻 Snapchat",
        "social_files": "📱 Social media files",
    },
    "turkish": {
        "mp3_voice": "🎵 MP3 → Ses", "voice_mp3": "🎙️ Ses → MP3",
        "video_mp3": "🎬 Video → MP3", "video_voice": "📹 Video → Ses",
        "facebook": "📘 Facebook", "tiktok": "🎵 TikTok",
        "instagram": "📸 Instagram", "snapchat": "👻 Snapchat",
        "social_files": "📱 Sosyal medya dosyaları",
    },
}


def _menu_language(language: str | None) -> str:
    return language if language in MENU_TEXT else "kurdish"


def build_back_button(language: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(MENU_TEXT[_menu_language(language)]["back"], callback_data="menu:main")]


def build_section_header(label: str, section: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(f"— {label} —", callback_data=f"menu:section:{section}")]


def build_main_menu(language: str = "kurdish") -> InlineKeyboardMarkup:
    selected_language = _menu_language(language)
    labels = MENU_TEXT[selected_language]
    actions = MENU_ACTION_TEXT[selected_language]
    translated_languages = LANGUAGE_BUTTON_TEXT[selected_language]
    language_buttons = [
        InlineKeyboardButton(translated_languages[code], callback_data=f"language:{code}")
        for _, code in LANGUAGE_OPTIONS
    ]
    return InlineKeyboardMarkup([
        build_section_header(labels["language"], "language"),
        language_buttons[:3],
        language_buttons[3:],
        [InlineKeyboardButton(f"— {PRIVATE_CHAT_HEADER_TEXT[_menu_language(language)]} —", callback_data="menu:chat")],
        build_section_header(labels["converter"], "converter"),
        [InlineKeyboardButton(actions["mp3_voice"], callback_data="menu:converter:mp3_voice"), InlineKeyboardButton(actions["voice_mp3"], callback_data="menu:converter:voice_mp3")],
        [InlineKeyboardButton(actions["video_mp3"], callback_data="menu:converter:video_mp3"), InlineKeyboardButton(actions["video_voice"], callback_data="menu:converter:video_voice")],
        build_section_header(labels["media"], "media"),
        [InlineKeyboardButton(actions["facebook"], callback_data="menu:media:facebook"), InlineKeyboardButton(actions["tiktok"], callback_data="menu:media:tiktok")],
        [InlineKeyboardButton(actions["instagram"], callback_data="menu:media:instagram"), InlineKeyboardButton(actions["snapchat"], callback_data="menu:media:snapchat")],
        [InlineKeyboardButton(f"— 📱 {labels['social_files']} —", callback_data="menu:media:upload")],
        [InlineKeyboardButton(labels["refresh"], callback_data="menu:main")],
    ])


def main_menu_text(language: str = "kurdish") -> str:
    return "🦋𝄟⃝ ᴠͥɪͣᴘͫ Ｓｈａ"


def build_language_menu(language: str = "kurdish") -> InlineKeyboardMarkup:
    selected_language = _menu_language(language)
    translated_labels = LANGUAGE_BUTTON_TEXT[selected_language]
    keyboard = [
        [InlineKeyboardButton(translated_labels[code], callback_data=f"language:{code}")]
        for _, code in LANGUAGE_OPTIONS
    ]
    keyboard.append(build_back_button(selected_language))
    return InlineKeyboardMarkup(keyboard)


def build_converter_menu(language: str) -> InlineKeyboardMarkup:
    actions = MENU_ACTION_TEXT[_menu_language(language)]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(actions["mp3_voice"], callback_data="menu:converter:mp3_voice")],
        [InlineKeyboardButton(actions["voice_mp3"], callback_data="menu:converter:voice_mp3")],
        [InlineKeyboardButton(actions["video_mp3"], callback_data="menu:converter:video_mp3")],
        [InlineKeyboardButton(actions["video_voice"], callback_data="menu:converter:video_voice")],
        build_back_button(language),
    ])


def build_media_menu(language: str) -> InlineKeyboardMarkup:
    actions = MENU_ACTION_TEXT[_menu_language(language)]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(actions["facebook"], callback_data="menu:media:facebook"), InlineKeyboardButton(actions["tiktok"], callback_data="menu:media:tiktok")],
        [InlineKeyboardButton(actions["instagram"], callback_data="menu:media:instagram"), InlineKeyboardButton(actions["snapchat"], callback_data="menu:media:snapchat")],
        [InlineKeyboardButton(actions["social_files"], callback_data="menu:media:upload")],
        build_back_button(language),
    ])


def language_menu_text(language: str = "kurdish") -> str:
    return f"──────────\n{MENU_TEXT[_menu_language(language)]['language']}\n──────────"


def detect_response_language(text: str) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return "english"

    kurdish_markers = set("ڕڵۆێەئڤ")
    persian_markers = set("پچژگ")
    turkish_markers = set("ğışöü")
    if any(character in normalized for character in kurdish_markers):
        return "kurdish"
    if any(character in normalized for character in persian_markers):
        return "persian"
    if any(character in normalized for character in turkish_markers):
        return "turkish"

    persian_words = {"سلام", "درود", "خوب", "چطور", "هستم", "فارسی", "ممنون"}
    turkish_words = {"merhaba", "selam", "nasıl", "teşekkür", "türkçe", "misin"}
    arabic_words = {"مرحبا", "أهلا", "اهلا", "كيف", "العربية", "شكرا"}
    words = set(normalized.split())
    if words & persian_words:
        return "persian"
    if words & turkish_words:
        return "turkish"
    if words & arabic_words:
        return "arabic"
    if re.search(r"[\u0600-\u06ff]", normalized):
        return "arabic"
    return "english"


def build_selected_language_instruction(language: str) -> str:
    language_names = {
        "sorani": "Sorani Kurdish",
        "kurmanji": "Kurmanji Kurdish",
        "persian": "Persian",
        "arabic": "Arabic",
        "turkish": "Turkish",
        "english": "English",
    }
    base_language = "kurdish" if language in {"sorani", "kurmanji"} else language
    instruction = GeminiClient.build_system_prompt(base_language)
    selected_name = language_names.get(language, "the detected language")
    return (
        f"{instruction} Reply ONLY in {selected_name}. Do not mix languages, translate, "
        "or include explanations in any other language."
    )


def build_response_instruction(text: str, selected_language: str | None = None) -> str:
    language = selected_language or detect_response_language(text)
    return build_selected_language_instruction(language)


IDENTITY_RESPONSE = (
    "ناوم\n"
    "🦋𝄟⃝ ᴠͥɪͣᴘͫ ᴍʀꜱʜᴀsᴏ\n"
    "@mrShaso\n"
    "تەمەنم 36 ساڵە خەڵکی کوردستانم"
)

IDENTITY_RESPONSES = {
    "persian": "🦋𝄟⃝ ᴠͥɪͣᴘͫ ᴍʀꜱʜᴀsᴏ\n@mrShaso\nسن من ۳۶ سال است و اهل کردستان هستم",
    "kurdish": "🦋𝄟⃝ ᴠͥɪͣᴘͫ ᴍʀꜱʜᴀsᴏ\n@mrShaso\nتەمەنم 36 ساڵە خەڵکی کوردستانم",
    "arabic": "🦋𝄟⃝ ᴠͥɪͣᴘͫ ᴍʀꜱʜᴀsᴏ\n@mrShaso\nعمري 36 سنة وأنا من كردستان",
    "english": "🦋𝄟⃝ ᴠͥɪͣᴘͫ ᴍʀꜱʜᴀsᴏ\n@mrShaso\nI am 36 years old and I am from Kurdistan",
    "turkish": "🦋𝄟⃝ ᴠͥɪͣᴘͫ ᴍʀꜱʜᴀsᴏ\n@mrShaso\n36 yaşındayım ve Kürdistanlıyım",
}


def is_identity_question(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False

    identity_phrases = {
        "ناوت چیە", "ناوت چیه", "ناوی تۆ چیە", "ناوی تۆ چیه",
        "خۆت بناسێنە", "خۆت بناسێنه", "تۆ کێیت", "تۆ کێی",
        "ناوت چیه و خۆت بناسێنە", "بنەڕەتت چیە", "بنەڕەتت چیه",
        "اسمت چیه", "اسم شما چیست", "خودت را معرفی کن", "معرفی کن",
        "اصلت چیه", "اصل من کجایی", "اصل شما کجاست", "اهل کجایی", "کی هستی",
        "ما اسمك", "ما اسمك؟", "من أنت", "عرف نفسك", "من انت",
        "اسمك ايه", "من اين انت",
        "adın ne", "adin ne", "sen kimsin", "kendini tanıt",
        "kendini tanit", "nerelisin",
        "what is your name", "what's your name", "who are you",
        "introduce yourself", "tell me about yourself", "where are you from",
        "اصل بده", "اصل میدی", "معرفی میکنی", "سن", "کجا زندگی",
        "ناسنامە", "تەمەن", "چەند ساڵتە", "خەڵکی کوێی",
        "عرفني", "كم عمرك", "اصلك", "معرفة",
        "how old are you", "bio", "kendini tanıt", "kaç yaşındasın",
        "nerelisin", "adın ne",
    }
    if normalized in identity_phrases:
        return True

    identity_markers = (
        "ناوت چی", "ناوت چیه", "خۆت بناسێن", "تۆ کێ",
        "اسمت چ", "معرفی کن", "اصلت چ", "اصل من", "اصل شما", "من أنت", "من انت",
        "ما اسمك", "عرف نفسك", "adın ne", "adin ne", "sen kimsin",
        "what is your name", "what's your name", "who are you",
        "introduce yourself",
        "اصل", "معرفی", "سن", "کجا زندگی", "ناسنامە", "تەمەن",
        "عرفني", "كم عمرك", "اصلك", "معرفة", "how old are you", "bio",
        "kendini tanıt", "kaç yaşındasın", "nerelisin", "adın ne",
    )
    return any(marker in normalized for marker in identity_markers)


def identity_response(text: str) -> str:
    normalized = normalize_text(text)
    if any(keyword in normalized for keyword in ("خۆت بناسێن", "ناسنامە", "تەمەن", "چەند ساڵ", "خەڵکی کوێ")):
        language = "kurdish"
    elif any(keyword in normalized for keyword in ("عرفني", "من أنت", "كم عمرك", "اصلك", "معرفة")):
        language = "arabic"
    elif any(keyword in normalized for keyword in ("kendini tanıt", "kaç yaşındasın", "nerelisin", "adın ne")):
        language = "turkish"
    elif any(keyword in normalized.split() for keyword in ("اصل", "معرفی", "سن")) or any(keyword in normalized for keyword in ("کجا زندگی", "اسم شما")):
        language = "persian"
    else:
        language = detect_response_language(text)
    return IDENTITY_RESPONSES.get(language, IDENTITY_RESPONSE)


def should_answer_identity(update: Update, bot_user_id: int | None) -> bool:
    """Allow identity replies privately or only when a group message replies to this bot."""
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None or not message.text or not is_identity_question(message.text):
        return False
    if chat.type == "private":
        return True
    if chat.type not in {"group", "supergroup"} or bot_user_id is None:
        return False
    return is_reply_to_bot_message(message.reply_to_message, bot_user_id)


def normalize_text(value: str) -> str:
    if not value:
        return ""
    text = value.lower().strip()
    text = re.sub(r"[\u200c\u200d\s\t\n]+", " ", text)
    text = re.sub(r"[^\w\s\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]", " ", text)
    return " ".join(text.split())


def extract_media_url(text: str) -> str | None:
    match = MEDIA_URL_PATTERN.search(text or "")
    if not match:
        return None
    url = match.group(0).rstrip(".,!?)]}")
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else None


def detect_media_platform(url: str) -> str | None:
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if hostname == "tiktok.com" or hostname.endswith(".tiktok.com"):
        return "tiktok"
    if hostname in {"facebook.com", "fb.watch"} or hostname.endswith(".facebook.com"):
        return "facebook"
    if hostname == "instagram.com" or hostname.endswith(".instagram.com"):
        return "instagram"
    if hostname in {"snapchat.com", "snap.com"} or hostname.endswith(".snapchat.com"):
        return "snapchat"
    return None


def media_url_matches_mode(url: str, mode: str) -> bool:
    if mode == "media:upload":
        return True
    if not mode.startswith("media:"):
        return False
    return detect_media_platform(url) == mode.removeprefix("media:")


def social_media_kind(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in SOCIAL_AUDIO_SUFFIXES:
        return "audio"
    if suffix in SOCIAL_VOICE_SUFFIXES:
        return "voice"
    if suffix in SOCIAL_VIDEO_SUFFIXES:
        return "video"
    return None


def _download_url_sync(url: str, workdir: str) -> Path:
    try:
        yt_dlp = importlib.import_module("yt_dlp")
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed") from exc

    options = {
        "outtmpl": str(Path(workdir) / "download.%(ext)s"),
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        downloader.download([url])

    candidates = [path for path in Path(workdir).iterdir() if path.is_file()]
    if not candidates:
        raise RuntimeError("No media was downloaded")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _convert_media_sync(source: Path, operation: str, workdir: str) -> Path:
    if operation not in SUPPORTED_CONVERSION_OPERATIONS:
        raise ValueError(f"Unsupported conversion operation: {operation}")
    output_suffix = ".mp3" if operation in {"voice_mp3", "video_mp3"} else ".ogg"
    output = Path(workdir) / f"converted{output_suffix}"
    codec_args = ["-vn", "-codec:a", "libmp3lame", "-q:a", "4"] if output_suffix == ".mp3" else [
        "-vn", "-codec:a", "libopus", "-b:a", "64k"
    ]
    if operation == "video_voice":
        codec_args = ["-vn", "-codec:a", "libopus", "-b:a", "64k"]

    command = ["ffmpeg", "-y", "-i", str(source), *codec_args, str(output)]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is not installed or is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("ffmpeg could not convert this media") from exc
    return output


def _media_suffix(message: object) -> str:
    for attribute in ("audio", "voice", "video", "video_note", "document"):
        media = getattr(message, attribute, None)
        if media is not None:
            filename = getattr(media, "file_name", None) or ""
            suffix = Path(filename).suffix
            if suffix:
                return suffix
            mime_type = getattr(media, "mime_type", None)
            return mimetypes.guess_extension(mime_type or "") or ".bin"
    return ".bin"


def is_greeting_message(text: str) -> bool:
    return detect_greeting_language(text) is not None


def detect_greeting_language(text: str) -> str | None:
    normalized = normalize_text(text)
    if not normalized:
        return None

    greeting_phrases = {
        "persian": {
            "سلام", "درود", "خوش آمدید", "سلام دوستان", "سلام بر شما",
        },
        "kurdish": {
            "سڵاو", "سڵاو هاوڕێیان", "بەخێربێیت", "بەخێربێن", "خۆش هاتن",
        },
        "arabic": {
            "مرحبا", "أهلا", "اهلا", "هلا", "السلام عليكم", "صباح الخير",
            "مساء الخير",
        },
        "turkish": {
            "merhaba", "selam", "günaydın", "iyi akşamlar", "hoş geldiniz",
        },
        "english": {
            "hello", "hi", "hey", "hallo", "helo", "hullo", "good morning",
            "good evening", "good night",
        },
    }

    for language, phrases in greeting_phrases.items():
        if any(normalized == phrase or normalized.startswith(f"{phrase} ") for phrase in phrases):
            return language

    words = normalized.split()
    single_word_greetings = {
        "persian": {"سلام", "درود"},
        "kurdish": {"سڵاو", "بەخێربێیت", "بەخێربێن"},
        "arabic": {"مرحبا", "اهلا", "أهلا", "هلا"},
        "turkish": {"merhaba", "selam"},
        "english": {"hello", "hi", "hey", "hallo", "helo", "hullo"},
    }
    for language, greetings in single_word_greetings.items():
        if words and words[0] in greetings:
            return language

    return None


def greeting_response(language: str) -> str:
    responses = {
        "persian": "سلام! خوش آمدید. 👋",
        "kurdish": "سڵاو! بەخێربێیت. 👋",
        "arabic": "مرحبًا! أهلًا وسهلًا. 👋",
        "turkish": "Merhaba! Hoş geldiniz. 👋",
        "english": "Hello! Welcome. 👋",
    }
    return responses.get(language, responses["english"])


def is_reply_to_bot_message(reply_message: object | None, bot_user_id: int | None) -> bool:
    if not reply_message or bot_user_id is None:
        return False
    from_user = getattr(reply_message, "from_user", None)
    if not from_user:
        return False
    return getattr(from_user, "id", None) == bot_user_id


def detect_moderation_action(text: str) -> str | None:
    normalized = normalize_text(text)
    if not normalized:
        return None

    mute_keywords = {
        "mute", "muted", "moot", "sokot", "سکوت", "صامت", "samit", "silent", "silence",
        "mute user", "muteuser", "نکوت", "صمت", "سكت", "كمت", "کتم", "کوت",
        "موت", "هموت", "sokut", "sokot"
    }
    ban_keywords = {
        "ban", "banned", "kick", "kickout", "kick out", "kickuser", "kick user", "ben", "بن",
        "remo", "ریمو", "remove", "remove user", "ban user", "حظر", "طرد", "اخراج", "إيقاف",
        "بند", "بَن", "بن user", "ريمو", "رِيمو"
    }

    for keyword in mute_keywords:
        if keyword in normalized:
            return "mute"

    for keyword in ban_keywords:
        if keyword in normalized:
            return "ban"

    return None


def detect_unmute_action(text: str) -> bool:
    text_without_target = re.sub(r"@[a-z0-9_]{5,32}", "", text, flags=re.IGNORECASE)
    normalized = normalize_text(text_without_target)
    unmute_phrases = {
        "unmute", "lift mute", "لغو سکوت", "برداشتن سکوت", "صامت برداشتن",
        "آزاد کردن", "دەرهێنان لە بێدەنگی", "لادانی بێدەنگی", "بێدەنگ نەکردن",
        "إلغاء الكتم", "رفع الكتم", "إلغاء الصامت",
    }
    return normalized in unmute_phrases


def extract_target_username(text: str) -> str | None:
    match = re.search(r"@([A-Za-z0-9_]{5,32})", text)
    return match.group(1).lower() if match else None


def parse_clear_chat_count(text: str) -> int | None:
    normalized = normalize_text(text)
    phrases = {
        "سڕینەوەی چاتەکان", "ڕەش کردنەوەی چاتەکان", "پاککردنەوەی چات", "پاکسازی",
        "حذف", "حذف چت", "پاک کردن چت", "پاکسازی چت", "حذف گروه",
        "مسح المحادثة", "حذف الرسائل", "تنظيف المجموعة", "مسح الدردشة",
        "clear chat", "delete chat", "clear group", "purge chat", "clean",
    }
    if normalized in phrases:
        return 500

    for phrase in phrases:
        match = re.fullmatch(rf"{re.escape(phrase)}\s+(\d+)", normalized)
        if match:
            return max(1, int(match.group(1)))
    return None


def is_clear_chat_command(text: str) -> bool:
    return parse_clear_chat_count(text) is not None


def is_command_guide_request(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized in {
        "commands", "command", "help", "bot commands", "how to use",
        "فەرمانەکان", "فەرمان", "چۆن بەکاری بهێنم", "ڕێنمایی",
        "دستورها", "دستورات", "راهنما", "دستور", "أوامر", "أمر",
        "كيف استخدم البوت", "مساعدة",
    }

COMMAND_GUIDES = {
    "kurdish": "ڕێنمایی فەرمانەکانی بۆت:\n\n• /start - دەستپێکردن\n• /help - ئەم ڕێنماییە\n• /ask <پرسیار> - پرسیارکردن لە Gemini\n• /status - دۆخی بۆت\n• /language - زمانەکان\n• /clear - پاککردنەوەی گفتوگۆ\n\nلە گرووپ، تەنها Admin/Manager:\n• قفڵکردن و کردنەوەی قفڵی میدیا\n• پاکسازی: پاکسازی 50، clean 100، حذف 50\n• بێدەنگکردن و ئازادکردن تەنها بە Reply یان @username\n• سزا/ban تەنها بە Reply یان @username\n\nبۆتەکە دەبێت لە گرووپدا Admin بێت و دەسەڵاتی سڕینەوە و گۆڕینی permissions ـی هەبێت.",
    "persian": "راهنمای دستورات ربات:\n\n• /start - شروع\n• /help - این راهنما\n• /ask <سؤال> - پرسش از Gemini\n• /status - وضعیت ربات\n• /language - زبان‌ها\n• /clear - پاک کردن گفتگو\n\nدر گروه فقط مدیر می‌تواند دستورات مدیریتی را اجرا کند.",
    "arabic": "دليل أوامر البوت:\n\n• /start - البدء\n• /help - هذا الدليل\n• /ask <سؤال> - سؤال Gemini\n• /status - حالة البوت\n• /language - اللغات\n• /clear - مسح المحادثة\n\nفي المجموعة يستطيع المشرف فقط تنفيذ أوامر الإدارة.",
    "english": "Bot command guide:\n\n• /start - Start\n• /help - This guide\n• /ask <question> - Ask Gemini\n• /status - Bot status\n• /language - Languages\n• /clear - Clear conversation\n\nOnly group administrators can run moderation commands.",
    "turkish": "Bot komutları:\n\n• /start - Başlat\n• /help - Bu rehber\n• /ask <soru> - Gemini’ye sor\n• /status - Bot durumu\n• /language - Diller\n• /clear - Sohbeti temizle\n\nGrupta yönetim komutlarını yalnızca yöneticiler çalıştırabilir.",
}


def build_command_guide(language: str = "kurdish") -> str:
    return COMMAND_GUIDES[_menu_language(language)]

def detect_lock_action(text: str) -> str | None:
    normalized = normalize_text(text)
    if not normalized:
        return None

    lock_phrases = {
        "gif": {
            "lock gif", "lock gifs", "قفل گیف", "قفڵ گیف", "قفڵ گیفەکان",
            "گیف قفل", "گیف قفڵ", "گیفەکان قفل", "گیفەکان قفڵ",
            "قفل گیفەکان",
        },
        "music": {
            "lock music", "lock audio", "قفل موزیک", "قفڵ موزیک", "قفل موسیقی",
            "قفڵ موسیقا", "موزیک قفل", "مۆسیقا قفڵ", "ئاهەنگ قفڵ",
            "قفل الموسيقى",
        },
        "video": {
            "lock video", "lock videos", "قفل فیلم", "قفڵ فیلم", "قفل ڤیدیۆ",
            "قفڵ ڤیدیۆ", "قفل ویدیو", "ڤیدیۆ قفڵ", "فیلم قفل",
            "قفل الفيديو",
        },
        "photo": {
            "lock photo", "lock photos", "قفل عکس", "قفڵ عەکس", "قفل وێنە",
            "قفڵ وێنە", "عکس قفل", "وێنە قفڵ",
            "قفل الصور",
        },
        "sticker": {
            "lock sticker", "lock stickers", "قفل استیکر", "قفڵ استیکەر",
            "قفل ملصق", "استیکر قفل", "استیکەر قفڵ",
            "قفل الملصقات",
        },
        "file": {
            "lock file", "lock files", "قفل فایل", "قفڵ فایل", "قفل فایلەکان",
            "فایل قفل", "فایل قفڵ",
            "قفل الملفات",
        },
        "all": {
            "lock all", "lock everything", "قفل همه", "قفڵ هەموو", "قفڵ گشتی",
            "قفل کلی", "هەموو قفل", "هەموو قفڵ", "گشتی قفڵ",
            "هەمووی قفڵ بکە", "قفل الكل", "قفل همه چیز",
        },
    }

    for action, phrases in lock_phrases.items():
        if normalized in phrases:
            return action
    return None


def detect_unlock_action(text: str) -> str | None:
    normalized = normalize_text(text)
    if not normalized:
        return None

    unlock_phrases = {
        "gif": {"unlock gif", "باز کردن گیف", "کردنەوەی گیف", "کردنەوەی گیفەکان", "فتح المتحركة"},
        "music": {"unlock music", "باز کردن موزیک", "کردنەوەی موزیک", "فتح الموسيقى"},
        "video": {"unlock video", "باز کردن فیلم", "کردنەوەی فیلم", "فتح الفيديو"},
        "photo": {"unlock photo", "باز کردن عکس", "کردنەوەی وێنە", "فتح الصور"},
        "sticker": {"unlock sticker", "باز کردن استیکر", "کردنەوەی استیکر", "فتح الملصقات"},
        "file": {"unlock file", "باز کردن فایل", "کردنەوەی فایل", "فتح الملفات"},
        "all": {"unlock all", "باز کردن همه", "کردنەوەی هەموو", "هەمووی بکەرەوە", "فتح الكل"},
    }

    for action, phrases in unlock_phrases.items():
        if normalized in phrases:
            return action
    return None


def permissions_for_locks(locked_actions: set[str]) -> ChatPermissions:
    permissions = {
        "can_send_messages": True,
        "can_send_audios": True,
        "can_send_documents": True,
        "can_send_photos": True,
        "can_send_videos": True,
        "can_send_video_notes": True,
        "can_send_voice_notes": True,
        "can_send_polls": True,
        "can_send_other_messages": True,
        "can_add_web_page_previews": True,
    }

    if "all" in locked_actions:
        for permission in permissions:
            permissions[permission] = False
        return ChatPermissions(**permissions)

    if "music" in locked_actions:
        permissions["can_send_audios"] = False
    if "video" in locked_actions:
        permissions["can_send_videos"] = False
        permissions["can_send_video_notes"] = False
    if "photo" in locked_actions:
        permissions["can_send_photos"] = False
    if "file" in locked_actions:
        permissions["can_send_documents"] = False
    if locked_actions & {"gif", "sticker"}:
        permissions["can_send_other_messages"] = False

    return ChatPermissions(**permissions)


def permissions_for_lock(action: str) -> ChatPermissions:
    return permissions_for_locks({action})


def is_private_chat(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.type == "private"


async def delete_start_response(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    if job is None or not isinstance(job.data, dict):
        return

    try:
        await context.bot.delete_message(
            chat_id=job.data["chat_id"],
            message_id=job.data["message_id"],
        )
    except Exception:
        logger.debug("Could not delete start response", exc_info=True)


async def is_admin_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat or not update.effective_user:
        return False

    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in {"administrator", "creator"}
    except Exception:
        return False


def create_application(settings: Settings) -> Application:
    gemini = GeminiClient(settings.gemini_api_key or "", settings.gemini_model)
    application = Application.builder().token(settings.bot_token).build()

    async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        error = getattr(context, "error", None)
        if error is not None:
            logger.error("Unhandled bot error for update %s", update, exc_info=error)
        else:
            logger.warning("Unhandled bot error without exception details for update %s", update)

        effective_message = getattr(update, "effective_message", None) if update else None
        if effective_message is not None:
            try:
                await effective_message.reply_text(
                    localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "error")
                )
            except Exception as reply_error:
                logger.debug("Could not send error response: %s", reply_error, exc_info=True)

    async def store_social_media_file(message: object, sent_message: object, source_path: Path, context: ContextTypes.DEFAULT_TYPE) -> None:
        SOCIAL_MEDIA_DIRECTORY.mkdir(parents=True, exist_ok=True)
        chat_id = getattr(getattr(message, "chat", None), "id", "unknown")
        message_id = getattr(sent_message, "message_id", "unknown")
        library_path = SOCIAL_MEDIA_DIRECTORY / f"{chat_id}_{message_id}{source_path.suffix}"
        try:
            shutil.copy2(source_path, library_path)
        except OSError:
            logger.warning("Could not save local social media file", exc_info=True)

    async def send_media_file(message: object, context: ContextTypes.DEFAULT_TYPE, path: Path, operation: str | None = None) -> object:
        suffix = path.suffix.lower()
        if operation in {"voice_mp3", "video_mp3"} or suffix in {".mp3", ".m4a", ".wav", ".flac"}:
            sent = await message.reply_audio(audio=str(path))
        elif operation in {"mp3_voice", "video_voice"} or suffix == ".ogg":
            sent = await message.reply_voice(voice=str(path))
        elif suffix in {".mp4", ".mkv", ".webm", ".mov", ".avi"}:
            sent = await message.reply_video(video=str(path), supports_streaming=True)
        else:
            raise RuntimeError("Unsupported media type")
        await store_social_media_file(message, sent, path, context)
        return sent

    async def download_telegram_media(message: object, context: ContextTypes.DEFAULT_TYPE, workdir: str) -> Path:
        media = next(
            (
                getattr(message, name, None)
                for name in ("audio", "voice", "video", "video_note", "document")
                if getattr(message, name, None) is not None
            ),
            None,
        )
        if media is None:
            raise RuntimeError("No supported media was attached")
        file = await context.bot.get_file(media.file_id)
        suffix = _media_suffix(message)
        path = Path(workdir) / f"input{suffix}"
        await file.download_to_drive(custom_path=str(path))
        return path

    async def handle_media_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, operation: str | None = None) -> None:
        message = update.message
        if message is None:
            return
        language = context.user_data.get(SELECTED_LANGUAGE_KEY)
        await message.reply_text(localized_message(language, "searching"))
        try:
            with tempfile.TemporaryDirectory(prefix="mrshaso_media_") as workdir:
                downloaded = await asyncio.to_thread(_download_url_sync, url, workdir)
                if operation:
                    downloaded = await asyncio.to_thread(_convert_media_sync, downloaded, operation, workdir)
                await send_media_file(message, context, downloaded, operation)
        except Exception as exc:
            logger.exception("Media URL processing failed for %s", url)
            await message.reply_text(localized_message(language, "download_error", error=exc))

    async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        if message is None:
            return
        mode = context.user_data.get(MENU_MODE_KEY, "main")
        if mode not in {"media:upload", "converter:mp3_voice", "converter:voice_mp3", "converter:video_mp3", "converter:video_voice"}:
            return

        try:
            with tempfile.TemporaryDirectory(prefix="mrshaso_media_") as workdir:
                source = await download_telegram_media(message, context, workdir)
                if mode == "media:upload":
                    await store_social_media_file(message, message, source, context)
                    await message.reply_text(localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "stored"))
                    return
                converted = await asyncio.to_thread(_convert_media_sync, source, mode.removeprefix("converter:"), workdir)
                await send_media_file(message, context, converted, mode.removeprefix("converter:"))
        except Exception as exc:
            logger.exception("Telegram media processing failed")
            await message.reply_text(localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "file_error", error=exc))

    async def send_social_media_gallery(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not SOCIAL_MEDIA_DIRECTORY.exists():
            return
        for path in sorted(SOCIAL_MEDIA_DIRECTORY.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file():
                continue
            media_kind = social_media_kind(path)
            try:
                if media_kind == "audio":
                    await context.bot.send_audio(chat_id=chat_id, audio=str(path))
                elif media_kind == "voice":
                    await context.bot.send_voice(chat_id=chat_id, voice=str(path))
                elif media_kind == "video":
                    await context.bot.send_video(chat_id=chat_id, video=str(path), supports_streaming=True)
            except Exception:
                logger.warning("Could not send social media library item %s", path, exc_info=True)

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not is_private_chat(update) or update.message is None:
            return

        response = await update.message.reply_text(BOT_PROFILE_NAME)
        if context.job_queue is not None:
            context.job_queue.run_once(
                delete_start_response,
                START_MESSAGE_DELETE_DELAY,
                data={"chat_id": response.chat_id, "message_id": response.message_id},
            )
        context.user_data[MENU_MODE_KEY] = "main"
        language = context.user_data.get(SELECTED_LANGUAGE_KEY, "kurdish")
        await update.message.reply_text(main_menu_text(language), reply_markup=build_main_menu(language))

    async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or not is_private_chat(update):
            return

        data = query.data or ""
        language = context.user_data.get(SELECTED_LANGUAGE_KEY, "kurdish")
        labels = MENU_TEXT[_menu_language(language)]
        if data == "menu:main":
            context.user_data[MENU_MODE_KEY] = "main"
            await query.answer()
            await query.edit_message_text(main_menu_text(language), reply_markup=build_main_menu(language))
            return
        if data == "menu:language":
            await query.answer()
            await query.edit_message_text(language_menu_text(language), reply_markup=build_language_menu(language))
            return
        if data == "menu:chat":
            context.user_data[MENU_MODE_KEY] = "chat"
            await query.answer()
            await query.edit_message_text(CHAT_WELCOME_TEXT[_menu_language(language)], reply_markup=InlineKeyboardMarkup([build_back_button(language)]))
            return
        if data == "menu:converter":
            context.user_data[MENU_MODE_KEY] = "converter"
            await query.answer()
            await query.edit_message_text(f"{labels['converter']}\n\n{labels['choose']}", reply_markup=build_converter_menu(language))
            return
        if data == "menu:media":
            context.user_data[MENU_MODE_KEY] = "media"
            await query.answer()
            await query.edit_message_text(f"{labels['media']}\n\n{labels['choose']}", reply_markup=build_media_menu(language))
            return
        if data == "menu:media:upload":
            context.user_data[MENU_MODE_KEY] = "media:upload"
            await query.answer()
            return
        if data.startswith("menu:converter:"):
            context.user_data[MENU_MODE_KEY] = data.removeprefix("menu:")
            await query.answer()
            await query.edit_message_text(labels["converter_prompt"], reply_markup=InlineKeyboardMarkup([build_back_button(language)]))
            return
        if data.startswith("menu:media:"):
            context.user_data[MENU_MODE_KEY] = data.removeprefix("menu:")
            await query.answer()
            await query.edit_message_text(labels["media_prompt"], reply_markup=InlineKeyboardMarkup([build_back_button(language)]))
            return
        await query.answer()

    async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or not is_private_chat(update):
            return

        language = (query.data or "").removeprefix("language:")
        language_labels = dict((value, label) for label, value in LANGUAGE_OPTIONS)
        if language not in language_labels:
            await query.answer()
            return

        context.user_data[SELECTED_LANGUAGE_KEY] = language
        context.user_data[MENU_MODE_KEY] = "main"
        await query.answer(MENU_TEXT[language]["language_chosen"])
        await query.edit_message_text(main_menu_text(language), reply_markup=build_main_menu(language))

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is not None:
            await update.message.reply_text(build_command_guide(context.user_data.get(SELECTED_LANGUAGE_KEY)))

    async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text(localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "usage_ask"))
            return

        question = " ".join(context.args)
        if is_private_chat(update) and is_identity_question(question):
            await update.message.reply_text(identity_response(question))
            return

        await update.message.reply_text(localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "thinking"))
        selected_language = context.user_data.get(SELECTED_LANGUAGE_KEY)
        system_instruction = build_response_instruction(question, selected_language)
        answer = gemini.ask(question, system_instruction=system_instruction)
        await update.message.reply_text(answer)

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        language = context.user_data.get(SELECTED_LANGUAGE_KEY)
        await update.message.reply_text(
            localized_message(language, "online") + "\n"
            f"Model: {settings.gemini_model}\n"
            "AI engine: Gemini\n"
            + localized_message(language, "language_support")
        )

    async def language_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not is_private_chat(update) or update.message is None:
            return
        await update.message.reply_text(
            language_menu_text(context.user_data.get(SELECTED_LANGUAGE_KEY, "kurdish")),
            reply_markup=build_language_menu(context.user_data.get(SELECTED_LANGUAGE_KEY, "kurdish")),
        )

    async def clear_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data.clear()
        context.chat_data.clear()
        await update.message.reply_text(localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "cleared"))

    async def track_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update is None:
            return
        message = update.effective_message
        chat = update.effective_chat
        if not message or not chat or chat.type not in {"group", "supergroup"}:
            return

        tracked_message_ids = context.chat_data.setdefault("tracked_message_ids", [])
        if message.message_id not in tracked_message_ids:
            tracked_message_ids.append(message.message_id)
            del tracked_message_ids[:-500]

    async def handle_group_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if not message or not chat or chat.type not in {"group", "supergroup"}:
            return

        try:
            bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        except Exception:
            logger.warning("Could not verify bot permissions in chat %s", chat.id, exc_info=True)
            return

        if bot_member.status not in {"administrator", "creator"} or (
            bot_member.status == "administrator"
            and not bot_member.can_delete_messages
        ):
            logger.warning("Bot needs Delete Messages permission in chat %s", chat.id)
            return

        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=message.message_id)
        except Exception:
            logger.warning(
                "Could not delete group member service message in chat %s",
                chat.id,
                exc_info=True,
            )
            return

        for member in message.new_chat_members or []:
            full_name = " ".join(
                part for part in (member.first_name, member.last_name) if part
            )
            member_name = f"@{member.username}" if member.username else full_name
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"🌟 بەخێربێیت {member_name}! خۆشحاڵین بە هاتنت بۆ گرووپەکەمان. 🌟",
            )

    async def handle_bot_promotion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_member_update = update.my_chat_member
        chat = update.effective_chat
        if not chat_member_update or not chat or chat.type not in {"group", "supergroup"}:
            return

        old_status = chat_member_update.old_chat_member.status
        new_status = chat_member_update.new_chat_member.status
        if new_status != "administrator" or old_status == "administrator":
            return

        promoter = chat_member_update.from_user
        promoter_name = (
            f"@{promoter.username}"
            if promoter.username
            else " ".join(
                part for part in (promoter.first_name, promoter.last_name) if part
            )
        )
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"✨ سوپاس بۆ {promoter_name}! ✨\n\n"
                "بە خۆشحاڵییەوە بۆتەکەت کرد بە ئەدمینی گرووپ. "
                "ئێستا ئامادەم بۆ یارمەتیدان و ڕێکخستنی گرووپەکەمان. 🤖🌟"
            ),
        )

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update is None or context is None:
            return
        if update.message is None or not update.message.text:
            return

        text = update.message.text.strip()
        if not text or text.startswith("/"):
            return

        chat = update.effective_chat
        is_group_chat = chat is not None and chat.type in {"group", "supergroup"}
        if is_group_chat and not await is_admin_user(update, context):
            return
        mode = context.user_data.get(MENU_MODE_KEY, "main")
        url = extract_media_url(text)
        if not is_group_chat and url and mode.startswith("media:") and not media_url_matches_mode(url, mode):
            platform = detect_media_platform(url)
            await update.message.reply_text(
                localized_message(
                    context.user_data.get(SELECTED_LANGUAGE_KEY),
                    "wrong_link",
                    platform=platform or "this",
                )
            )
            return
        if not is_group_chat and url and (mode.startswith("media:") or mode.startswith("converter:")):
            operation = mode.removeprefix("converter:") if mode.startswith("converter:") else None
            await handle_media_url(update, context, url, operation)
            return
        if not is_group_chat and is_identity_question(text):
            await update.message.reply_text(identity_response(text))
            return
        if not is_group_chat and context.user_data.get(MENU_MODE_KEY, "main") != "chat":
            language = context.user_data.get(SELECTED_LANGUAGE_KEY, "kurdish")
            await update.message.reply_text(main_menu_text(language), reply_markup=build_main_menu(language))
            return
        reply_target = update.message.reply_to_message

        if is_group_chat and update.effective_user and update.effective_user.username:
            known_users = context.chat_data.setdefault("known_users", {})
            known_users[update.effective_user.username.lower()] = update.effective_user

        if is_group_chat:
            if is_clear_chat_command(text):
                if not await is_admin_user(update, context):
                    return
                if chat is None or update.message.message_id is None:
                    return

                message_ids = list(context.chat_data.get("tracked_message_ids", []))
                requested_count = parse_clear_chat_count(text) or 500
                command_message_id = update.message.message_id
                previous_message_ids = [
                    message_id for message_id in message_ids if message_id != command_message_id
                ]
                for message_id in previous_message_ids[-requested_count:]:
                    if message_id is None:
                        continue
                    try:
                        await context.bot.delete_message(chat_id=chat.id, message_id=message_id)
                    except Exception:
                        logger.debug("Could not delete tracked message %s", message_id, exc_info=True)

                try:
                    await context.bot.delete_message(
                        chat_id=chat.id,
                        message_id=command_message_id,
                    )
                except Exception:
                    logger.debug("Could not delete clear command message", exc_info=True)
                context.chat_data.clear()
                return

            lock_action = detect_lock_action(text)
            unlock_action = detect_unlock_action(text)
            if lock_action or unlock_action:
                if not await is_admin_user(update, context):
                    return
                try:
                    locked_actions = set(context.chat_data.get("locked_media", []))
                    if lock_action == "all":
                        locked_actions = {"all"}
                    elif lock_action:
                        locked_actions.discard("all")
                        locked_actions.add(lock_action)
                    elif unlock_action == "all":
                        locked_actions.clear()
                    elif unlock_action:
                        if "all" in locked_actions:
                            locked_actions = {"music", "video", "photo", "sticker", "file", "gif"}
                        locked_actions.discard(unlock_action)

                    context.chat_data["locked_media"] = list(locked_actions)
                    await context.bot.set_chat_permissions(
                        chat_id=chat.id,
                        permissions=permissions_for_locks(locked_actions),
                    )
                    action_label = lock_action or unlock_action
                    status = "locked" if lock_action else "unlocked"
                    language = context.user_data.get(SELECTED_LANGUAGE_KEY)
                    message_key = "locked" if lock_action else "unlocked"
                    await update.message.reply_text(localized_message(language, message_key, action_label=action_label))
                except Exception as exc:
                    action_label = lock_action or unlock_action
                    logger.exception("Failed to update %s in chat: %s", action_label, exc)
                    await update.message.reply_text(localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "failed_restriction"))
                return

            moderation_action = detect_moderation_action(text)
            unmute_action = detect_unmute_action(text)
            if moderation_action or unmute_action:
                if not await is_admin_user(update, context):
                    return

                target_user = reply_target.from_user if reply_target else None
                target_username = extract_target_username(text)
                if not target_user and target_username:
                    target_user = context.chat_data.get("known_users", {}).get(target_username)
                if not target_user:
                    return

                try:
                    if unmute_action:
                        await context.bot.restrict_chat_member(
                            chat_id=chat.id,
                            user_id=target_user.id,
                            permissions=permissions_for_locks(
                                set(context.chat_data.get("locked_media", []))
                            ),
                            until_date=None,
                        )
                        await update.message.reply_text(localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "unmuted", name=target_user.first_name))
                    elif moderation_action == "mute":
                        await context.bot.restrict_chat_member(
                            chat_id=chat.id,
                            user_id=target_user.id,
                            permissions=ChatPermissions(
                                can_send_messages=False,
                                can_send_media_messages=False,
                                can_send_polls=False,
                                can_send_other_messages=False,
                                can_add_web_page_previews=False,
                            ),
                            until_date=None,
                        )
                        await update.message.reply_text(localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "muted", name=target_user.first_name))
                    else:
                        await context.bot.ban_chat_member(
                            chat_id=chat.id,
                            user_id=target_user.id,
                            until_date=None,
                        )
                        await update.message.reply_text(localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "banned", name=target_user.first_name))
                except Exception as exc:
                    logger.exception("Failed to apply group moderation command: %s", exc)
                    await update.message.reply_text(localized_message(context.user_data.get(SELECTED_LANGUAGE_KEY), "failed_moderation"))
                return

            if should_answer_identity(update, context.bot.id):
                await update.message.reply_text(identity_response(text))
                return

            if reply_target and is_reply_to_bot_message(reply_target, context.bot.id):
                chat_history = context.chat_data.setdefault("history", [])
                chat_history.append({"role": "user", "content": text})

                recent_history = chat_history[-12:]
                prompt = "\n".join(f"User: {item['content']}" for item in recent_history)

                selected_language = context.user_data.get(SELECTED_LANGUAGE_KEY)
                system_instruction = build_response_instruction(text, selected_language)
                answer = gemini.ask(prompt, system_instruction=system_instruction)
                chat_history.append({"role": "assistant", "content": answer})
                await update.message.reply_text(answer)
                return

            greeting_language = detect_greeting_language(text)
            if greeting_language:
                await update.message.reply_text(greeting_response(greeting_language))
                return

            return

        if should_answer_identity(update, context.bot.id):
            await update.message.reply_text(identity_response(text))
            return

        greeting_language = detect_greeting_language(text)
        if greeting_language:
            await update.message.reply_text(greeting_response(greeting_language))
            return

        if is_command_guide_request(text):
            await update.message.reply_text(build_command_guide(context.user_data.get(SELECTED_LANGUAGE_KEY)))
            return

        chat_history = context.chat_data.setdefault("history", [])
        chat_history.append({"role": "user", "content": text})

        recent_history = chat_history[-12:]
        prompt = "\n".join(f"User: {item['content']}" for item in recent_history)

        selected_language = context.user_data.get(SELECTED_LANGUAGE_KEY)
        system_instruction = build_response_instruction(text, selected_language)
        answer = gemini.ask(prompt, system_instruction=system_instruction)

        chat_history.append({"role": "assistant", "content": answer})
        await update.message.reply_text(answer)

    application.add_error_handler(handle_error)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("language", language_info))
    application.add_handler(CommandHandler("clear", clear_context))
    application.add_handler(
        CallbackQueryHandler(handle_menu_callback, pattern=r"^menu:")
    )
    application.add_handler(
        CallbackQueryHandler(select_language, pattern=r"^language:")
    )
    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
            handle_group_member_update,
        ),
        group=-2,
    )
    application.add_handler(
        ChatMemberHandler(handle_bot_promotion, ChatMemberHandler.MY_CHAT_MEMBER),
        group=-2,
    )
    application.add_handler(MessageHandler(filters.ALL, track_group_message), group=-1)
    application.add_handler(
        MessageHandler(
            filters.AUDIO | filters.VOICE | filters.VIDEO | filters.VIDEO_NOTE | filters.Document.ALL,
            handle_media_message,
        )
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return application
