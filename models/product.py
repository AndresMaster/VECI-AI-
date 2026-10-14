from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base

class Product(Base):
    """
    Modelo de Producto para el Módulo de Inventario.
    Incluye cálculo automático de utilidad, margen y control de stock mínimo.
    """
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    barcode: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    presentacion: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True) # ej. "65g", "500ml", "1kg"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Costos y Precios
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0) # Costo de Compra
    sale_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0) # Precio de Venta
    
    # Stock y Alertas
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    category: Mapped[Optional[str]] = mapped_column(String(100), default="General")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación con items de factura
    invoice_items = relationship("InvoiceItem", back_populates="product", lazy="select")

    # ================= CÁLCULOS AUTOMÁTICOS (PROPERTIES) =================

    @property
    def unit_profit(self) -> float:
        """Utilidad neta calculada automáticamente por unidad vendida."""
        return round(self.sale_price - self.cost_price, 2)

    @property
    def profit_margin_percent(self) -> float:
        """Margen porcentual de utilidad sobre el precio de venta."""
        if self.sale_price > 0:
            return round(((self.sale_price - self.cost_price) / self.sale_price) * 100, 2)
        return 0.0

    @property
    def total_cost_value(self) -> float:
        """Valoración total en costo de compra del inventario actual de este producto."""
        return round(self.cost_price * self.stock, 2)

    @property
    def total_retail_value(self) -> float:
        """Valoración total en precio de venta del inventario actual."""
        return round(self.sale_price * self.stock, 2)

    @property
    def is_low_stock(self) -> bool:
        """Indica si el stock actual está en o por debajo del umbral mínimo de alerta."""
        return self.stock <= self.min_stock

    @property
    def display_name(self) -> str:
        """Nombre con presentación física concatenada (ej. 'Chocoramo - 65g')."""
        if self.presentacion and self.presentacion.strip():
            return f"{self.name} - {self.presentacion.strip()}"
        return self.name

    def to_dict(self) -> dict:
        """Serialización a diccionario para consumo en vistas o controlador AI."""
        return {
            "id": self.id,
            "barcode": self.barcode,
            "name": self.name,
            "presentacion": self.presentacion or "",
            "display_name": self.display_name,
            "description": self.description or "",
            "cost_price": self.cost_price,
            "sale_price": self.sale_price,
            "stock": self.stock,
            "min_stock": self.min_stock,
            "category": self.category,
            "unit_profit": self.unit_profit,
            "profit_margin_percent": self.profit_margin_percent,
            "total_cost_value": self.total_cost_value,
            "total_retail_value": self.total_retail_value,
            "is_low_stock": self.is_low_stock
        }

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, barcode='{self.barcode}', name='{self.name}', stock={self.stock})>"
