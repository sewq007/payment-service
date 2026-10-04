from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)  # копейки


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_payment_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    tariff_id: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    installment_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )