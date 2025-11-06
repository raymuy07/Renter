import secrets
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def generate_uuid() -> str:
    return secrets.token_hex(16)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    email: Mapped[Optional[str]] = mapped_column(String(320), unique=True, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    telegram_start_token: Mapped[str] = mapped_column(String(128), unique=True, default=lambda: secrets.token_urlsafe(12))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    preferences: Mapped[list["SearchPreference"]] = relationship("SearchPreference", back_populates="user", cascade="all, delete-orphan")


class SearchPreference(Base):
    __tablename__ = "search_preferences"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    query_params: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=20)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship("User", back_populates="preferences")
    listings: Mapped[list["Listing"]] = relationship("Listing", back_populates="preference", cascade="all, delete-orphan")


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True, nullable=False)
    preference_id: Mapped[str] = mapped_column(String(64), ForeignKey("search_preferences.id"), index=True, nullable=False)
    listing_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    price: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    price_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    price_drop_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_notification_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    preference: Mapped[SearchPreference] = relationship("SearchPreference", back_populates="listings")
    user: Mapped[User] = relationship("User")


Index("ix_listing_user_listing", Listing.user_id, Listing.listing_id, unique=True)
Index("ix_listing_preference_listing", Listing.preference_id, Listing.listing_id)

