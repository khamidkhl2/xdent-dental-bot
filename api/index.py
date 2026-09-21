from __future__ import annotations

import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Ensure root directory is on Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram.types import Update
import main


class handler(BaseHTTPRequestHandler):
    """
    Vercel Serverless Function entrypoint for Telegram webhook updates.
    """

    def do_POST(self) -> None:
        """Handle incoming webhook update from Telegram."""
        if not main.bot:
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({
                    "ok": False,
                    "error": "BOT_TOKEN is not configured in Vercel Environment Variables"
                }).encode("utf-8")
            )
            return

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode("utf-8"))
            update = Update.model_validate(body, context={"bot": main.bot})
            asyncio.run(main.dp.feed_update(bot=main.bot, update=update))
        except Exception as exc:
            print(f"Error processing Telegram update: {exc}", file=sys.stderr)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def do_GET(self) -> None:
        """Health check endpoint."""
        token_status = "configured" if main.bot else "MISSING (please add BOT_TOKEN in Vercel Environment Variables)"
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        msg = f"Dr. Shoxruz XDENT Telegram Bot Webhook is active.\nBot token status: {token_status}\n"
        self.wfile.write(msg.encode("utf-8"))
