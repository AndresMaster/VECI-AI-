import os
import sys
from typing import Optional, Dict, Any

# En modo ventana de PyInstaller (console=False en Windows), sys.stdout y sys.stderr son None.
# Redirigirlos evita que librerías como Flet/rich/matplotlib fallen al escribir en consola.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import flet as ft
from config import APP_TITLE, PastelTheme
from database import init_auth_db
from services.barcode_manager import BarcodeManager, ScannerMode
from controllers import (
    AuthController,
    PosController,
    InventoryController,
    CustomerController,
    DashboardController,
)
from views import (
    AuthView,
    DashboardView,
    PosView,
    InventoryView,
    InOutView,
    CarteraView,
    CashFlowView,
    MainLayout,
)


def main(page: ft.Page) -> None:
    # 1. Configuración de Ventana y Tema
    page.title = APP_TITLE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = PastelTheme.BG_LIGHT
    page.padding = 0
    try:
        page.width = 1280
        page.height = 820
    except Exception:
        pass

    # 2. Inicialización de la Base de Datos Maestra de Autenticación (auth.db)
    init_auth_db()
    auth_controller = AuthController()

    # Referencia al gestor de escáner de la sesión activa para liberarlo al cerrar sesión
    active_barcode_manager: Optional[BarcodeManager] = None

    # 3. Sistema de Seguridad Global (Error Boundary) para evitar bloqueos
    def on_global_error(e: ft.ControlEvent) -> None:
        error_msg = str(e.data) if hasattr(e, "data") else str(e)
        print(f"[SEGURIDAD GLOBAL] Excepción interceptada: {error_msg}")
        try:
            rescue_dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.SHIELD_ROUNDED, color=PastelTheme.PRIMARY, size=26),
                    ft.Text("Protección del Sistema", weight=ft.FontWeight.BOLD),
                ]),
                content=ft.Container(
                    width=420,
                    content=ft.Column(
                        tight=True,
                        spacing=10,
                        controls=[
                            ft.Text(
                                "Se interceptó un evento inesperado. Tu sesión y datos están a salvo.",
                                size=13,
                            ),
                            ft.Container(
                                bgcolor=PastelTheme.SURFACE_VARIANT,
                                padding=10,
                                border_radius=8,
                                content=ft.Text(
                                    error_msg,
                                    size=11,
                                    color=PastelTheme.TEXT_SECONDARY,
                                    selectable=True,
                                ),
                            ),
                        ],
                    ),
                ),
                actions=[
                    ft.FilledButton(
                        "Continuar en la Aplicación",
                        bgcolor=PastelTheme.PRIMARY,
                        color=PastelTheme.TEXT_ON_PRIMARY,
                        on_click=lambda _: page.pop_dialog(),
                    )
                ],
            )
            page.show_dialog(rescue_dialog)
        except Exception as rescue_err:
            print(f"[SEGURIDAD GLOBAL] Error mostrando alerta de rescate: {rescue_err}")

    page.on_error = on_global_error

    # Contenedor raíz con transición suave entre Login y Aplicación Principal
    root_container = ft.Container(
        expand=True,
        bgcolor=PastelTheme.BG_LIGHT,
        animate_opacity=250,
    )

    # 4. Ruteo y Transición de Sesión Multi-Tenant
    def handle_logout() -> None:
        """
        Cierra la sesión activa:
        - Detiene el lector de código de barras.
        - Destruye la conexión SQLite local del usuario (tenant_{username}.db).
        - Devuelve al usuario a la vista de Login ocultando el menú lateral y el Dashboard.
        """
        nonlocal active_barcode_manager
        if active_barcode_manager is not None:
            try:
                active_barcode_manager.stop()
            except Exception:
                pass
            active_barcode_manager = None

        page.on_keyboard_event = None
        auth_controller.logout()
        page.title = APP_TITLE

        auth_view.reset_for_login("Sesión finalizada. Conexión a base de datos local cerrada.")
        root_container.content = auth_view
        page.update()

    def handle_auth_success(user_data: Dict[str, Any]) -> None:
        """
        Tras una autenticación o registro exitoso:
        - El AuthController ya conectó SQLAlchemy a 'tenant_{username}.db'.
        - Instancia los controladores y vistas aisladas para este usuario.
        - Realiza la transición hacia el Dashboard principal (con menú lateral visible).
        """
        nonlocal active_barcode_manager
        if active_barcode_manager is not None:
            try:
                active_barcode_manager.stop()
            except Exception:
                pass

        username = user_data.get("username", "")
        page.title = f"{APP_TITLE} — @{username} ({user_data.get('tenant_db', '')})"

        # Instanciar hardware y controladores sobre la conexión tenant_{username}.db activa
        barcode_manager = BarcodeManager(mode=ScannerMode.KEYBOARD_WEDGE, camera_index=1)
        active_barcode_manager = barcode_manager

        pos_controller = PosController()
        inventory_controller = InventoryController()
        customer_controller = CustomerController()
        dashboard_controller = DashboardController()

        # Construir vistas para el tenant autenticado
        dashboard_view = DashboardView(dashboard_controller)
        pos_view = PosView(pos_controller, customer_controller, barcode_manager)
        inventory_view = InventoryView(inventory_controller, barcode_manager, pos_view)
        in_out_view = InOutView(
            inventory_controller,
            on_inventory_changed=lambda: (inventory_view.load_products(), dashboard_view.refresh_data()),
        )
        cartera_view = CarteraView(customer_controller)
        cash_flow_view = CashFlowView(dashboard_controller)

        def on_barcode_scanned(code: str) -> None:
            print(f"[Hardware Barcode] Código detectado: {code}")
            if inventory_view.active_barcode_callback is not None:
                inventory_view.active_barcode_callback(code)
                return
            pos_view.handle_external_scan(code)

        barcode_manager.subscribe(on_barcode_scanned)
        barcode_manager.start()

        def on_keyboard_event(e: ft.KeyboardEvent) -> None:
            barcode_manager.handle_keyboard_event(e.key)

        page.on_keyboard_event = on_keyboard_event

        main_layout = MainLayout(
            dashboard_view=dashboard_view,
            pos_view=pos_view,
            inventory_view=inventory_view,
            in_out_view=in_out_view,
            cartera_view=cartera_view,
            cash_flow_view=cash_flow_view,
            current_username=username,
            on_logout=handle_logout,
        )

        root_container.content = main_layout
        page.update()

    # 5. Al iniciar la aplicación, la ÚNICA vista renderizada es el Login
    auth_view = AuthView(
        auth_controller=auth_controller,
        on_auth_success=handle_auth_success,
    )
    root_container.content = auth_view
    page.add(root_container)

    # Manejo de cierre seguro para liberar cámara y conexiones
    def on_close() -> None:
        if active_barcode_manager is not None:
            active_barcode_manager.stop()
        auth_controller.logout()

    page.on_close = on_close


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
