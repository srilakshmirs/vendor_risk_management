"""Vendor — the central entity."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .alert import Alert
    from .breach import BreachEvent
    from .certification import Certification
    from .contract import Contract
    from .data_access import DataAccess
    from .risk import RiskAssessment
    from .sbom import Sbom


class Vendor(Base, TimestampMixin):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vendor_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(8), nullable=False)
    criticality: Mapped[str] = mapped_column(String(16), nullable=False, default="Tier3")
    annual_spend_usd: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    primary_contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_assessment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    under_investigation: Mapped[bool] = mapped_column(default=False, nullable=False)
    financial_health_score: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    preliminary_risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)

    # Relationships
    contracts: Mapped[list["Contract"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    certifications: Mapped[list["Certification"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    data_access: Mapped[list["DataAccess"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="vendor", cascade="all, delete-orphan", order_by="RiskAssessment.created_at.desc()"
    )
    breaches: Mapped[list["BreachEvent"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    sboms: Mapped[list["Sbom"]] = relationship(
        back_populates="vendor", cascade="all, delete-orphan", order_by="Sbom.created_at.desc()"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vendor {self.vendor_id} {self.name}>"
