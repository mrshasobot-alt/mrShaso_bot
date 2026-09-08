from __future__ import annotations

import argparse
from app.config import Settings
from app.bot import create_application


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the MrShaso AI Telegram bot.")
    parser.add_argument("--check", action="store_true", help="Validate configuration without starting the bot.")
    args = parser.parse_args()

    settings = Settings.from_env()
    settings.validate()

    if args.check:
        print("Configuration OK")
        print(settings.summary())
        return 0

    application = create_application(settings)
    print(f"Starting MrShaso AI bot for chat ID: {settings.bot_token[:10]}...")
    application.run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
