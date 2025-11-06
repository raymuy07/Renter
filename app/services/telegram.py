from __future__ import annotations

import logging
import threading
import time
from typing import Iterable, Optional

from telegram import Bot, Update
from telegram.error import TelegramError

from ..config import get_settings
from ..db import session_scope
from ..models import User


logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """Escape Telegram MarkdownV2 reserved characters."""

    if not text:
        return text

    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


class TelegramService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.bot = Bot(token=self.settings.telegram_bot_token)
        self.bot_username: Optional[str] = self.settings.telegram_bot_username
        self.update_offset: Optional[int] = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return

        try:
            info = self.bot.get_me()
            self.bot_username = info.username or self.bot_username
            if self.bot_username is None:
                raise RuntimeError("Telegram bot username not available. Set TELEGRAM_BOT_USERNAME in env.")

            updates = self.bot.get_updates(timeout=1)
            if updates:
                self.update_offset = updates[-1].update_id + 1
            else:
                self.update_offset = 0

            self._initialized = True
            logger.info("Telegram bot initialized as @%s", self.bot_username)
        except TelegramError as exc:
            logger.error("Failed to initialize Telegram bot: %s", exc)
            raise

    def generate_deep_link(self, user: User) -> str:
        self.initialize()
        if not self.bot_username:
            raise RuntimeError("Telegram bot username missing")
        return f"https://t.me/{self.bot_username}?start={user.telegram_start_token}"

    def send_message(self, chat_id: str | int, text: str) -> None:
        try:
            self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30,
            )
        except TelegramError as exc:
            logger.warning("Markdown send failed, retry without formatting: %s", exc)
            try:
                self.bot.send_message(
                    chat_id=chat_id,
                    text=text.replace("\\", ""),
                    disable_web_page_preview=True,
                )
            except TelegramError as final_exc:
                logger.error("Failed to send Telegram message: %s", final_exc)

    def notify_listing_updates(self, chat_id: str, messages: Iterable[str]) -> None:
        for message in messages:
            self.send_message(chat_id, message)
            time.sleep(1.5)

    def poll_for_updates(self) -> None:
        self.initialize()
        try:
            updates: list[Update] = self.bot.get_updates(offset=self.update_offset, timeout=10)
        except TelegramError as exc:
            logger.error("Error polling Telegram updates: %s", exc)
            time.sleep(5)
            return

        if not updates:
            return

        for update in updates:
            self.update_offset = update.update_id + 1
            message = update.message or update.edited_message
            if not message:
                continue

            text = message.text or ""
            if not text.startswith("/start"):
                continue

            token = None
            parts = text.split(maxsplit=1)
            if len(parts) == 2:
                token = parts[1].strip()

            if not token:
                continue

            chat_id = str(message.chat.id)
            with session_scope() as session:
                user = session.query(User).filter(User.telegram_start_token == token).one_or_none()
                if not user:
                    logger.warning("Received /start with unknown token: %s", token)
                    continue

                user.telegram_chat_id = chat_id
                session.add(user)

            try:
                self.send_message(chat_id, "\u2705 Registered successfully. We'll notify you about new listings!")
            except TelegramError:
                logger.exception("Failed to confirm Telegram registration for user %s", token)


class TelegramUpdatePoller(threading.Thread):
    def __init__(self, service: TelegramService, interval_seconds: int = 5) -> None:
        super().__init__(daemon=True)
        self.service = service
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()

    def run(self) -> None:
        logger.info("Starting Telegram update poller")
        while not self._stop_event.is_set():
            try:
                self.service.poll_for_updates()
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected error in Telegram poller")

            self._stop_event.wait(self.interval_seconds)

        logger.info("Telegram update poller stopped")

    def stop(self) -> None:
        self._stop_event.set()

