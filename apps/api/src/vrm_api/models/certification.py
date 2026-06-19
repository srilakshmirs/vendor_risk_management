"""Certification — SOC 2, ISO 27001, PCI-DSS, HIPAA, etc."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .vendor import Vendor


class Certification(Base, TimestampMixin):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"), index=True)
    cert_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # SOC2 | ISO27001 | PCI-DSS | HIPAA
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # Certified|Expired|NotCertified|Pending
    issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    document_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    vendor: Mapped["Vendor"] = relationship(back_populates="certifications")
