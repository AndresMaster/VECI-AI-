from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base


class Invoice(Base):
    """
    Modelo de Factura / Ticket de Venta.
    Soporta ventas al contado y a crédito asignadas a clientes con descripción de crédito,
    control de abonos parciales (con fecha y hora exacta) y saldo pendiente.
    """
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True, nullable=False)

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
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)

    # Descripción opcional del crédito o condiciones pactadas
    credit_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Origen de la transacción (útil para auditoría e integración con la futura IA de voz)
    created_via: Mapped[str] = mapped_column(String(50), default="POS_DESKTOP")  # 'POS_DESKTOP', 'AI_VOICE'

    # Relaciones
    customer = relationship("Customer", back_populates="invoices", lazy="joined")
    items: Mapped[List["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="joined"
    )
    payments: Mapped[List["InvoicePayment"]] = relationship(
        "InvoicePayment",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="joined",
        order_by="InvoicePayment.fecha_hora.asc()"
    )

    @property
    def fecha_hora(self) -> datetime:
        """Alias de fecha y hora exacta de la factura."""
        return self.created_at

    @property
    def total_abonos(self) -> float:
        """Suma total abonada a la factura."""
        if self.payments:
            return round(sum(p.amount for p in self.payments), 2)
        return round(float(self.amount_paid or 0.0), 2)

    @property
    def balance_due(self) -> float:
        """Saldo pendiente actual tras descontar abonos parciales."""
        if self.payment_status == "PAID":
            return 0.0
        paid = self.total_abonos
        return max(0.0, round(float(self.total or 0.0) - paid, 2))

    @property
    def total_cost(self) -> float:
        """Costo total acumulado de los productos vendidos en esta factura."""
        return round(sum(item.unit_cost * item.quantity for item in self.items), 2)

    @property
    def total_profit(self) -> float:
        """Utilidad real generada por la factura (Total venta - Total costo)."""
        return round(self.total - self.total_cost, 2)

    def to_dict(self) -> dict:
        dt = self.created_at or datetime.now()
        paid_val = self.total_abonos if self.payment_status != "PAID" else max(self.total, self.total_abonos)
        return {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "created_at": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "fecha_hora": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%S"),
            "timestamp": dt,
            "customer_id": self.customer_id,
            "customer_name": self.customer.name if self.customer else "Consumidor Final",
            "payment_type": self.payment_type,
            "payment_status": self.payment_status,
            "subtotal": round(float(self.subtotal or 0.0), 2),
            "discount": round(float(self.discount or 0.0), 2),
            "tax": round(float(self.tax or 0.0), 2),
            "total": round(float(self.total or 0.0), 2),
            "amount_paid": round(float(paid_val), 2),
            "balance_due": self.balance_due,
            "total_cost": self.total_cost,
            "total_profit": self.total_profit,
            "credit_notes": self.credit_notes or "",
            "created_via": self.created_via,
            "items_count": sum(item.quantity for item in self.items),
            "items": [item.to_dict() for item in self.items],
            "payments": [p.to_dict() for p in self.payments],
        }

    def __repr__(self) -> str:
        return (
            f"<Invoice(id={self.id}, number='{self.invoice_number}', "
            f"total={self.total}, balance_due={self.balance_due}, status='{self.payment_status}')>"
        )


class InvoiceItem(Base):
    """
    Renglón o Ítem individual de la factura (DetalleFactura).
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
    presentacion: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)  # ej. "65g", "500ml"
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)

    # Relaciones
    invoice = relationship("Invoice", back_populates="items")
    product = relationship("Product", back_populates="invoice_items", lazy="joined")

    # ================= ALIASES SNAPSHOT EN ESPAÑOL (DETALLE FACTURA) =================

    @property
    def precio_unitario(self) -> float:
        return self.unit_price

    @precio_unitario.setter
    def precio_unitario(self, value: float) -> None:
        self.unit_price = value

    @property
    def costo_unitario(self) -> float:
        return self.unit_cost

    @costo_unitario.setter
    def costo_unitario(self, value: float) -> None:
        self.unit_cost = value

    @property
    def nombre_producto_snapshot(self) -> str:
        return self.product_name

    @nombre_producto_snapshot.setter
    def nombre_producto_snapshot(self, value: str) -> None:
        self.product_name = value

    @property
    def display_product_name(self) -> str:
        """
        Retorna el nombre snapshot guardado en la factura (self.product_name),
        concatenando su presentación física si aplica.
        En ventas de 'Comodín / Venta Libre', respeta estrictamente el nombre/descripción
        personalizado guardado en self.product_name al momento de la venta.
        """
        snapshot_name = (self.product_name or "").strip()
        is_wildcard = (
            (self.barcode or "").startswith("COMODIN")
            or (self.product is not None and self.product.barcode == "COMODIN-VENTA-LIBRE")
        )
        if is_wildcard and snapshot_name:
            return snapshot_name

        pres = (self.presentacion or "").strip()
        if not pres and self.product and self.product.presentacion:
            pres = self.product.presentacion.strip()

        base_name = snapshot_name or (self.product.name if self.product else "").strip()

        if pres:
            # Si base_name terminaba con la presentación sin guion (ej. 'Leche Entera 1L'), normalizar con ' - '
            if base_name.endswith(f" - {pres}"):
                return base_name
            if base_name.endswith(f" {pres}"):
                base_name = base_name[: -len(pres)].strip()
            return f"{base_name} - {pres}"
        return snapshot_name or base_name

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
            "nombre_producto_snapshot": self.product_name,
            "display_name": self.display_product_name,
            "presentacion": (self.presentacion or (self.product.presentacion if self.product else "") or ""),
            "category": (self.product.category if self.product else "General"),
            "unit_cost": round(float(self.unit_cost or 0.0), 2),
            "costo_unitario": round(float(self.unit_cost or 0.0), 2),
            "unit_price": round(float(self.unit_price or 0.0), 2),
            "precio_unitario": round(float(self.unit_price or 0.0), 2),
            "quantity": int(self.quantity or 0),
            "subtotal": round(float(self.subtotal or 0.0), 2),
            "total_profit": self.total_profit,
        }

    def __repr__(self) -> str:
        return f"<InvoiceItem(barcode='{self.barcode}', qty={self.quantity}, subtotal={self.subtotal})>"


class InvoicePayment(Base):
    """
    Registro histórico de Abonos y Pagos aplicados a una Factura a crédito.
    Conserva la justificación con Fecha y Hora exacta (DateTime) de cada abono
    sin eliminar el historial previo de la factura.
    """
    __tablename__ = "invoice_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payment_kind: Mapped[str] = mapped_column(String(30), default="ABONO")  # 'ABONO' o 'PAGO_TOTAL'
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    invoice = relationship("Invoice", back_populates="payments")

    def to_dict(self) -> dict:
        dt = self.fecha_hora or datetime.now()
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "fecha_hora": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%S"),
            "amount": round(float(self.amount or 0.0), 2),
            "balance_after": round(float(self.balance_after or 0.0), 2),
            "payment_kind": self.payment_kind,
            "notes": self.notes or "",
        }

    def __repr__(self) -> str:
        return (
            f"<InvoicePayment(id={self.id}, invoice_id={self.invoice_id}, "
            f"amount={self.amount}, fecha_hora='{self.fecha_hora}')>"
        )
