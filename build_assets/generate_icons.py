"""
Script de preparación de Assets e Íconos para empaquetado multiplataforma de VECI_AI.
Convierte el logo oficial de VECI_AI en:
  1. build_assets/veci_ai_icon.ico  (Windows - tamaños embebidos: 16, 32, 48, 64, 128, 256)
  2. build_assets/veci_ai_icon.icns (macOS - paquete Apple Icon Image)
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image


ASSETS_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE_CANDIDATES = [
    ASSETS_DIR / "veci_ai_logo.png",
    ASSETS_DIR / "veci_ai_logo.jpg",
    ASSETS_DIR / "logo.png",
    ASSETS_DIR / "logo.jpg",
]

ICO_OUTPUT = ASSETS_DIR / "veci_ai_icon.ico"
ICNS_OUTPUT = ASSETS_DIR / "veci_ai_icon.icns"
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def prepare_square_rgba(source_path: Path, target_size: int = 1024) -> Image.Image:
    """Abre la imagen fuente, la recorta centrada en proporción 1:1 y la escala en RGBA."""
    img = Image.open(source_path).convert("RGBA")
    width, height = img.size

    if width != height:
        min_side = min(width, height)
        left = (width - min_side) // 2
        top = (height - min_side) // 2
        img = img.crop((left, top, left + min_side, top + min_side))

    return img.resize((target_size, target_size), Image.Resampling.LANCZOS)


def generate_windows_ico(base_img: Image.Image, output_path: Path) -> None:
    """Genera el archivo .ico para Windows con resoluciones embebidas: 16, 32, 48, 64, 128, 256."""
    ico_base = base_img.resize((256, 256), Image.Resampling.LANCZOS)
    ico_base.save(
        output_path,
        format="ICO",
        sizes=ICO_SIZES,
    )
    print(f"[OK] Ícono de Windows generado: {output_path} (tamaños: {ICO_SIZES})")


def generate_macos_icns(base_img: Image.Image, output_path: Path) -> None:
    """
    Genera el archivo .icns para macOS usando Pillow (y iconutil nativo si está en macOS).
    """
    # Intentar primero con iconutil nativo de macOS para máxima compatibilidad Retina
    if sys.platform == "darwin" and shutil.which("iconutil"):
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                iconset_dir = Path(tmp_dir) / "veci_ai.iconset"
                iconset_dir.mkdir(parents=True, exist_ok=True)

                mac_sizes = [
                    (16, "icon_16x16.png"),
                    (32, "icon_16x16@2x.png"),
                    (32, "icon_32x32.png"),
                    (64, "icon_32x32@2x.png"),
                    (128, "icon_128x128.png"),
                    (256, "icon_128x128@2x.png"),
                    (256, "icon_256x256.png"),
                    (512, "icon_256x256@2x.png"),
                    (512, "icon_512x512.png"),
                    (1024, "icon_512x512@2x.png"),
                ]
                for px, filename in mac_sizes:
                    resized = base_img.resize((px, px), Image.Resampling.LANCZOS)
                    resized.save(iconset_dir / filename, format="PNG")

                subprocess.run(
                    ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_path)],
                    check=True,
                )
                print(f"[OK] Ícono de macOS (.icns vía iconutil) generado: {output_path}")
                return
        except Exception as exc:
            print(f"[INFO] Fallback a Pillow ICNS ({exc})")

    # Fallback multiplataforma directo con Pillow (funciona en Windows, Linux y macOS)
    icns_img = base_img.resize((512, 512), Image.Resampling.LANCZOS)
    icns_img.save(output_path, format="ICNS")
    print(f"[OK] Ícono de macOS (.icns vía Pillow) generado: {output_path}")


def resolve_source_image(cli_arg: str | None = None) -> Path:
    if cli_arg:
        custom_path = Path(cli_arg).expanduser().resolve()
        if not custom_path.exists():
            raise FileNotFoundError(f"No se encontró la imagen especificada: {custom_path}")
        return custom_path

    for candidate in DEFAULT_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "No se encontró la imagen base del logo en 'build_assets/'. "
        "Coloca 'veci_ai_logo.png' o pasa la ruta como argumento: "
        "python build_assets/generate_icons.py ruta/al/logo.jpg"
    )


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    cli_source = sys.argv[1] if len(sys.argv) > 1 else None
    source_img_path = resolve_source_image(cli_source)
    print(f"[INFO] Procesando imagen fuente: {source_img_path}")

    # Guardar copia maestra en PNG dentro de build_assets/ si se pasó una ruta externa
    master_png = ASSETS_DIR / "veci_ai_logo.png"
    base_rgba = prepare_square_rgba(source_img_path, target_size=1024)
    if source_img_path.resolve() != master_png.resolve():
        base_rgba.save(master_png, format="PNG")
        print(f"[OK] Copia maestra PNG guardada en: {master_png}")

    generate_windows_ico(base_rgba, ICO_OUTPUT)
    generate_macos_icns(base_rgba, ICNS_OUTPUT)


if __name__ == "__main__":
    main()
