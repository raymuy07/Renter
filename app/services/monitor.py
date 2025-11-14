from __future__ import annotations

import logging
import random
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import session_scope
from ..models import Listing, SearchPreference, User
from ..yad_scrapper import StealthYad2Monitor
from .telegram import TelegramService


logger = logging.getLogger(__name__)


ListingDict = Dict[str, Any]


class MonitorWorker(threading.Thread):
    def __init__(self, preference_id: str, telegram_service: TelegramService) -> None:
        super().__init__(daemon=True)
        self.preference_id = preference_id
        self.telegram_service = telegram_service
        self.stop_event = threading.Event()
        self.settings = get_settings()
        self.monitor: Optional[StealthYad2Monitor] = None

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        logger.info("Starting monitor worker for preference %s", self.preference_id)
        while not self.stop_event.is_set():
            sleep_seconds = self.settings.min_check_interval_seconds

            # Check quiet hours BEFORE scraping
            if self.settings.is_quiet_hours():
                logger.debug("Quiet hours active. Skipping scraping for preference %s", self.preference_id)
                # Sleep for a shorter time during quiet hours to check when they end
                self.stop_event.wait(1500)  # Check every 5 minutes
                continue

            with session_scope() as session:
                preference = session.get(SearchPreference, self.preference_id)
                if not preference or not preference.active:
                    logger.info("Preference %s inactive. Stopping worker", self.preference_id)
                    return

                if self.monitor is None or self.monitor.url != preference.source_url:
                    self.monitor = StealthYad2Monitor(preference.source_url)

                user = preference.user
                sleep_seconds = max(
                    self.settings.min_check_interval_seconds,
                    min(
                        preference.check_interval_minutes * 60,
                        self.settings.max_check_interval_seconds,
                    ),
                )

                updates_to_send = self._process_preference(session, user, preference)

                chat_id = user.telegram_chat_id
                if chat_id and updates_to_send:
                    messages = [self.monitor.format_listing_for_telegram(update) for update in updates_to_send]
                    self.telegram_service.notify_listing_updates(chat_id, messages)

                if chat_id:
                    pending = self._collect_pending_notifications(session, user.id)
                    if pending:
                        messages = [self.monitor.format_listing_for_telegram(item) for item in pending]
                        self.telegram_service.notify_listing_updates(chat_id, messages)
                        self._mark_pending_as_sent(session, user.id, pending)

            jitter = random.uniform(-0.25, 0.25)
            wait_seconds = max(self.settings.min_check_interval_seconds, sleep_seconds + (sleep_seconds * jitter))
            logger.debug("Worker %s sleeping for %.1fs", self.preference_id, wait_seconds)
            self.stop_event.wait(wait_seconds)

        logger.info("Monitor worker for preference %s stopped", self.preference_id)

    def _process_preference(
        self,
        session: Session,
        user: User,
        preference: SearchPreference,
    ) -> List[ListingDict]:
        assert self.monitor is not None
        html = self.monitor.fetch_page()
        if not html:
            return []

        listings = self.monitor.parse_listings(html)
        updates: List[ListingDict] = []

        for listing in listings:
            listing_id = listing["id"]
            existing: Optional[Listing] = session.execute(
                select(Listing).where(Listing.user_id == user.id, Listing.listing_id == listing_id)
            ).scalar_one_or_none()

            listing_copy = listing.copy()
            listing_copy.setdefault("timestamp", datetime.utcnow().isoformat())

            normalized_price = self.monitor.normalize_price_for_comparison(listing.get("price", ""))
            price_hash = self.monitor.compute_price_hash(normalized_price)

            if existing is None:
                listing_copy["notification_type"] = "new"
                updates.append(listing_copy)
                model = Listing(
                    user_id=user.id,
                    preference_id=preference.id,
                    listing_id=listing_id,
                    raw_payload=listing_copy,
                    price=listing.get("price"),
                    price_hash=price_hash,
                    price_drop_notified=False,
                    last_notification_type="new",
                    last_notified_at=datetime.utcnow() if user.telegram_chat_id else None,
                    first_seen_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                )
                try:
                    session.add(model)
                    session.flush()  # Flush immediately to catch constraint violations
                except IntegrityError:
                    # Listing already exists (race condition or previous failed transaction)
                    logger.warning("Listing %s already exists for user %s, treating as existing", listing_id, user.id)
                    session.rollback()
                    # Re-fetch the existing listing and update it
                    existing = session.execute(
                        select(Listing).where(Listing.user_id == user.id, Listing.listing_id == listing_id)
                    ).scalar_one_or_none()
                    if existing:
                        existing.last_seen_at = datetime.utcnow()
                        existing.raw_payload = listing_copy
                    # Remove from updates since it's not actually new
                    if updates and updates[-1] == listing_copy:
                        updates.pop()
            else:
                existing.last_seen_at = datetime.utcnow()
                existing.raw_payload = listing_copy

                previous_price_hash = existing.price_hash
                current_price_hash = price_hash

                notification_type: Optional[str] = None

                if previous_price_hash is None or previous_price_hash == "":
                    previous_price_hash = self.monitor.compute_price_hash(
                        self.monitor.normalize_price_for_comparison(existing.price or "")
                    )

                if current_price_hash != previous_price_hash:
                    if listing.get("price_dropped"):
                        notification_type = "price_drop"
                        listing_copy["notification_type"] = "price_drop"
                        listing_copy["old_price"] = existing.price
                    else:
                        notification_type = "price_change"
                        listing_copy["notification_type"] = "price_change"
                        listing_copy["old_price"] = existing.price

                    updates.append(listing_copy)

                    existing.price = listing.get("price")
                    existing.price_hash = current_price_hash
                    existing.price_drop_notified = listing.get("price_dropped", False)
                    existing.last_notification_type = notification_type
                    existing.last_notified_at = datetime.utcnow() if user.telegram_chat_id else None
                else:
                    existing.price = listing.get("price")
                    existing.price_hash = current_price_hash

        return updates if user.telegram_chat_id else []

    def _collect_pending_notifications(self, session: Session, user_id: str) -> List[ListingDict]:
        rows = session.execute(
            select(Listing).where(
                Listing.user_id == user_id,
                Listing.last_notified_at.is_(None),
                Listing.last_notification_type.is_not(None),
            )
        ).scalars().all()
        pending: List[ListingDict] = []
        for row in rows:
            payload = row.raw_payload or {}
            if payload:
                pending.append(payload)
        return pending

    def _mark_pending_as_sent(self, session: Session, user_id: str, payloads: List[ListingDict]) -> None:
        if not payloads:
            return
        listing_ids = [item.get("id") for item in payloads if item.get("id")]
        if not listing_ids:
            return

        session.query(Listing).filter(
            Listing.user_id == user_id,
            Listing.listing_id.in_(listing_ids),
        ).update({Listing.last_notified_at: datetime.utcnow()}, synchronize_session=False)


class MonitorManager:
    def __init__(self, telegram_service: TelegramService) -> None:
        self.telegram_service = telegram_service
        self.workers: Dict[str, MonitorWorker] = {}
        self.lock = threading.Lock()

    def start_monitor(self, preference_id: str) -> None:
        with self.lock:
            worker = self.workers.get(preference_id)
            if worker and worker.is_alive():
                logger.info("Monitor for %s already running", preference_id)
                return

            worker = MonitorWorker(preference_id, self.telegram_service)
            self.workers[preference_id] = worker
            worker.start()

    def stop_monitor(self, preference_id: str) -> None:
        with self.lock:
            worker = self.workers.pop(preference_id, None)
            if worker:
                worker.stop()

    def stop_all(self) -> None:
        with self.lock:
            for worker in self.workers.values():
                worker.stop()
            self.workers.clear()

