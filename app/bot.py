from __future__ import annotations

import logging
import re

from telegram import ChatPermissions, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import Settings
from app.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


def normalize_text(value: str) -> str:
    if not value:
        return ""
    text = value.lower().strip()
    text = re.sub(r"[\u200c\u200d\s\t\n]+", " ", text)
    text = re.sub(r"[^\w\s\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]", " ", text)
    return " ".join(text.split())


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


def is_clear_chat_command(text: str) -> bool:
    normalized = normalize_text(text)
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

def build_command_guide() -> str:
    return (
        "ڕێنمایی فەرمانەکانی بۆت:\n\n"
        "لە چاتی تایبەت:\n"
        "• /start - دەستپێکردن\n"
        "• /help - پیشاندانی ئەم ڕێنماییە\n"
        "• /ask <پرسیار> - پرسیارکردن لە Gemini\n"
        "• /status - دۆخی بۆت\n"
        "• /language - زمانە پشتگیریکراوەکان\n"
        "• /clear - پاککردنەوەی context ـی گفتوگۆ\n\n"
        "لە گرووپ، تەنها Admin/Manager:\n"
        "• قفڵکردن: قفل گیف، قفل موزیک، قفل فیلم، قفل عکس، قفل فایل، قفل همه\n"
        "• کردنەوەی قفڵ: باز کردن گیف، باز کردن موزیک، باز کردن فیلم، باز کردن عکس، باز کردن فایل، باز کردن همه\n"
        "• پاکسازی: پاکسازی 50، clean 100، حذف 50\n"
        "• بێدەنگکردن: سکوت، صامت، mute، بێدەنگی (تەنها بە Reply یان @username)\n"
        "• ئازادکردن: لغو سکوت، رفع الكتم، unmute (تەنها بە Reply یان @username)\n"
        "• سزا/ban: بن، ریمو، ban، kick (تەنها بە Reply یان @username)\n\n"
        "فەرمانەکانی قفڵ، کردنەوەی قفڵ و پاکسازی بە ڕاستەوخۆ لە گرووپ کار دەکەن.\n"
        "بۆ کارکردنی فەرمانەکانی گرووپ، بۆت دەبێت لە گرووپدا Admin بێت و دەسەڵاتی سڕینەوە و گۆڕینی permissions ـی هەبێت."
    )

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
                    "⚠️ Something went wrong. Please try again in a moment."
                )
            except Exception as reply_error:
                logger.debug("Could not send error response: %s", reply_error, exc_info=True)

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update is None or update.message is None:
            return

        user = update.effective_user
        first_name = user.first_name if user and user.first_name else "friend"
        chat = update.effective_chat
        if chat is not None and chat.type == "private":
            welcome_message = (
                f"سڵاو {first_name} گیان! بەخێربێیت بۆ بۆتی تایبەتی من 👋✨\n\n"
                "من لێرەم بۆ ئەوەی لە هەموو پرسیارێک یان کارێکدا یارمەتیت بدەم. "
                "دەتوانیت ڕاستەوخۆ پرسیار یان داواکاریی خۆت بنێریت!"
            )
        else:
            welcome_message = f"سڵاو {first_name}، خێربێی 👋"

        await update.message.reply_text(welcome_message)

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is not None:
            await update.message.reply_text(build_command_guide())

    async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Usage: /ask <your question>")
            return

        question = " ".join(context.args)
        await update.message.reply_text("Thinking...")
        answer = gemini.ask(question)
        await update.message.reply_text(answer)

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "✅ Bot is online\n"
            f"Model: {settings.gemini_model}\n"
            "AI engine: Gemini\n"
            "Language support: Arabic, Kurdish, Persian, English, and more"
        )

    async def language_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Supported languages include:\n"
            "- Arabic\n"
            "- Kurdish\n"
            "- Persian\n"
            "- English\n"
            "- and many more languages depending on the prompt"
        )

    async def clear_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data.clear()
        context.chat_data.clear()
        await update.message.reply_text("✅ Conversation context cleared.")

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
                    await update.message.reply_text(f"🔒 {action_label} {status}.")
                except Exception as exc:
                    action_label = lock_action or unlock_action
                    logger.exception("Failed to update %s in chat: %s", action_label, exc)
                    await update.message.reply_text("⚠️ Failed to update that restriction.")
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
                        await update.message.reply_text(f"🔊 User {target_user.first_name} unmuted.")
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
                        await update.message.reply_text(f"🔇 User {target_user.first_name} muted.")
                    else:
                        await context.bot.ban_chat_member(
                            chat_id=chat.id,
                            user_id=target_user.id,
                            until_date=None,
                        )
                        await update.message.reply_text(f"⛔ User {target_user.first_name} banned.")
                except Exception as exc:
                    logger.exception("Failed to apply group moderation command: %s", exc)
                    await update.message.reply_text("⚠️ Failed to apply that moderation command.")
                return

            if reply_target and is_reply_to_bot_message(reply_target, context.bot.id):
                chat_history = context.chat_data.setdefault("history", [])
                chat_history.append({"role": "user", "content": text})

                recent_history = chat_history[-12:]
                prompt = "\n".join(f"User: {item['content']}" for item in recent_history)
                detected_language = GeminiClient.detect_language(text)

                system_instruction = GeminiClient.build_system_prompt(detected_language)
                answer = gemini.ask(prompt, system_instruction=system_instruction)
                chat_history.append({"role": "assistant", "content": answer})
                await update.message.reply_text(answer)
                return

            greeting_language = detect_greeting_language(text)
            if greeting_language:
                await update.message.reply_text(greeting_response(greeting_language))
                return

            return

        greeting_language = detect_greeting_language(text)
        if greeting_language:
            await update.message.reply_text(greeting_response(greeting_language))
            return

        if is_command_guide_request(text):
            await update.message.reply_text(build_command_guide())
            return

        chat_history = context.chat_data.setdefault("history", [])
        chat_history.append({"role": "user", "content": text})

        recent_history = chat_history[-12:]
        prompt = "\n".join(f"User: {item['content']}" for item in recent_history)
        detected_language = GeminiClient.detect_language(text)

        system_instruction = GeminiClient.build_system_prompt(detected_language)
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
    application.add_handler(MessageHandler(filters.ALL, track_group_message), group=-1)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return application
