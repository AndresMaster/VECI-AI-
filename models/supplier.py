from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base

class Supplier(Base):
    """
    Modelo de Proveedor para el Módulo de Compras y Cartera.
    """
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "contact_name": self.contact_name or "",
            "phone": self.phone or "",
            "email": self.email or "",
            "address": self.address or "",
            "notes": self.notes or ""
        }

    def __repr__(self) -> str:
        return f"<Supplier(id={self.id}, name='{self.name}')>"
