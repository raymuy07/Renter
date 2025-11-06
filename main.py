from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.db import init_db
from app.db import session_scope
from app.models import SearchPreference
from app.services.monitor import MonitorManager
from app.services.telegram import TelegramService, TelegramUpdatePoller


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Yad2 Monitoring Service",
    version="0.2.0",
    description="Multi-user Yad2 scraper with Telegram notifications.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    init_db()

    telegram_service = TelegramService()
    monitor_manager = MonitorManager(telegram_service)
    poller = TelegramUpdatePoller(telegram_service, interval_seconds=5)
    poller.start()

    app.state.telegram_service = telegram_service
    app.state.monitor_manager = monitor_manager
    app.state.telegram_poller = poller

    with session_scope() as session:
        active_preferences = session.query(SearchPreference.id).filter(SearchPreference.active.is_(True)).all()

    for pref_id, in active_preferences:
        monitor_manager.start_monitor(pref_id)


@app.on_event("shutdown")
def on_shutdown() -> None:
    poller: TelegramUpdatePoller | None = getattr(app.state, "telegram_poller", None)
    if poller:
        poller.stop()

    monitor_manager: MonitorManager | None = getattr(app.state, "monitor_manager", None)
    if monitor_manager:
        monitor_manager.stop_all()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

