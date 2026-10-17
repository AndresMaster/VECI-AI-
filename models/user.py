import re
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from werkzeug.security import generate_password_hash, check_password_hash


class AuthBase(DeclarativeBase):
    """
    DeclarativeBase exclusivo para la base de datos maestra de autenticación (auth.db).
    Garantiza que auth.db SOLO contenga la tabla de Usuarios, manteniendo aislamiento
    estricto respecto a las tablas operativas de cada tenant (tenant_{username}.db).
    """
    pass


class User(AuthBase):
    """
    Modelo de Usuario almacenado únicamente en la base de datos maestra (auth.db).
    Campos: ID, Username, Password_Hash, Created_At.
    """
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    def set_password(self, raw_password: str) -> None:
        """Encripta la contraseña utilizando werkzeug.security (PBKDF2/Scrypt con salt)."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Verifica la contraseña contra el hash encriptado (compatible con werkzeug y bcrypt)."""
        if not self.password_hash or not raw_password:
            return False
        if self.password_hash.startswith(("$2a$", "$2b$", "$2y$")):
            try:
                import bcrypt
                return bcrypt.checkpw(
                    raw_password.encode("utf-8"),
                    self.password_hash.encode("utf-8"),
                )
            except Exception:
                return False
        return check_password_hash(self.password_hash, raw_password)

    @staticmethod
    def sanitize_tenant_slug(username: str) -> str:
        """Convierte el nombre de usuario en un identificador seguro para el archivo tenant_{username}.db."""
        clean = (username or "").strip().lower()
        slug = re.sub(r"[^a-z0-9_]", "_", clean)
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug or "default"

    @property
    def tenant_db_filename(self) -> str:
        return f"tenant_{self.sanitize_tenant_slug(self.username)}.db"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "tenant_db": self.tenant_db_filename,
        }
