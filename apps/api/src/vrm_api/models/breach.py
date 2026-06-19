"""Breach event — detected from breach DB feeds, news, vendor disclosure."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .vendor import Vendor


class BreachEvent(Base, TimestampMixin):
    __tablename__ = "breach_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # HIBP|CISA-KEV|news|self-disclosed
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # Low|Medium|High|Critical
    detected_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_exposed: Mapped[str] = mapped_column(Text, nullable=False, default="")  # ;-separated classes
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(default=False, nullable=False)

    vendor: Mapped["Vendor"] = relationship(back_populates="breaches")
