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
import threading
import random
from urllib.parse import urljoin, urlparse
import cloudscraper

class StealthYad2Monitor:
    def __init__(self, url: str, check_interval: int = 900):
        self.url = url
        self.check_interval = check_interval
        
        # Use cloudscraper instead of requests for better Cloudflare bypass
        self.session = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        self.known_listings_file = 'known_listings.json'
        
        # Rotate user agents
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
        
        # Set initial headers
        self.update_headers()
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('yad2_monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Load known listings from file
        self.known_listings = self.load_known_listings()
        
        # Track request patterns to avoid detection
        self.last_request_time = 0
        self.request_count = 0
        
    def update_headers(self):
        """Update headers with a random user agent and realistic browser headers."""
        user_agent = random.choice(self.user_agents)
        
        # More realistic headers that change based on browser type
        if 'Chrome' in user_agent:
            accept = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
            sec_ch_ua = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
        else:  # Firefox
            accept = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
            sec_ch_ua = None
        
        headers = {
            'User-Agent': user_agent,
            'Accept': accept,
            'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',  # Hebrew preference for Israeli site
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        if sec_ch_ua:
            headers['sec-ch-ua'] = sec_ch_ua
            headers['sec-ch-ua-mobile'] = '?0'
            headers['sec-ch-ua-platform'] = '"Windows"'
        
        self.session.headers.update(headers)
        
    def add_randomized_delay(self):
        """Add randomized delays to mimic human behavior."""
        # Base delay between 2-8 seconds, with additional random component
        base_delay = random.uniform(2, 8)
        
        # Add extra delay if we've made multiple requests recently
        if self.request_count > 5:
            base_delay += random.uniform(10, 30)
            self.request_count = 0
            
        # Longer delays during typical "sleep" hours (11 PM to 6 AM Israel time)
        current_hour = datetime.now().hour
        if 23 <= current_hour or current_hour <= 6:
            base_delay += random.uniform(60, 180)
            
        self.logger.info(f"Waiting {base_delay:.1f} seconds before request...")
        time.sleep(base_delay)
        
    def load_known_listings(self) -> Dict:
        """Load known listings from JSON file."""
        try:
            if os.path.exists(self.known_listings_file):
                with open(self.known_listings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.logger.info(f"Loaded {len(data)} known listings from file")
                    return data
            else:
                self.logger.info("No existing known_listings.json file found, starting fresh")
                return {}
        except Exception as e:
            self.logger.error(f"Error loading known listings: {e}")
            return {}
    
    def save_known_listings(self):
        """Save known listings to JSON file."""
        try:
            with open(self.known_listings_file, 'w', encoding='utf-8') as f:
                json.dump(self.known_listings, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved {len(self.known_listings)} known listings to file")
        except Exception as e:
            self.logger.error(f"Error saving known listings: {e}")
            
    def simulate_human_browsing(self):
        """Simulate human browsing patterns before the main request."""
        # Occasionally visit the homepage first
        if random.random() < 0.2:  # 20% chance
            try:
                self.logger.info("Simulating homepage visit...")
                self.session.get('https://www.yad2.co.il/', timeout=30)
                time.sleep(random.uniform(1, 3))
            except:
                pass  # Ignore errors in simulation
                
    def fetch_page(self) -> str:
        """Fetch the HTML content of the Yad2 page with stealth measures."""
        try:
            # Update headers periodically
            if random.random() < 0.3:  # 30% chance to rotate headers
                self.update_headers()
                
            # Add human-like delay
            self.add_randomized_delay()
            
            # Simulate human browsing patterns occasionally
            self.simulate_human_browsing()
            
            # Add referer header to look more natural
            referer_options = [
                'https://www.google.com/',
                'https://www.yad2.co.il/',
                'https://www.yad2.co.il/realestate/rent'
            ]
            self.session.headers['Referer'] = random.choice(referer_options)
            
            # Make the request
            response = self.session.get(self.url, timeout=30)
            response.raise_for_status()
            
            # Track request
            self.last_request_time = time.time()
            self.request_count += 1
            
            self.logger.info(f"Successfully fetched page (Status: {response.status_code})")
            return response.text
            
        except requests.RequestException as e:
            self.logger.error(f"Error fetching page: {e}")
            
            # If blocked, wait longer before retry
            if "403" in str(e) or "429" in str(e):
                self.logger.warning("Possible rate limiting detected, waiting longer...")
                time.sleep(random.uniform(300, 600))  # 5-10 minutes
                
            return ""
    
    def parse_listings(self, html: str) -> List[Dict]:
        """Parse listings from the HTML content."""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []
        
        # Yad2 uses item-layout_itemLink__CZZ7w class for listing links
        listing_items = soup.find_all('a', class_='item-layout_itemLink__CZZ7w')
        
        self.logger.info(f"Found {len(listing_items)} potential listings")
        
        for item in listing_items:
            try:
                listing_data = self.extract_listing_data(item)
                if listing_data:
                    listings.append(listing_data)
            except Exception as e:
                self.logger.warning(f"Error parsing listing: {e}")
                
        return listings
    
    def extract_listing_data(self, item) -> Dict:
        """Extract data from a single listing item."""
        listing = {}
        
        # Extract the link first
        href = item.get('href', '')
        if href:
            if href.startswith('/'):
                listing['link'] = 'https://www.yad2.co.il' + href
            else:
                listing['link'] = href
        else:
            listing['link'] = 'No link'
        
        # Check for price drop indicator
        price_drop_elem = item.find('span', class_='text-tag_textTag__mQeO_ item-image_imageTag__EaPPF')
        listing['price_dropped'] = price_drop_elem is not None
        if listing['price_dropped']:
            listing['price_drop_text'] = price_drop_elem.get_text(strip=True) if price_drop_elem else 'מחיר ירד'
        
        # Find the content container
        content_div = item.find('div', class_='item-layout_itemContent__qT_A8')
        if not content_div:
            return None
        
        # Extract price
        price_elem = content_div.find('span', class_='feed-item-price_price__ygoeF')
        listing['price'] = price_elem.get_text(strip=True) if price_elem else 'No price'
        
        # Extract title/heading
        title_elem = content_div.find('span', class_='item-data-content_heading__tphH4')
        listing['title'] = title_elem.get_text(strip=True) if title_elem else 'No title'
        
        # Extract location and details
        info_lines = content_div.find_all('span', class_='item-data-content_itemInfoLine__AeoPP')
        
        if len(info_lines) >= 1:
            listing['location'] = info_lines[0].get_text(strip=True)
        else:
            listing['location'] = 'No location'
            
        if len(info_lines) >= 2:
            listing['details'] = info_lines[1].get_text(strip=True)
        else:
            listing['details'] = 'No details'
        
        # Create unique ID
        listing_text = f"{listing['title']}_{listing['location']}"
        listing['id'] = hashlib.md5(listing_text.encode()).hexdigest()
        
        # Add timestamp
        listing['timestamp'] = datetime.now().isoformat()
        
        return listing
    
    def check_for_updates(self) -> List[Dict]:
        """Check for new listings and price drops."""
        html = self.fetch_page()
        if not html:
            return []
        
        current_listings = self.parse_listings(html)
        updates = []
        
        for listing in current_listings:
            listing_id = listing['id']
            known_listing = self.known_listings.get(listing_id)
            
            if not known_listing:
                listing['notification_type'] = 'new'
                updates.append(listing)
                self.known_listings[listing_id] = listing.copy()
                
            elif listing.get('price_dropped') and not known_listing.get('price_dropped'):
                listing['notification_type'] = 'price_drop'
                listing['old_price'] = known_listing.get('price', 'Unknown')
                updates.append(listing)
                self.known_listings[listing_id] = listing.copy()
                
            elif listing['price'] != known_listing.get('price'):
                listing['notification_type'] = 'price_change'
                listing['old_price'] = known_listing.get('price', 'Unknown')
                updates.append(listing)
                self.known_listings[listing_id] = listing.copy()
                
            else:
                self.known_listings[listing_id]['timestamp'] = listing['timestamp']
        
        # Clean up old listings
        current_ids = {listing['id'] for listing in current_listings}
        removed_count = 0
        for listing_id in list(self.known_listings.keys()):
            if listing_id not in current_ids:
                del self.known_listings[listing_id]
                removed_count += 1
        
        if removed_count > 0:
            self.logger.info(f"Removed {removed_count} inactive listings")
        
        # Save updated listings
        if updates or removed_count > 0:
            self.save_known_listings()
        
        return updates
    
    def format_listing_for_telegram(self, listing: Dict) -> str:
        """Format a listing for Telegram message."""
        notification_type = listing.get('notification_type', 'new')
        
        if notification_type == 'new':
            header = "🏠 *NEW LISTING FOUND\\!*"
        elif notification_type == 'price_drop':
            header = f"💰 *PRICE DROP\\!* {listing.get('price_drop_text', 'מחיר ירד')}"
        elif notification_type == 'price_change':
            header = "📈 *PRICE CHANGED\\!*"
        else:
            header = "🏠 *LISTING UPDATE\\!*"
        
        def escape_md(text):
            chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in chars_to_escape:
                text = text.replace(char, f'\\{char}')
            return text
        
        title = escape_md(listing['title'])
        price = escape_md(listing['price'])
        location = escape_md(listing['location'])
        details = escape_md(listing['details'])
        link = listing['link']
        
        message = f"""
{header}

🏷️ *Title:* {title}
💰 *Price:* {price}"""
        
        if notification_type in ['price_drop', 'price_change'] and listing.get('old_price'):
            old_price = escape_md(listing['old_price'])
            message += f" \\(was: {old_price}\\)"
            
        message += f"""
📍 *Location:* {location}
📋 *Details:* {details}
🔗 [View Listing]({link})

⏰ {datetime.now().strftime('%Y\\-%m\\-%d %H:%M:%S')}
"""
        return message

class TelegramYad2Bot:
    def __init__(self, bot_token: str, chat_id: str, yad2_url: str, check_interval: int = 15):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.monitor = StealthYad2Monitor(yad2_url)
        self.check_interval = check_interval  # minutes
        self.logger = logging.getLogger(__name__)
        
        # Test bot connection
        asyncio.run(self.test_connection())
    
    async def test_connection(self):
        """Test the Telegram bot connection."""
        try:
            bot_info = await self.bot.get_me()
            self.logger.info(f"✅ Telegram bot connected: @{bot_info.username}")
            await self.send_message("🤖 Stealth Yad2 Monitor Started!\nUsing advanced anti-detection measures...")
        except TelegramError as e:
            self.logger.error(f"❌ Telegram bot connection failed: {e}")
            raise
    
    async def send_message(self, message: str):
        """Send a message to the Telegram chat."""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='MarkdownV2',
                disable_web_page_preview=True
            )
        except TelegramError as e:
            self.logger.error(f"Error sending Telegram message: {e}")
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message.replace('\\', '').replace('*', '').replace('_', ''),
                    disable_web_page_preview=True
                )
            except TelegramError as e2:
                self.logger.error(f"Error sending fallback message: {e2}")
    
    def check_listings_sync(self):
        """Synchronous wrapper for checking listings."""
        try:
            self.logger.info("🔍 Starting stealth listing check...")
            updates = self.monitor.check_for_updates()
            
            if updates:
                self.logger.info(f"🎉 Found {len(updates)} updates!")
                
                for listing in updates:
                    message = self.monitor.format_listing_for_telegram(listing)
                    asyncio.run(self.send_message(message))
                    time.sleep(random.uniform(1, 3))  # Random delay between messages
                    
                summary = self.create_summary(updates)
                asyncio.run(self.send_message(summary))
                
            else:
                self.logger.info("No new listings found")
                
        except Exception as e:
            self.logger.error(f"Error during listing check: {e}")
            asyncio.run(self.send_message(f"❌ Monitoring error: {str(e)}"))
    
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
        
        def run_with_jitter():
            """Run checks with randomized timing."""
            while True:
                try:
                    self.check_listings_sync()
                    
                    # Add jitter to check interval (±25%)
                    base_interval = self.check_interval * 60  # Convert to seconds
                    jitter = random.uniform(-0.25, 0.25) * base_interval
                    sleep_time = max(300, base_interval + jitter)  # Minimum 5 minutes
                    
                    self.logger.info(f"Next check in {sleep_time/60:.1f} minutes")
                    time.sleep(sleep_time)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    self.logger.error(f"Monitoring error: {e}")
                    time.sleep(300)  # Wait 5 minutes before retry
        
        run_with_jitter()

def main():
    # Configuration
    BOT_TOKEN = "7889379066:AAEflJTAFqwTDLXoYClOddzUoSXHR2Yxw1U"  # Get from @BotFather
    CHAT_ID = "6372583816"  # Your Telegram chat ID
    YAD2_URL = "https://www.yad2.co.il/realestate/rent?maxPrice=8000&minRooms=2.5&maxRooms=2.5&minFloor=0&maxFloor=3&property=1&balcony=1&multiNeighborhood=1520%2C1521%2C1461&zoom=13"
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("❌ Please configure your BOT_TOKEN and CHAT_ID!")
        return
    
    try:
        telegram_bot = TelegramYad2Bot(
            bot_token=BOT_TOKEN,
            chat_id=CHAT_ID,
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