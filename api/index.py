import asyncio
import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler

# Ensure root directory is on Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_startup_error = None
try:
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.types import Update
    import main
except Exception as exc:
    _startup_error = traceback.format_exc()


async def process_telegram_update(body: dict) -> None:
    """
    Process a single Telegram update with an isolated Bot session.
    Prevents 'Event loop is closed' errors on serverless lambdas.
    """
    token = main.BOT_TOKEN
    if not token or ":" not in token:
        raise ValueError("BOT_TOKEN is not configured or invalid")

    if main.HAS_DEFAULT_PROPERTIES:
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    else:
        bot = Bot(token=token, parse_mode=ParseMode.HTML)

    try:
        update = Update.model_validate(body, context={"bot": bot})
        await main.dp.feed_update(bot=bot, update=update)
    finally:
        await bot.session.close()


class handler(BaseHTTPRequestHandler):
    """
    Vercel Serverless Function entrypoint for Telegram webhook updates.
    """

    def do_POST(self) -> None:
        """Handle incoming webhook update from Telegram."""
        if _startup_error:
            self.send_response(500)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Startup Error:\n{_startup_error}".encode("utf-8"))
            return

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode("utf-8"))
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(process_telegram_update(body))
            finally:
                loop.close()
        except Exception as exc:
            print(f"Error processing Telegram update: {exc}", file=sys.stderr)
            traceback.print_exc()

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def do_GET(self) -> None:
        """Health check endpoint."""
        if _startup_error:
            self.send_response(500)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Startup Error:\n{_startup_error}".encode("utf-8"))
            return

        token_status = (
            "configured"
            if main.BOT_TOKEN
            else "MISSING (please add BOT_TOKEN in Vercel Environment Variables)"
        )
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        msg = (
            f"Dr. Shoxruz XDENT Telegram Bot Webhook is active.\n"
            f"Bot token status: {token_status}\n"
        )
        self.wfile.write(msg.encode("utf-8"))
