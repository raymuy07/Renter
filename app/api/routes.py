from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from ..config import get_settings
from ..db import session_scope
from ..models import Listing, SearchPreference, User
from ..schemas import AuthRequest, RegisterUserRequest, RegisterUserResponse, UserStatusResponse
from ..services.monitor import MonitorManager
from ..services.telegram import TelegramService, escape_markdown


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/auth")
def authenticate(payload: AuthRequest) -> dict[str, bool]:
    """Authenticate user with username and password."""
    settings = get_settings()
    valid_credentials = settings.get_valid_credentials()
    
    for cred in valid_credentials:
        if payload.username == cred["username"] and payload.password == cred["password"]:
            return {"authenticated": True}
    
    return {"authenticated": False}


def _get_services(request: Request) -> tuple[TelegramService, MonitorManager]:
    try:
        telegram_service: TelegramService = request.app.state.telegram_service
        monitor_manager: MonitorManager = request.app.state.monitor_manager
    except AttributeError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service not initialized") from exc
    return telegram_service, monitor_manager


@router.post("/users/register", response_model=RegisterUserResponse)
def register_user(payload: RegisterUserRequest, request: Request) -> RegisterUserResponse:
    telegram_service, monitor_manager = _get_services(request)

    with session_scope() as session:
        user = session.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()

        if user is None:
            user = User(username=payload.username)
            session.add(user)

        session.flush()

        preference = session.execute(
            select(SearchPreference).where(
                SearchPreference.user_id == user.id,
                SearchPreference.source_url == str(payload.search_url),
            )
        ).scalar_one_or_none()

        if preference is None:
            preference = SearchPreference(
                user_id=user.id,
                label=payload.label,
                source_url=str(payload.search_url),
                query_params=dict(payload.query_params),
                check_interval_minutes=get_settings().default_check_interval_minutes,
            )
            session.add(preference)
        else:
            preference.query_params = dict(payload.query_params)
            if payload.label:
                preference.label = payload.label
            preference.active = True

        session.flush()

        deep_link = telegram_service.generate_deep_link(user)
        qr_code = telegram_service.generate_qr_code(deep_link)
        preference_id = preference.id
        user_id = user.id
        chat_id = user.telegram_chat_id
        label = preference.label or "Yad2 search"
        source_url = preference.source_url

    # Only start monitoring if user has already connected their Telegram
    if chat_id:
        monitor_manager.start_monitor(preference_id)
        try:
            message = (
                "\ud83d\udd0d Monitoring updated for *{label}*\n"
                "We'll notify you about new listings and price changes.\n"
                "\ud83d\udd17 [View search]({url})"
            ).format(label=escape_markdown(label), url=source_url)
            telegram_service.send_message(chat_id, message)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to send registration confirmation to Telegram chat %s", chat_id)

    if chat_id:
        response_message = "Search preference updated. Monitoring is active."
    else:
        response_message = "Registration completed. Scan the QR code or click the Telegram link to activate monitoring."
    
    return RegisterUserResponse(
        user_id=user_id,
        preference_id=preference_id,
        telegram_deep_link=deep_link,
        telegram_qr_code=qr_code,
        message=response_message,
    )

@router.get("/debug/auth")
def debug_auth():
    """Debug endpoint to check auth credentials."""
    settings = get_settings()
    credentials = settings.get_valid_credentials()
    return {
        "credentials_count": len(credentials),
        "usernames": [cred["username"] for cred in credentials],
        "has_credentials": len(credentials) > 0,
    }

    
@router.get("/users/{user_id}/status", response_model=UserStatusResponse)
def get_user_status(user_id: str) -> UserStatusResponse:
    with session_scope() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        preferences = []
        for pref in user.preferences:
            preferences.append(
                {
                    "id": pref.id,
                    "label": pref.label,
                    "source_url": pref.source_url,
                    "active": pref.active,
                    "check_interval_minutes": pref.check_interval_minutes,
                    "created_at": pref.created_at,
                }
            )

        pending_notifications = session.execute(
            select(func.count()).select_from(Listing).where(
                Listing.user_id == user.id,
                Listing.last_notified_at.is_(None),
                Listing.last_notification_type.is_not(None),
            )
        ).scalar_one()

    return UserStatusResponse(
        user_id=user.id,
        telegram_chat_id=user.telegram_chat_id,
        preferences=preferences,
        pending_notifications=pending_notifications or 0,
    )

