from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker

from .config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"sqlite:///{settings.sqlite_db_path()}",
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:  # noqa: BLE001 - we want to rollback for any exception
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables."""

    from . import models  # noqa: F401 - ensure models are imported

    Base.metadata.create_all(bind=engine)

