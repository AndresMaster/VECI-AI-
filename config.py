from pathlib import Path
import os
import shutil
import sys

# Paths (con soporte transparente para ejecución en código fuente y empaquetado PyInstaller)
if getattr(sys, "frozen", False):
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    if sys.platform == "win32":
        _appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        BASE_DIR = _appdata / "VECI_AI"
    elif sys.platform == "darwin":
        BASE_DIR = Path.home() / "Library" / "Application Support" / "VECI_AI"
    else:
        BASE_DIR = Path.home() / ".veci_ai"
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    # Copiar base de datos maestra vacía (auth.db) empaquetada si es la primera ejecución
    _bundled_auth = RESOURCE_DIR / "auth.db"
    _target_auth = BASE_DIR / "auth.db"
    if _bundled_auth.exists() and not _target_auth.exists():
        try:
            shutil.copy2(_bundled_auth, _target_auth)
        except Exception:
            pass
else:
    BASE_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = BASE_DIR

AUTH_DATABASE_PATH = BASE_DIR / "auth.db"
AUTH_DATABASE_URL = f"sqlite:///{AUTH_DATABASE_PATH}"
DATABASE_PATH = BASE_DIR / "pos_inventory.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# App Config
APP_TITLE = "VECI_AI"
APP_VERSION = "1.0.5"
LOW_STOCK_THRESHOLD_DEFAULT = 5

# Open Food Facts API Policy (Required Custom User-Agent)
OFF_CONTACT_EMAIL = "andresromeo1324@gmail.com"
OFF_USER_AGENT = f"VECI_AI/2.0 - Python - Contacto: {OFF_CONTACT_EMAIL}"

# Pastel UI Design Tokens (Light Theme with High Contrast Typography)
class PastelTheme:
    # Backgrounds & Surfaces
    BG_LIGHT = "#F8FAFC"             # Slate 50 (fondo limpio)
    SURFACE_WHITE = "#FFFFFF"        # Blanco puro para tarjetas
    SURFACE_VARIANT = "#F1F5F9"      # Slate 100 para contenedores secundarios
    BORDER_LIGHT = "#E2E8F0"         # Borde sutil

    # Pastel Accents
    PRIMARY = "#4F46E5"              # Indigo suave accesible
    PRIMARY_PASTEL = "#EEF2FF"       # Fondo pastel índigo
    ACCENT_MINT = "#10B981"          # Menta / Verde éxito
    MINT_PASTEL = "#ECFDF5"          # Fondo menta pastel
    ACCENT_CORAL = "#F43F5E"         # Coral / Rosa alerta
    CORAL_PASTEL = "#FFF1F2"         # Fondo coral pastel
    ACCENT_AMBER = "#F59E0B"         # Ámbar alerta stock
    AMBER_PASTEL = "#FFFBEB"         # Fondo ámbar pastel
    ACCENT_SKY = "#0284C7"           # Celeste info
    SKY_PASTEL = "#F0F9FF"           # Fondo celeste pastel

    # Typography (Alto contraste para lectura rápida en caja)
    TEXT_PRIMARY = "#0F172A"         # Slate 900
    TEXT_SECONDARY = "#475569"       # Slate 600
    TEXT_MUTED = "#94A3B8"           # Slate 400
    TEXT_ON_PRIMARY = "#FFFFFF"

    # Geometría
    BORDER_RADIUS_CARD = 16
    BORDER_RADIUS_BUTTON = 12
    BORDER_RADIUS_INPUT = 10
