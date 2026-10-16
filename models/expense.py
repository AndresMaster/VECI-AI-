from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base


class GastosGenerales(Base):
    """
    Modelo de Gastos Generales (Egresos fijos o variables como Servicios Públicos,
    Nómina, Arriendo, Mantenimiento, Varios).
    Almacena fecha y hora exacta (DateTime) para inteligencia financiera temporal.
    """
    __tablename__ = "gastos_generales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True, nullable=False)
    categoria: Mapped[str] = mapped_column(String(100), nullable=False, default="Varios", index=True)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    @property
    def created_at(self) -> datetime:
        return self.fecha_hora

    @property
    def category(self) -> str:
        return self.categoria

    @property
    def description(self) -> str:
        return self.descripcion

    @property
    def amount(self) -> float:
        return self.monto

    def to_dict(self) -> dict:
        dt = self.fecha_hora or datetime.now()
        return {
            "id": self.id,
            "fecha_hora": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%S"),
            "timestamp": dt,
            "categoria": self.categoria,
            "descripcion": self.descripcion,
            "monto": round(float(self.monto or 0.0), 2),
        }

    def __repr__(self) -> str:
        return (
            f"<GastosGenerales(id={self.id}, fecha_hora='{self.fecha_hora}', "
            f"categoria='{self.categoria}', monto={self.monto})>"
        )


# Alias en inglés por compatibilidad arquitectónica
Expense = GastosGenerales
