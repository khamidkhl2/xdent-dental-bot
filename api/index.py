import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Ensure root directory is on Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram.types import Update
from main import bot, dp


class handler(BaseHTTPRequestHandler):
    """
    Vercel Serverless Function entrypoint for Telegram webhook updates.
    """

    def do_POST(self) -> None:
        """Handle incoming webhook update from Telegram."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode("utf-8"))
            update = Update.model_validate(body, context={"bot": bot})
            asyncio.run(dp.feed_update(bot=bot, update=update))
        except Exception as exc:
            print(f"Error processing Telegram update: {exc}", file=sys.stderr)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def do_GET(self) -> None:
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Dr. Shoxruz XDENT Telegram Bot Webhook is active.")
