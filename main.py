import requests
from bs4 import BeautifulSoup
import time
import json
import hashlib
from datetime import datetime
import logging
from typing import Set, Dict, List
import asyncio
import os
from telegram import Bot
from telegram.error import TelegramError
import schedule
import random
from urllib.parse import urljoin, urlparse
import cloudscraper
from yad_scrapper import StealthYad2Monitor
import pytz



class TelegramYad2Bot:
    def __init__(self, bot_token: str, chat_ids: List[str], yad2_url: str, check_interval: int = 15):
        self.bot = Bot(token=bot_token)
        self.chat_ids = chat_ids
        self.monitor = StealthYad2Monitor(yad2_url)
        self.check_interval = check_interval  # minutes
        self.logger = logging.getLogger(__name__)

        # Create persistent event loop
        self.loop = None
        self.setup_async_loop()

        # Test bot connection
        self.run_async(self.test_connection())

    def setup_async_loop(self):
        """Set up a persistent event loop for async operations."""
        try:
            # Try to get existing loop
            self.loop = asyncio.get_event_loop()
            if self.loop.is_closed():
                raise RuntimeError("Loop is closed")
        except RuntimeError:
            # Create new loop if none exists or current is closed
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def run_async(self, coro):
        """Run async coroutine safely."""
        try:
            if self.loop.is_running():
                # If loop is already running, schedule the task
                future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                return future.result(timeout=30)
            else:
                # Run the coroutine in the loop
                return self.loop.run_until_complete(coro)
        except Exception as e:
            self.logger.error(f"Error running async operation: {e}")
            # Fallback: try with a new event loop
            try:
                return asyncio.run(coro)
            except Exception as e2:
                self.logger.error(f"Fallback async operation also failed: {e2}")
                return None


    async def test_connection(self):
        """Test the Telegram bot connection."""
        try:
            bot_info = await self.bot.get_me()
            self.logger.info(f"✅ Telegram bot connected: @{bot_info.username}")
            await self.send_message("🤖 Stealth Yad2 Monitor Started\nUsing advanced anti-detection measures...")
        except TelegramError as e:
            self.logger.error(f"❌ Telegram bot connection failed: {e}")
            raise

    async def send_message(self, message: str):
        """Send a message to the Telegram chat."""
        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,  # Fixed: was self.chat_id, now using chat_id from loop
                    text=message,
                    parse_mode='MarkdownV2',
                    disable_web_page_preview=True,
                    read_timeout=30,
                    write_timeout=30,
                    connect_timeout=30,
                    pool_timeout=30
                )
                self.logger.info(f"Message sent successfully to chat {chat_id}")

            except TelegramError as e:
                self.logger.error(f"Error sending Telegram message to chat {chat_id}: {e}")
                try:
                    # Fallback without markdown
                    await self.bot.send_message(
                        chat_id=chat_id,  # Fixed: was self.chat_id, now using chat_id from loop
                        text=message.replace('\\', '').replace('*', '').replace('_', ''),
                        disable_web_page_preview=True,
                        read_timeout=30,
                        write_timeout=30,
                        connect_timeout=30,
                        pool_timeout=30
                    )
                    self.logger.info(f"Fallback message sent successfully to chat {chat_id}")

                except TelegramError as e2:
                    self.logger.error(f"Error sending fallback message to chat {chat_id}: {e2}")
                    # Wait a bit before next attempt
                    await asyncio.sleep(5)

    def send_message_sync(self, message: str):
        """Synchronous wrapper for sending messages - creates new coroutine each time."""
        # Create a new coroutine each time to avoid reuse issues
        return self.run_async(self.send_message(message))

    def check_listings_sync(self):
       
        """Synchronous wrapper for checking listings."""
        try:
            self.logger.info("🔍 Starting stealth listing check...")
            updates = self.monitor.check_for_updates()

            if updates:
                self.logger.info(f"🎉 Found {len(updates)} updates")

                for i, listing in enumerate(updates):
                    message = self.monitor.format_listing_for_telegram(listing)
                    # Use the sync wrapper to avoid coroutine reuse
                    self.send_message_sync(message)

                    # Add delay between messages, but not after the last one
                    if i < len(updates) - 1:
                        delay = random.uniform(2, 5)
                        self.logger.info(f"Waiting {delay:.1f}s before next message...")
                        time.sleep(delay)

                # Send summary after a short pause
                time.sleep(1)
                summary = self.create_summary(updates)
                self.send_message_sync(summary)

            else:
                self.logger.info("No new listings found")

        except Exception as e:
            self.logger.error(f"Error during listing check: {e}")
            error_msg = f"❌ Monitoring error: {str(e)[:100]}..."
            self.send_message_sync(error_msg)

    def create_summary(self, updates: List[Dict]) -> str:
        """Create a summary message."""
        new_count = sum(1 for u in updates if u.get('notification_type') == 'new')
        price_drop_count = sum(1 for u in updates if u.get('notification_type') == 'price_drop')
        price_change_count = sum(1 for u in updates if u.get('notification_type') == 'price_change')

        summary = f"📊 *Update Summary:*\n"
        if new_count:
            summary += f"🏠 {new_count} new listings\n"
        if price_drop_count:
            summary += f"💰 {price_drop_count} price drops\n"
        if price_change_count:
            summary += f"📈 {price_change_count} price changes\n"

        return summary

    def start_monitoring(self):
        """Start the monitoring service with randomized intervals."""
        
        self.logger.info(f"🚀 Starting stealth monitoring (avg {self.check_interval} min intervals)")
        israel_tz = pytz.timezone('Asia/Jerusalem')
        def run_with_jitter():
            """Run checks with randomized timing."""
            while True:
                israel_time = datetime.now(israel_tz)
                current_hour = israel_time.hour
                if current_hour < 7 or current_hour >= 23:
                    self.logger.info(f"Outside monitoring hours (current Israel time: {israel_time.strftime('%H:%M')})")
                    time.sleep(3600)  # Wait 1 hour before retry
                    continue
                
                try:
                    self.check_listings_sync()

                    # Add jitter to check interval (±25%)
                    base_interval = self.check_interval * 60  # Convert to seconds
                    jitter = random.uniform(-0.25, 0.25) * base_interval
                    sleep_time = max(300, base_interval + jitter)  # Minimum 5 minutes

                    self.logger.info(f"Next check in {sleep_time/60:.1f} minutes")
                    time.sleep(sleep_time)

                except KeyboardInterrupt:
                    self.logger.info("Monitoring stopped by user")
                    break
                except Exception as e:
                    self.logger.error(f"Monitoring error: {e}")
                    time.sleep(300)  # Wait 5 minutes before retry

        try:
            run_with_jitter()
        finally:
            # Clean up event loop
            if self.loop and not self.loop.is_closed():
                self.logger.info("Cleaning up event loop...")
                try:
                    # Cancel any pending tasks
                    pending = asyncio.all_tasks(self.loop)
                    for task in pending:
                        task.cancel()

                    # Close the loop
                    self.loop.close()
                except Exception as e:
                    self.logger.error(f"Error cleaning up event loop: {e}")

def main():
    # Configuration
    BOT_TOKEN = "7889379066:AAEflJTAFqwTDLXoYClOddzUoSXHR2Yxw1U"  # Get from @BotFather
    CHAT_IDS = ["6372583816", "8182838467","421141181"]  # Your Telegram chat ID
    YAD2_URL = "https://www.yad2.co.il/realestate/rent?maxPrice=8000&minRooms=2&maxRooms=2.5&minFloor=0&maxFloor=3&property=1&balcony=1&multiNeighborhood=1520%2C1521%2C1461&zoom=13"
    
   
    try:
        telegram_bot = TelegramYad2Bot(
            bot_token=BOT_TOKEN,
            chat_ids=CHAT_IDS,
            yad2_url=YAD2_URL,
            check_interval=20  # Average 20 minutes with jitter
        )
        
        telegram_bot.start_monitoring()
        
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
