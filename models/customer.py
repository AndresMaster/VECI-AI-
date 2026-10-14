from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base

class Customer(Base):
    """
    Modelo de Cliente para el Módulo de Cartera y Crédito.
    Permite registrar clientes, otorgar facturas a crédito y controlar su saldo.
    """
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    document_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True) # Cédula/NIT
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    credit_limit: Mapped[float] = mapped_column(Float, default=0.0) # Límite de crédito disponible
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relación con facturas
    invoices = relationship("Invoice", back_populates="customer", cascade="all, delete-orphan", lazy="select")

    @property
    def current_debt(self) -> float:
        """Calcula el saldo pendiente por pagar de facturas a crédito no liquidadas."""
        return round(sum(inv.total for inv in self.invoices if inv.payment_type == "CREDIT" and inv.payment_status == "PENDING"), 2)

    @property
    def available_credit(self) -> float:
        """Crédito disponible restante respecto al límite otorgado."""
        return max(0.0, round(self.credit_limit - self.current_debt, 2))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "document_id": self.document_id or "",
            "phone": self.phone or "",
            "email": self.email or "",
            "address": self.address or "",
            "credit_limit": self.credit_limit,
            "current_debt": self.current_debt,
            "available_credit": self.available_credit,
            "notes": self.notes or ""
        }

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, name='{self.name}', debt={self.current_debt})>"
