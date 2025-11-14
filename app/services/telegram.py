from __future__ import annotations

import asyncio
import base64
import io
import logging
import threading
import time
from typing import Iterable, Optional

import qrcode
from telegram import Bot, Update
from telegram.error import TelegramError

from ..config import get_settings
from ..db import session_scope
from ..models import SearchPreference, User


logger = logging.getLogger(__name__)

# Thread-local storage for event loops
_thread_local = threading.local()


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
        self.on_user_registered = None  # Callback for when user completes registration
        self.monitor_manager = None  # Reference to MonitorManager for stopping monitors

    def _get_event_loop(self):
        """Get or create a persistent event loop for the current thread."""
        # Check if this thread has a loop
        if not hasattr(_thread_local, 'loop') or _thread_local.loop is None or _thread_local.loop.is_closed():
            # Create a new event loop for this thread
            _thread_local.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_thread_local.loop)
        return _thread_local.loop

    def _run_async(self, coro):
        """Run async coroutine safely in current thread."""
        loop = self._get_event_loop()
        return loop.run_until_complete(coro)

    def initialize(self) -> None:
        if self._initialized:
            return

        try:
            info = self._run_async(self.bot.get_me())
            self.bot_username = info.username or self.bot_username
            if self.bot_username is None:
                raise RuntimeError("Telegram bot username not available. Set TELEGRAM_BOT_USERNAME in env.")

            updates = self._run_async(self.bot.get_updates(timeout=1))
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
    
    def generate_qr_code(self, deep_link: str) -> str:
        """Generate QR code for deep link and return as base64 encoded PNG."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(deep_link)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{img_base64}"

    def send_message(self, chat_id: str | int, text: str) -> None:
        try:
            self._run_async(
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
            )
        except TelegramError as exc:
            logger.warning("Markdown send failed, retry without formatting: %s", exc)
            try:
                self._run_async(
                    self.bot.send_message(
                        chat_id=chat_id,
                        text=text.replace("\\", ""),
                        disable_web_page_preview=True,
                    )
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
            updates: list[Update] = self._run_async(self.bot.get_updates(offset=self.update_offset, timeout=10))
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
            chat_id = str(message.chat.id)
            
            # Handle /start command
            if text.startswith("/start"):
                token = None
                parts = text.split(maxsplit=1)
                if len(parts) == 2:
                    token = parts[1].strip()

                if not token:
                    continue

                user_id = None
                with session_scope() as session:
                    user = session.query(User).filter(User.telegram_start_token == token).one_or_none()
                    if not user:
                        logger.warning("Received /start with unknown token: %s", token)
                        continue

                    user.telegram_chat_id = chat_id
                    session.add(user)
                    user_id = user.id

                try:
                    self.send_message(chat_id, "\u2705 Registered successfully\\! We'll notify you about new listings\\!")
                except TelegramError:
                    logger.exception("Failed to confirm Telegram registration for user %s", token)
                
                # Start monitoring for all active preferences for this user
                if self.on_user_registered and user_id:
                    self.on_user_registered(user_id)
                continue
            
            # Handle /delete command
            if text.strip() == "/delete":
                self._handle_delete_command(chat_id)
                continue
            
            # Handle /list command
            if text.strip() == "/list":
                self._handle_list_command(chat_id)
                continue
    
    def _handle_delete_command(self, chat_id: str) -> None:
        """Handle /delete command to deactivate user's active search preferences."""
        preference_ids_to_stop = []
        with session_scope() as session:
            user = session.query(User).filter(User.telegram_chat_id == chat_id).one_or_none()
            if not user:
                try:
                    self.send_message(chat_id, "\u274c You are not registered\\. Please register first\\.")
                except TelegramError:
                    logger.exception("Failed to send error message to chat %s", chat_id)
                return
            
            # Find all active preferences
            active_prefs = session.query(SearchPreference).filter(
                SearchPreference.user_id == user.id,
                SearchPreference.active.is_(True)
            ).all()
            
            if not active_prefs:
                try:
                    self.send_message(chat_id, "\U0001f937 You don't have any active searches to delete\\.")
                except TelegramError:
                    logger.exception("Failed to send message to chat %s", chat_id)
                return
            
            # Deactivate all active preferences
            deleted_labels = []
            for pref in active_prefs:
                pref.active = False
                deleted_labels.append(pref.label or "Yad2 search")
                preference_ids_to_stop.append(pref.id)
            
            session.commit()
        
        # Stop monitoring for deleted preferences
        if self.monitor_manager:
            for pref_id in preference_ids_to_stop:
                try:
                    self.monitor_manager.stop_monitor(pref_id)
                    logger.info("Stopped monitoring for preference %s", pref_id)
                except Exception:
                    logger.exception("Failed to stop monitor for preference %s", pref_id)
        
        # Send confirmation message
        try:
            if len(deleted_labels) == 1:
                message = f"\u2705 Deleted search: *{escape_markdown(deleted_labels[0])}*\\. You can now add a new search\\!"
            else:
                labels_list = "\\n".join([f"  \\- {escape_markdown(label)}" for label in deleted_labels])
                message = f"\u2705 Deleted {len(deleted_labels)} searches:\\n{labels_list}\\nYou can now add a new search\\!"
            self.send_message(chat_id, message)
        except TelegramError:
            logger.exception("Failed to send delete confirmation to chat %s", chat_id)
    
    def _handle_list_command(self, chat_id: str) -> None:
        """Handle /list command to show user's active search preferences."""
        with session_scope() as session:
            user = session.query(User).filter(User.telegram_chat_id == chat_id).one_or_none()
            if not user:
                try:
                    self.send_message(chat_id, "\u274c You are not registered\\. Please register first\\.")
                except TelegramError:
                    logger.exception("Failed to send error message to chat %s", chat_id)
                return
            
            # Find all preferences (both active and inactive)
            all_prefs = session.query(SearchPreference).filter(
                SearchPreference.user_id == user.id
            ).order_by(SearchPreference.created_at.desc()).all()
            
            if not all_prefs:
                try:
                    self.send_message(chat_id, "\U0001f50d You don't have any searches yet\\. Use the Chrome extension to add one\\!")
                except TelegramError:
                    logger.exception("Failed to send message to chat %s", chat_id)
                return
            
            # Build message with active and inactive preferences
            active_list = []
            inactive_list = []
            for pref in all_prefs:
                label = escape_markdown(pref.label or "Untitled search")
                if pref.active:
                    active_list.append(f"  \u2705 {label}")
                else:
                    inactive_list.append(f"  \u274c {label}")
            
            message_parts = ["\U0001f4cb *Your searches:*\\n"]
            
            if active_list:
                message_parts.append("\\n*Active:*")
                message_parts.extend(active_list)
            
            if inactive_list:
                message_parts.append("\\n*Inactive:*")
                message_parts.extend(inactive_list)
            
            message_parts.append("\\nUse /delete to remove active searches\\.")
            
            message = "\\n".join(message_parts)
            
            try:
                self.send_message(chat_id, message)
            except TelegramError:
                logger.exception("Failed to send list message to chat %s", chat_id)


class TelegramUpdatePoller(threading.Thread):
    def __init__(self, service: TelegramService, interval_seconds: int = 5, on_user_registered=None) -> None:
        super().__init__(daemon=True)
        self.service = service
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        # Set the callback on the service
        self.service.on_user_registered = on_user_registered

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

