import uuid
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import func, TIMESTAMP
from datetime import datetime


class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy ORM models.
    All models inherit from this class.
    """
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    """
    Convenience factory for a UUID primary key column with a server-side default.
    Use as a class-level assignment in model definitions:

        id: Mapped[uuid.UUID] = uuid_pk()
    """
    return mapped_column(primary_key=True, default=uuid.uuid4)


def now_utc() -> Mapped[datetime]:
    """
    Convenience factory for a non-nullable TIMESTAMPTZ column defaulting to NOW().
    """
    return mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
