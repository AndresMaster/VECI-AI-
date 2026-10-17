# -*- mode: python ; coding: utf-8 -*-
"""
Configuración de PyInstaller (veci_ai.spec) para VECI_AI v1.0.0.
- Modo Directorio (Onedir) optimizado para Inno Setup en Windows y paquete .app en macOS.
- Modo Ventana (console=False / windowed).
- Empaqueta íconos (.ico / .icns), base de datos maestra vacía (auth.db) e imports ocultos.
"""

import os
import sqlite3
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None
PROJECT_ROOT = Path(SPECPATH).resolve()
ASSETS_DIR = PROJECT_ROOT / "build_assets"


def ensure_empty_master_auth_db() -> Path:
    """
    Garantiza que exista una base de datos maestra vacía (auth.db) con el esquema
    de la tabla 'usuarios' lista para empaquetarse en el instalador.
    """
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    clean_auth_db = ASSETS_DIR / "auth.db"
    if not clean_auth_db.exists():
        conn = sqlite3.connect(str(clean_auth_db))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(80) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at DATETIME NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()
    return clean_auth_db


master_auth_db_path = ensure_empty_master_auth_db()

# Recolección automática de binarios y recursos dinámicos (pyzbar, flet, cv2)
datas = [
    (str(master_auth_db_path), "."),
    (str(ASSETS_DIR), "build_assets"),
]
binaries = []
hiddenimports = [
    # Core & ORM
    "sqlalchemy",
    "sqlalchemy.orm",
    "sqlalchemy.ext.declarative",
    "sqlalchemy.sql.default_comparator",
    "sqlalchemy.dialects.sqlite",
    "sqlite3",
    # Seguridad y Autenticación Multi-Tenant
    "werkzeug",
    "werkzeug.security",
    "bcrypt",
    # Visión por Computador y Lector de Código de Barras
    "cv2",
    "numpy",
    "pyzbar",
    "pyzbar.pyzbar",
    "pyzbar.wrapper",
    # UI Frameworks & Gráficos
    "flet",
    "flet_desktop",
    "customtkinter",
    "PIL",
    "PIL.Image",
    "matplotlib",
    "matplotlib.backends.backend_agg",
    "requests",
    # Módulos internos MVC de VECI_AI
    "config",
    "database",
    "models",
    "controllers",
    "views",
    "services",
]

for pkg in ("pyzbar", "flet", "flet_desktop"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        pass

try:
    binaries += collect_dynamic_libs("pyzbar")
except Exception:
    pass

try:
    hiddenimports += collect_submodules("sqlalchemy")
except Exception:
    pass

# Selección de ícono según sistema operativo
if sys.platform == "darwin":
    app_icon = str(ASSETS_DIR / "veci_ai_icon.icns")
else:
    app_icon = str(ASSETS_DIR / "veci_ai_icon.ico")

if not os.path.exists(app_icon):
    app_icon = None

a = Analysis(
    ["main.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(dict.fromkeys(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "unittest", "pydoc"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Modo Directorio (Onedir): exclude_binaries=True delega el empaquetado final a COLLECT
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VECI_AI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Modo ventana (sin consola negra detrás)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VECI_AI",
)

# En macOS, generar adicionalmente el Application Bundle (.app) listo para .dmg / .zip
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="VECI_AI.app",
        icon=app_icon,
        bundle_identifier="com.veciai.pos.inventory",
        info_plist={
            "CFBundleName": "VECI AI",
            "CFBundleDisplayName": "VECI AI",
            "CFBundleIdentifier": "com.veciai.pos.inventory",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSCameraUsageDescription": "VECI AI requiere acceso a la cámara para escanear códigos de barras en el POS.",
        },
    )
