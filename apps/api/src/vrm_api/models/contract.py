"""Contract — links to PDF + extracted clauses."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .vendor import Vendor


class Contract(Base, TimestampMixin):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value_usd: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extracted_terms: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    auto_renew: Mapped[bool] = mapped_column(default=False, nullable=False)

    vendor: Mapped["Vendor"] = relationship(back_populates="contracts")
