# MrShaso AI Bot

A professional Telegram AI bot built with Python, Telegram Bot API, and Gemini.

## Features

- /start welcome screen
- /help command list
- /ask <question> direct AI prompt
- /status checks bot status
- /clear resets conversation context
- Natural-language conversation with Gemini for normal messages
- Optional Telegram API credentials support for advanced client features

## Setup

1. Copy `.env.example` to `.env`.
2. Fill in your Telegram bot token and Gemini API key.
3. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Run the bot:

   ```bash
   python main.py
   ```

5. To validate configuration only:

   ```bash
   python main.py --check
   ```

## Notes

- The bot uses Gemini as the AI engine for chat responses.
- Telegram API ID and hash are stored in `.env` and can be used for future account features.
