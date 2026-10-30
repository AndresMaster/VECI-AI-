import json
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base


class RegistroAnulaciones(Base):
    """
    Modelo inmutable de Auditoría de Anulaciones / Reversiones de Ventas (Loss Prevention).
    Almacena en la base de datos de cada inquilino (tenant_{username}.db) qué factura fue
    reversada/eliminada, su monto total, la fecha y hora exacta de la anulación, el motivo
    obligatorio registrado por el cajero, y el snapshot completo (JSON) de la factura y sus
    productos para poder visualizar su detalle o retornarla a Flujo de Caja.
    """
    __tablename__ = "registro_anulaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factura_id_original: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    monto_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fecha_anulacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True, nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    restaurada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @property
    def fecha_hora(self) -> datetime:
        """Alias indexado de fecha y hora exacta de la anulación."""
        return self.fecha_anulacion

    @fecha_hora.setter
    def fecha_hora(self, value: datetime) -> None:
        self.fecha_anulacion = value

    def to_dict(self) -> dict:
        dt = self.fecha_anulacion or datetime.now()
        snapshot_data = None
        if self.snapshot_json:
            try:
                snapshot_data = json.loads(self.snapshot_json)
            except Exception:
                snapshot_data = None
        items_list = snapshot_data.get("items", []) if isinstance(snapshot_data, dict) else []
        return {
            "id": self.id,
            "factura_id_original": self.factura_id_original,
            "monto_total": round(float(self.monto_total or 0.0), 2),
            "fecha_anulacion": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "fecha": dt.strftime("%Y-%m-%d"),
            "hora": dt.strftime("%H:%M:%S"),
            "timestamp": dt,
            "motivo": self.motivo,
            "restaurada": bool(self.restaurada),
            "snapshot": snapshot_data,
            "items": items_list,
            "has_snapshot": bool(snapshot_data),
        }

    def __repr__(self) -> str:
        return (
            f"<RegistroAnulaciones(id={self.id}, factura_id_original='{self.factura_id_original}', "
            f"monto_total={self.monto_total}, fecha_anulacion='{self.fecha_anulacion}')>"
        )


# Alias en inglés por compatibilidad arquitectónica (AuditLog)
AuditLog = RegistroAnulaciones
