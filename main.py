import flet as ft
from config import APP_TITLE, PastelTheme
from database import init_db
from services.barcode_manager import BarcodeManager, ScannerMode
from controllers import (
    PosController,
    InventoryController,
    CustomerController,
    DashboardController
)
from views import (
    DashboardView,
    PosView,
    InventoryView,
    CarteraView,
    MainLayout
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

    # 2. Inicialización de Base de Datos y Datos Semilla
    init_db(seed_sample_data=True)

    # 3. Inicialización del Administrador de Códigos de Barras
    barcode_manager = BarcodeManager(mode=ScannerMode.KEYBOARD_WEDGE)

    # 4. Inicialización de Controladores (Patrón MVC)
    pos_controller = PosController()
    inventory_controller = InventoryController()
    customer_controller = CustomerController()
    dashboard_controller = DashboardController()

    # 5. Enlace desacoplado de hardware con lógica de negocio
    # Cualquier lectura (USB, Cámara o Entrada Manual) agrega automáticamente al POS
    def on_barcode_scanned(code: str) -> None:
        print(f"[Sistema POS] Código recibido desde hardware: {code}")
        success, msg = pos_controller.add_product_by_barcode(code)
        if not success:
            print(f"[Sistema POS] Aviso de escaneo: {msg}")

    barcode_manager.subscribe(on_barcode_scanned)
    barcode_manager.start()

    # Captura global de teclado para escáneres USB tipo 'Keyboard Wedge'
    def on_keyboard_event(e: ft.KeyboardEvent) -> None:
        barcode_manager.handle_keyboard_event(e.key)

    page.on_keyboard_event = on_keyboard_event

    # 5.1 Sistema de Seguridad Global (Error Boundary) para evitar bloqueos
    def on_global_error(e: ft.ControlEvent) -> None:
        error_msg = str(e.data) if hasattr(e, "data") else str(e)
        print(f"[SEGURIDAD GLOBAL] Excepción interceptada: {error_msg}")
        try:
            rescue_dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.SHIELD_ROUNDED, color=PastelTheme.PRIMARY, size=26),
                    ft.Text("Protección del Sistema", weight=ft.FontWeight.BOLD)
                ]),
                content=ft.Container(
                    width=420,
                    content=ft.Column(
                        tight=True,
                        spacing=10,
                        controls=[
                            ft.Text("Se interceptó un evento inesperado. Tu sesión y datos están a salvo.", size=13),
                            ft.Container(
                                bgcolor=PastelTheme.SURFACE_VARIANT,
                                padding=10,
                                border_radius=8,
                                content=ft.Text(error_msg, size=11, color=PastelTheme.TEXT_SECONDARY, selectable=True)
                            )
                        ]
                    )
                ),
                actions=[
                    ft.FilledButton(
                        "Continuar en la Aplicación",
                        bgcolor=PastelTheme.PRIMARY,
                        color=PastelTheme.TEXT_ON_PRIMARY,
                        on_click=lambda _: page.pop_dialog()
                    )
                ]
            )
            page.show_dialog(rescue_dialog)
        except Exception as rescue_err:
            print(f"[SEGURIDAD GLOBAL] Error mostrando alerta de rescate: {rescue_err}")

    page.on_error = on_global_error

    # 6. Construcción de Vistas
    dashboard_view = DashboardView(dashboard_controller)
    pos_view = PosView(pos_controller, customer_controller, barcode_manager)
    inventory_view = InventoryView(inventory_controller)
    cartera_view = CarteraView(customer_controller)

    # 7. Layout Principal con Navegación Persistente
    main_layout = MainLayout(
        dashboard_view=dashboard_view,
        pos_view=pos_view,
        inventory_view=inventory_view,
        cartera_view=cartera_view
    )

    page.add(main_layout)

    # Manejo de cierre seguro para liberar cámara o hilos en ejecución
    def on_close():
        barcode_manager.stop()

    page.on_close = on_close

if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
