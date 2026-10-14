from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base

class Invoice(Base):
    """
    Modelo de Factura / Ticket de Venta.
    Soporta ventas al contado y a crédito asignadas a clientes con descripción de crédito.
    """
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Cliente asociado (Opcional en ventas rápidas de contado, requerido en crédito)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id"), nullable=True)
    
    # Modalidad de Pago: 'CASH', 'CREDIT', 'CARD', 'TRANSFER'
    payment_type: Mapped[str] = mapped_column(String(20), default="CASH")
    # Estado: 'PAID' (Pagada), 'PENDING' (Pendiente/Crédito), 'CANCELLED' (Anulada)
    payment_status: Mapped[str] = mapped_column(String(20), default="PAID")

    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    tax: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float, default=0.0)

    # Descripción opcional del crédito o condiciones pactadas
    credit_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Origen de la transacción (útil para auditoría e integración con la futura IA de voz)
    created_via: Mapped[str] = mapped_column(String(50), default="POS_DESKTOP") # 'POS_DESKTOP', 'AI_VOICE'

    # Relaciones
    customer = relationship("Customer", back_populates="invoices", lazy="joined")
    items: Mapped[List["InvoiceItem"]] = relationship(
        "InvoiceItem", 
        back_populates="invoice", 
        cascade="all, delete-orphan", 
        lazy="joined"
    )

    @property
    def total_cost(self) -> float:
        """Costo total acumulado de los productos vendidos en esta factura."""
        return round(sum(item.unit_cost * item.quantity for item in self.items), 2)

    @property
    def total_profit(self) -> float:
        """Utilidad real generada por la factura (Total venta - Total costo)."""
        return round(self.total - self.total_cost, 2)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_id": self.customer_id,
            "customer_name": self.customer.name if self.customer else "Consumidor Final",
            "payment_type": self.payment_type,
            "payment_status": self.payment_status,
            "subtotal": self.subtotal,
            "discount": self.discount,
            "tax": self.tax,
            "total": self.total,
            "total_profit": self.total_profit,
            "credit_notes": self.credit_notes or "",
            "created_via": self.created_via,
            "items_count": sum(item.quantity for item in self.items),
            "items": [item.to_dict() for item in self.items]
        }

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, number='{self.invoice_number}', total={self.total}, status='{self.payment_status}')>"


class InvoiceItem(Base):
    """
    Renglón o Ítem individual de la factura.
    Almacena una copia histórica del costo y precio al momento de la venta para
    garantizar consistencia contable aun si el producto cambia de precio en inventario.
    """
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id"), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("products.id"), nullable=True)

    # Snapshot histórico
    barcode: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    presentacion: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True) # ej. "65g", "500ml"
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)

    # Relaciones
    invoice = relationship("Invoice", back_populates="items")
    product = relationship("Product", back_populates="invoice_items")

    @property
    def unit_profit(self) -> float:
        return round(self.unit_price - self.unit_cost, 2)

    @property
    def total_profit(self) -> float:
        return round(self.unit_profit * self.quantity, 2)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "barcode": self.barcode,
            "product_name": self.product_name,
            "presentacion": self.presentacion or "",
            "unit_cost": self.unit_cost,
            "unit_price": self.unit_price,
            "quantity": self.quantity,
            "subtotal": self.subtotal,
            "total_profit": self.total_profit
        }

    def __repr__(self) -> str:
        return f"<InvoiceItem(barcode='{self.barcode}', qty={self.quantity}, subtotal={self.subtotal})>"
