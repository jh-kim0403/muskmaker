import uuid
from datetime import datetime
from sqlalchemy import Boolean, TIMESTAMP, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, uuid_pk


class AdminUser(Base):
    """
    Admin panel users. Completely separate from app User accounts.
    Auth is via a static API key (SHA-256 hashed at rest).

    role values: 'reviewer' | 'super_admin'
    """
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="reviewer")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AdminUser name={self.name} role={self.role}>"
