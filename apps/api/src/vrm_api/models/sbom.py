"""SBOM (Software Bill of Materials) models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .vendor import Vendor


class Sbom(Base, TimestampMixin):
    __tablename__ = "sboms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g., "CycloneDX", "SPDX"
    version: Mapped[str | None] = mapped_column(String(32), nullable=True) # e.g. "1.4"
    
    vendor: Mapped["Vendor"] = relationship(back_populates="sboms")
    components: Mapped[list["SbomComponent"]] = relationship(
        back_populates="sbom", cascade="all, delete-orphan", order_by="SbomComponent.name"
    )

    def __repr__(self) -> str:
        return f"<Sbom {self.id} format={self.format}>"


class SbomComponent(Base, TimestampMixin):
    __tablename__ = "sbom_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sbom_id: Mapped[int] = mapped_column(ForeignKey("sboms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str | None] = mapped_column(String(64), nullable=True) # e.g., "library", "framework"
    
    # Store detected vulnerabilities during ingestion for easy querying later
    vulnerabilities: Mapped[str | None] = mapped_column(String(1024), nullable=True) # JSON string or comma separated
    highest_severity: Mapped[str | None] = mapped_column(String(16), nullable=True) # "CRITICAL", "HIGH", etc.

    sbom: Mapped["Sbom"] = relationship(back_populates="components")

    def __repr__(self) -> str:
        return f"<SbomComponent {self.name}@{self.version}>"
