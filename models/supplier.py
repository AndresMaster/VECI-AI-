from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True, nullable=False)

    # Relación con compras/pagos realizados al proveedor
    purchases: Mapped[List["SupplierPurchase"]] = relationship(
        "SupplierPurchase",
        back_populates="supplier",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def to_dict(self) -> dict:
        dt = self.created_at or datetime.now()
        return {
            "id": self.id,
            "name": self.name,
            "contact_name": self.contact_name or "",
            "phone": self.phone or "",
            "email": self.email or "",
            "address": self.address or "",
            "notes": self.notes or "",
            "created_at": dt.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def __repr__(self) -> str:
        return f"<Supplier(id={self.id}, name='{self.name}')>"


class SupplierPurchase(Base):
    """
    Modelo de Compras / Pagos a Proveedores (Egresos de inventario).
    Almacena fecha y HORA EXACTA (DateTime) de la transacción con proveedor.
    """
    __tablename__ = "supplier_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True, nullable=False)
    invoice_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payment_method: Mapped[str] = mapped_column(String(30), default="CASH")

    supplier = relationship("Supplier", back_populates="purchases", lazy="joined")

    @property
    def created_at(self) -> datetime:
        return self.fecha_hora

    def to_dict(self) -> dict:
        dt = self.fecha_hora or datetime.now()
        supplier_name = self.supplier.name if self.supplier else "Proveedor General"
        return {
            "id": self.id,
            "supplier_id": self.supplier_id,
            "supplier_name": supplier_name,
            "fecha_hora": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%S"),
            "timestamp": dt,
            "invoice_reference": self.invoice_reference or "",
            "descripcion": self.descripcion,
            "monto": round(float(self.monto or 0.0), 2),
            "payment_method": self.payment_method,
        }

    def __repr__(self) -> str:
        return (
            f"<SupplierPurchase(id={self.id}, supplier_id={self.supplier_id}, "
            f"fecha_hora='{self.fecha_hora}', monto={self.monto})>"
        )


# Alias en español
CompraProveedor = SupplierPurchase
