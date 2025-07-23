import requests
from bs4 import BeautifulSoup
import time
import json
import hashlib
from datetime import datetime
import logging
from typing import Set, Dict, List
import os
from telegram import Bot
from telegram.error import TelegramError
import schedule
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

        # Set up rotating file logging (no terminal output)
        from logging.handlers import RotatingFileHandler
        log_file = 'yad2_monitor.log'
        max_bytes = 2 * 1024 * 1024  # 2 MB
        backup_count = 3  # Keep up to 3 old log files
        handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.handlers = []  # Remove any existing handlers
        self.logger.addHandler(handler)

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
                full_link = 'https://www.yad2.co.il' + href
            else:
                full_link = href
            # Remove everything after the question mark
            base_link = full_link.split('?', 1)[0]
            listing['link'] = base_link
        else:
            listing['link'] = 'No link'

        # Check for price drop indicator
        price_drop_elem = item.find('span', class_='text-tag_textTag__mQeO_ item-image_imageTag__EaPPF')
        listing['price_dropped'] = price_drop_elem is not None
        if listing['price_dropped']:
            listing['price_drop_text'] = price_drop_elem.get_text(strip=True) if price_drop_elem else 'מחיר ירד'
        
        # Filter out "פרויקט חדש" (new project) listings
        if listing.get('price_drop_text') == 'פרויקט חדש':
            return None

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

        # Filter out listings with missing essential data
        if (listing['price'] == 'No price' or 
            listing['title'] == 'No title' or 
            listing['location'] == 'No location'):
            return None

        # Create unique ID using title, location, and link
        listing_text = f"{listing['title']}_{listing['location']}_{listing['link']}"
        listing['id'] = hashlib.md5(listing_text.encode()).hexdigest()

        # Add timestamp
        listing['timestamp'] = datetime.now().isoformat()

        return listing

    def normalize_price_for_comparison(self, price: str) -> str:
        """Normalize price string for accurate comparison, handling shekel symbols and whitespace."""
        if not price or price == 'No price':
            return price
        
        # Remove extra whitespace and normalize
        normalized = price.strip()
        
        # Handle different shekel representations
        normalized = normalized.replace('₪', '₪')  # Ensure consistent unicode
        normalized = ' '.join(normalized.split())  # Normalize internal whitespace
        
        return normalized

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
                # This is a completely new listing
                listing['notification_type'] = 'new'
                updates.append(listing)
                
                # Store with normalized price for future comparisons
                stored_listing = listing.copy()
                stored_listing['normalized_price'] = self.normalize_price_for_comparison(listing['price'])
                stored_listing['price_hash'] = hashlib.md5(stored_listing['normalized_price'].encode()).hexdigest()
                stored_listing['price_drop_notified'] = False
                self.known_listings[listing_id] = stored_listing

            else:
                # This listing already exists, check for changes
                current_normalized_price = self.normalize_price_for_comparison(listing['price'])
                previous_normalized_price = known_listing.get('normalized_price', '')
                
                # If we don't have normalized_price in stored data, create it from the stored price
                if not previous_normalized_price:
                    previous_normalized_price = self.normalize_price_for_comparison(known_listing.get('price', ''))
                
                price_changed = current_normalized_price != previous_normalized_price
                
                # Check if this is a new price drop (price drop indicator is present now but wasn't before)
                current_has_drop_indicator = listing.get('price_dropped', False)
                previous_had_drop_indicator = known_listing.get('price_dropped', False)
                
                # Track the actual price to detect real price drops
                current_price_hash = hashlib.md5(current_normalized_price.encode()).hexdigest()
                previous_price_hash = known_listing.get('price_hash', '')
                
                if current_has_drop_indicator and not previous_had_drop_indicator and price_changed:
                    # This is a NEW price drop that we haven't notified about yet
                    listing['notification_type'] = 'price_drop'
                    listing['old_price'] = known_listing.get('price', 'Unknown')
                    updates.append(listing)
                    
                    # Update the stored listing with the new information
                    updated_listing = listing.copy()
                    updated_listing['normalized_price'] = current_normalized_price
                    updated_listing['price_hash'] = current_price_hash
                    updated_listing['price_drop_notified'] = True  # Mark that we've sent this notification
                    self.known_listings[listing_id] = updated_listing
                    
                elif price_changed and not current_has_drop_indicator:
                    # Regular price change without drop indicator
                    listing['notification_type'] = 'price_change'
                    listing['old_price'] = known_listing.get('price', 'Unknown')
                    updates.append(listing)
                    
                    # Update the stored listing
                    updated_listing = listing.copy()
                    updated_listing['normalized_price'] = current_normalized_price
                    updated_listing['price_hash'] = current_price_hash
                    updated_listing['price_drop_notified'] = False  # Reset drop notification flag
                    self.known_listings[listing_id] = updated_listing
                    
                else:
                    # No significant changes, just update timestamp
                    self.known_listings[listing_id]['timestamp'] = listing['timestamp']
                    # Keep the existing price_hash and price_drop_notified status
                    if 'price_hash' not in self.known_listings[listing_id]:
                        self.known_listings[listing_id]['normalized_price'] = current_normalized_price
                        self.known_listings[listing_id]['price_hash'] = current_price_hash
                        self.known_listings[listing_id]['price_drop_notified'] = False

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
            header = "🏠 *פוסט חדש*"
        elif notification_type == 'price_drop':
            header = f"💰 *ירידת מחיר* {listing.get('price_drop_text', 'מחיר ירד')}"
        elif notification_type == 'price_change':
            header = "📈 *שינוי מחיר*"
        else:
            header = "🏠 *שינוי מחיר*"

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

🏷️ *כותרת:* {title}
💰 *מחיר:* {price}"""

        if notification_type in ['price_drop', 'price_change'] and listing.get('old_price'):
            old_price = escape_md(listing['old_price'])
            message += f" \\(היה: {old_price}\\)"

        message += f"""
📍 *כתובת:* {location}
📋 *פרטים:* {details}
🔗 [View listing]({link})

{datetime.now().strftime("%Y %m %d %H:%M:%S")}
"""
        return message
