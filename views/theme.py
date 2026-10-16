import flet as ft
from config import PastelTheme

def create_card(
    content: ft.Control,
    padding: int = 16,
    bg_color: str = PastelTheme.SURFACE_WHITE,
    border_color: str = PastelTheme.BORDER_LIGHT,
    border_radius: int = PastelTheme.BORDER_RADIUS_CARD,
    expand: bool | int = False,
    visible: bool = True
) -> ft.Container:
    """Contenedor estilo Card redondeada con sombra y borde sutil."""
    return ft.Container(
        content=content,
        bgcolor=bg_color,
        border_radius=border_radius,
        border=ft.Border.all(1, border_color),
        padding=padding,
        expand=expand,
        visible=visible,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=8,
            color="#0A0F1D0A", # Sombra suave sutil
            offset=ft.Offset(0, 2),
        )
    )

def create_metric_tile(
    title: str,
    value: str,
    icon: str,
    bg_pastel: str,
    icon_color: str,
    subtitle: str = ""
) -> ft.Container:
    """Tarjeta KPI métrica con fondo pastel, icono grande y números legibles."""
    return create_card(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=4,
                    controls=[
                        ft.Text(title, size=13, weight=ft.FontWeight.W_500, color=PastelTheme.TEXT_SECONDARY),
                        ft.Text(value, size=22, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                        *( [ft.Text(subtitle, size=11, color=PastelTheme.TEXT_MUTED)] if subtitle else [] )
                    ]
                ),
                ft.Container(
                    content=ft.Icon(icon, size=28, color=icon_color),
                    bgcolor=bg_pastel,
                    border_radius=12,
                    padding=10,
                )
            ]
        ),
        padding=18,
        expand=True
    )

def create_badge(text: str, bg_color: str, text_color: str) -> ft.Container:
    """Etiqueta/Chip redondeado para estados y categorías."""
    return ft.Container(
        content=ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=text_color),
        bgcolor=bg_color,
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
    )

def safe_update(control: ft.Control) -> None:
    """Actualiza el control de forma segura si ya está montado en la página."""
    try:
        control.update()
    except Exception:
        pass

