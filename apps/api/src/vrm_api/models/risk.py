"""Risk assessment — composite score, components, narrative."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .vendor import Vendor


class RiskAssessment(Base, TimestampMixin):
    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100, higher = riskier
    traffic_light: Mapped[str] = mapped_column(String(8), nullable=False, index=True)  # Red|Yellow|Green
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # CRITICAL|HIGH|MEDIUM|LOW|NONE
    anomaly_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    components: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_rules: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0")

    vendor: Mapped["Vendor"] = relationship(back_populates="risk_assessments")
