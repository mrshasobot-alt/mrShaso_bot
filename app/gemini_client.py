from __future__ import annotations

import re
from typing import Any, Optional


class GeminiClient:
    SUPPORTED_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.6-flash",
        "gemini-2.0-flash",
    ]

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash") -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")

        self.model_name = self._resolve_model_name(model_name)
        self.client = None
        self.model = None
        self.chat = None

        self._initialize_client(api_key)

    @classmethod
    def get_fallback_models(cls, requested_model: str) -> list[str]:
        preferred = [requested_model.strip()] if requested_model and requested_model.strip() else []
        ordered = preferred + [m for m in cls.SUPPORTED_MODELS if m not in preferred]
        return ordered

    @classmethod
    def _resolve_model_name(cls, model_name: str) -> str:
        cleaned = (model_name or "").strip() or "gemini-2.5-flash"
        if cleaned in cls.SUPPORTED_MODELS:
            return cleaned
        if "gemini-" in cleaned:
            return cleaned
        return "gemini-2.5-flash"

    def _initialize_client(self, api_key: str) -> None:
        try:
            from google import genai as google_genai

            if hasattr(google_genai, "Client"):
                self.client = google_genai.Client(api_key=api_key)
                self.model = self.model_name
                self.chat = self.client.chats.create(model=self.model_name)
                return
        except Exception:
            pass

        try:
            import google.generativeai as legacy_genai

            legacy_genai.configure(api_key=api_key)
            self.model = legacy_genai.GenerativeModel(self.model_name)
            return
        except Exception as exc:
            raise RuntimeError("Unable to initialize Gemini client. Check the Gemini API key and package install.") from exc

    @staticmethod
    def detect_language(text: str) -> str:
        cleaned = (text or "").strip().lower()
        if not cleaned:
            return "multilingual"

        if any(ch in cleaned for ch in ["ڕ", "ڵ", "ۆ", "ێ", "ە", "ئ", "ڤ"]):
            return "kurdish"

        if any(word in cleaned for word in ["سلام", "خوب", "چطور", "درود", "پرسش", "فارسی", "دستورات"]):
            return "persian"

        if any(word in cleaned for word in ["مرحبا", "أهلا", "اهلا", "كيف", "العربية", "شكرا"]):
            return "arabic"

        if re.search(r"[\u0600-\u06FF]", cleaned):
            return "arabic"

        if re.search(r"[a-z]", cleaned):
            return "english"

        return "multilingual"

    @staticmethod
    def detect_kurdish_dialect(text: str) -> str:
        """Return the most likely Kurdish variety without claiming certainty."""
        cleaned = (text or "").strip().lower()
        if not cleaned:
            return "unknown"

        sorani_markers = ("ە", "ۆ", "ێ", "ڵ", "ڕ", "بۆ", "چی", "چۆن", "دەکات")
        badini_markers = ("ئەڤ", "ئێ", "ێک", "هەیە", "دکەم", "دکەی", "خۆ")
        if any(marker in cleaned for marker in ("ئەڤ", "دکەم", "دکەی")):
            return "badini"
        sorani_score = sum(cleaned.count(marker) for marker in sorani_markers)
        badini_score = sum(cleaned.count(marker) for marker in badini_markers)
        if sorani_score > badini_score and sorani_score:
            return "sorani"
        if badini_score > sorani_score and badini_score:
            return "badini"
        return "kurdish-general"

    @classmethod
    def detect_language_profile(cls, text: str) -> str:
        language = cls.detect_language(text)
        if language == "kurdish":
            return f"kurdish-{cls.detect_kurdish_dialect(text)}"
        return language

    @staticmethod
    def build_system_prompt(language: str) -> str:
        lang = (language or "multilingual").lower()
        if lang in {"kurdish", "sorani", "badini", "kurdish-sorani", "kurdish-badini", "kurdish-kurdish-general"}:
            dialect = {
                "kurdish-sorani": "Sorani",
                "kurdish-badini": "Badini/Kurmanji",
                "kurdish-kurdish-general": "the user's Kurdish variety",
            }.get(lang, "the user's Kurdish dialect")
            language_hint = f"Kurdish, specifically {dialect}"
        elif lang == "arabic":
            language_hint = "عربي (Arabic)"
        elif lang == "persian":
            language_hint = "فارسی (Persian)"
        elif lang == "english":
            language_hint = "English"
        else:
            language_hint = "بە زمانەکەی بەکارهێنەر (user language)"

        return (
            "You are MrShaso AI, a highly capable, helpful, and professional multilingual assistant. "
            f"Answer mainly in {language_hint}, and switch naturally to the user's language when needed. "
            "Identify the user's intent before answering and ask one concise clarification question only when the request is genuinely ambiguous. "
            "Preserve the user's dialect, register, and script whenever possible. For Kurdish, distinguish Sorani from Badini/Kurmanji and do not replace one with another without a reason. "
            "For Kurdish, Persian, and Arabic, use correct spelling, grammar, punctuation, and natural word order. "
            "Do not mix languages or dialects inside a sentence unless the user asks for translation or uses necessary technical names. "
            "Provide clear, accurate, respectful, and structured answers. "
            "Avoid harmful, illegal, or unsafe content. "
            "Be concise but detailed enough to be useful. "
            "Use Markdown formatting when it improves clarity."
        )

    def ask(self, prompt: str, *, system_instruction: Optional[str] = None) -> str:
        if not prompt or not prompt.strip():
            return "Please provide a question or message to continue."

        request = prompt.strip()
        language = self.detect_language(request)
        system_prompt = system_instruction or self.build_system_prompt(language)

        try:
            if self.client is not None:
                from google.genai import types

                last_error = None
                for model_name in self.get_fallback_models(self.model_name):
                    try:
                        config = types.GenerateContentConfig(system_instruction=system_prompt)
                        chat = self.client.chats.create(model=model_name, config=config)
                        response = chat.send_message(request)
                        self.model_name = model_name
                        self.chat = chat
                        return self._extract_text(response)
                    except Exception as exc:  # pragma: no cover - runtime API fallback
                        last_error = exc
                        continue

                if last_error is not None:
                    raise last_error

            if self.model is not None:
                response = self.model.generate_content(f"{system_prompt}\n\n{request}")
                return self._extract_text(response)

            return "The AI service is temporarily unavailable. Please try again in a moment."
        except Exception:
            return "The AI service is temporarily unavailable. Please try again in a moment."

    @staticmethod
    def _extract_text(response: Any) -> str:
        try:
            if hasattr(response, "text") and response.text:
                return response.text
            if hasattr(response, "candidates") and response.candidates:
                first = response.candidates[0]
                if hasattr(first, "content") and hasattr(first.content, "parts"):
                    return "".join(part.text for part in first.content.parts if hasattr(part, "text"))
            if hasattr(response, "output") and response.output:
                return str(response.output)
            return str(response)
        except Exception:
            return str(response)
