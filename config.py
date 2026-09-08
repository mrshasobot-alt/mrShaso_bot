from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass
class Settings:
    bot_token: str
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            api_id=_as_int(os.getenv("TELEGRAM_API_ID")),
            api_hash=os.getenv("TELEGRAM_API_HASH", "").strip() or None,
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip() or None,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
        )

    def validate(self) -> None:
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is missing or empty. Create a .env file from .env.example.")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is missing or empty. Set it in your .env file.")

    def summary(self) -> str:
        return (
            f"Bot token: {self.bot_token[:12]}...\n"
            f"API ID: {self.api_id}\n"
            f"API hash set: {bool(self.api_hash)}\n"
            f"Gemini model: {self.gemini_model}\n"
            f"Gemini key set: {bool(self.gemini_api_key)}"
        )


def _as_int(value: Optional[str]) -> Optional[int]:
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None
