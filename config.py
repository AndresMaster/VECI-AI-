from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "pos_inventory.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# App Config
APP_TITLE = "PointPulse POS & Inventory"
APP_VERSION = "2.0.0"
LOW_STOCK_THRESHOLD_DEFAULT = 5

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
