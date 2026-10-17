import re
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import func

from database import (
    init_auth_db,
    get_auth_db_session,
    connect_tenant_db,
    disconnect_tenant_db,
)
from models.user import User


class AuthController:
    """
    Controlador de Autenticación y Administrador de Sesión Multi-Tenant (SessionManager).
    - Gestiona el registro y validación de credenciales contra la base maestra 'auth.db'.
    - Encripta contraseñas utilizando werkzeug.security (y soporta bcrypt).
    - Conecta dinámicamente el ORM a 'tenant_{username}.db' con aislamiento total de datos.
    - Destruye la conexión local del tenant al cerrar sesión.
    """

    def __init__(self) -> None:
        init_auth_db()
        self.current_user: Optional[Dict[str, Any]] = None
        self.current_tenant_db: Optional[str] = None

    @property
    def is_authenticated(self) -> bool:
        return self.current_user is not None

    @property
    def current_username(self) -> str:
        return self.current_user["username"] if self.current_user else ""

    def register(
        self,
        username: str,
        password: str,
        confirm_password: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Registra un nuevo usuario en 'auth.db' con contraseña encriptada y crea su
        archivo de base de datos exclusivo 'tenant_{username}.db' ejecutando
        Base.metadata.create_all(engine) desde cero.
        """
        clean_username = (username or "").strip()
        if len(clean_username) < 3:
            return False, "El nombre de usuario debe tener al menos 3 caracteres.", None

        if not re.match(r"^[A-Za-z0-9_.\-]+$", clean_username):
            return (
                False,
                "El usuario solo puede contener letras, números, puntos, guiones o guion bajo (sin espacios).",
                None,
            )

        if not password or len(password) < 4:
            return False, "La contraseña debe tener al menos 4 caracteres.", None

        if confirm_password is not None and password != confirm_password:
            return False, "Las contraseñas ingresadas no coinciden.", None

        with get_auth_db_session() as session:
            existing = (
                session.query(User)
                .filter(func.lower(User.username) == clean_username.lower())
                .first()
            )
            if existing:
                return False, f"El usuario '{clean_username}' ya está registrado.", None

            new_user = User(
                username=clean_username,
                created_at=datetime.now(),
            )
            new_user.set_password(password)
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            user_data = new_user.to_dict()

        # Conectar e inicializar desde cero la base de datos exclusiva del usuario (tenant_{username}.db)
        tenant_path = connect_tenant_db(clean_username, seed_sample_data=False)
        self.current_user = user_data
        self.current_tenant_db = str(tenant_path)

        return (
            True,
            f"Cuenta '{clean_username}' creada exitosamente. Base de datos aislada ({tenant_path.name}) inicializada.",
            user_data,
        )

    def login(
        self,
        username: str,
        password: str,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Autentica un usuario contra 'auth.db' y conecta el ORM a su base de datos
        exclusiva 'tenant_{username}.db'.
        """
        clean_username = (username or "").strip()
        if not clean_username or not password:
            return False, "Por favor ingresa tu usuario y contraseña.", None

        with get_auth_db_session() as session:
            user = (
                session.query(User)
                .filter(func.lower(User.username) == clean_username.lower())
                .first()
            )
            if not user or not user.check_password(password):
                return False, "Usuario o contraseña incorrectos.", None

            user_data = user.to_dict()
            canonical_username = user.username

        # Conectar el ORM a la base de datos exclusiva del usuario autenticado
        tenant_path = connect_tenant_db(canonical_username, seed_sample_data=False)
        self.current_user = user_data
        self.current_tenant_db = str(tenant_path)

        return (
            True,
            f"Bienvenido de nuevo, {canonical_username}.",
            user_data,
        )

    def logout(self) -> None:
        """
        Cierra la sesión activa y destruye la conexión local a la base de datos del usuario.
        """
        disconnect_tenant_db()
        self.current_user = None
        self.current_tenant_db = None


# Alias semántico para gestión de sesión
SessionManager = AuthController
