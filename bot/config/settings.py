import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_bot_token():
    raw = os.getenv("DISCORD_BOT_TOKEN", os.getenv("BOT_TOKEN", ""))
    if not raw or raw == "YOUR_DISCORD_BOT_TOKEN_HERE" or len(raw) < 10:
        try:
            from bot.database.db import db
            db_tok = db.get_guild_setting(0, "bot_token")
            if db_tok and len(db_tok) > 10:
                raw = db_tok
        except Exception:
            pass
    return raw.strip().strip('"').strip("'").strip() if raw else ""

class Config:
    @classmethod
    def get_token(cls):
        return get_bot_token()

    BOT_TOKEN = get_bot_token()
    GUILD_ID = int(os.getenv("GUILD_ID", 0)) if os.getenv("GUILD_ID") and os.getenv("GUILD_ID").isdigit() else None
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ar") # 'ar' or 'en'
    MAX_OPEN_TICKETS_PER_USER = int(os.getenv("MAX_OPEN_TICKETS_PER_USER", 1))
    COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", 10))
    HTML_TRANSCRIPT_ENABLED = os.getenv("HTML_TRANSCRIPT_ENABLED", "true").lower() == "true"
    BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "1406547827865288786"))
