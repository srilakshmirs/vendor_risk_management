"""Data access mapping — which systems and data classes a vendor touches."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .vendor import Vendor


class DataAccess(Base, TimestampMixin):
    __tablename__ = "data_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"), index=True)
    access_level: Mapped[str] = mapped_column(String(16), nullable=False)  # None|Read|ReadWrite|FullAdmin
    data_classes: Mapped[str] = mapped_column(Text, nullable=False, default="")  # ;-separated
    systems_accessed: Mapped[str] = mapped_column(Text, nullable=False, default="")  # ;-separated
    gdpr_compliant: Mapped[bool] = mapped_column(default=True, nullable=False)

    vendor: Mapped["Vendor"] = relationship(back_populates="data_access")

    @property
    def data_class_list(self) -> list[str]:
        return [c for c in self.data_classes.split(";") if c]

    @property
    def systems_list(self) -> list[str]:
        return [s for s in self.systems_accessed.split(";") if s]
