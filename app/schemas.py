from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field


class RegisterUserRequest(BaseModel):
    email: Optional[str] = Field(default=None, max_length=320)
    display_name: Optional[str] = Field(default=None, max_length=255)
    telegram_username: Optional[str] = Field(default=None, max_length=255)
    label: Optional[str] = Field(default=None, max_length=255)
    search_url: AnyHttpUrl
    query_params: Dict[str, Any] = Field(default_factory=dict)
    check_interval_minutes: Optional[int] = Field(default=None, ge=5, le=180)


class RegisterUserResponse(BaseModel):
    user_id: str
    preference_id: str
    telegram_deep_link: Optional[str]
    message: str


class ListingPayload(BaseModel):
    listing_id: str
    title: str
    price: str
    location: str
    details: str
    link: str
    notification_type: str
    timestamp: datetime


class UserStatusResponse(BaseModel):
    user_id: str
    telegram_chat_id: Optional[str]
    preferences: List[Dict[str, Any]]
    pending_notifications: int = 0

