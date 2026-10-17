import flet as ft
from typing import Optional, Callable
from config import PastelTheme, APP_TITLE, APP_VERSION
from views.dashboard_view import DashboardView
from views.inventory_view import InventoryView
from views.pos_view import PosView
from views.cartera_view import CarteraView
from views.cash_flow_view import CashFlowView


class MainLayout(ft.Row):
    """
    Layout maestro con menú de navegación lateral persistente.
    - Tras iniciar sesión, abre directamente en el Dashboard principal (índice 0).
    - Preserva el estado en memoria de todas las vistas del usuario activo.
    - Incluye indicador de cuenta Multi-Tenant y botón 'Cerrar Sesión' en el menú lateral.
    """
    def __init__(
        self,
        dashboard_view: DashboardView,
        pos_view: PosView,
        inventory_view: InventoryView,
        cartera_view: CarteraView,
        cash_flow_view: Optional[CashFlowView] = None,
        current_username: str = "",
        on_logout: Optional[Callable[[], None]] = None,
    ):
        super().__init__(expand=True, spacing=0)
        self.on_logout = on_logout
        self.current_username = current_username

        self.views = [
            dashboard_view,
            pos_view,
            inventory_view,
            cartera_view,
        ]
        if cash_flow_view is not None:
            self.views.append(cash_flow_view)

        # Tras una autenticación exitosa, arrancamos en el Dashboard principal (índice 0)
        self.current_index = 0

        # Contenedor dinámico del área de contenido
        self.content_container = ft.Container(
            content=self.views[self.current_index],
            expand=True,
            bgcolor=PastelTheme.BG_LIGHT
        )

        destinations = [
            ft.NavigationRailDestination(
                icon=ft.Icons.DASHBOARD_OUTLINED,
                selected_icon=ft.Icons.DASHBOARD_ROUNDED,
                label="Dashboard",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.RECEIPT_LONG_OUTLINED,
                selected_icon=ft.Icons.RECEIPT_LONG_ROUNDED,
                label="Facturación",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.INVENTORY_2_OUTLINED,
                selected_icon=ft.Icons.INVENTORY_2_ROUNDED,
                label="Inventario",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.PEOPLE_ALT_OUTLINED,
                selected_icon=ft.Icons.PEOPLE_ALT_ROUNDED,
                label="Cartera",
            ),
        ]

        if cash_flow_view is not None:
            destinations.append(
                ft.NavigationRailDestination(
                    icon=ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
                    selected_icon=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                    label="Flujo de Caja",
                )
            )

        # Sección inferior del menú lateral: Usuario activo y botón de Cerrar Sesión
        trailing_section = ft.Container(
            padding=ft.Padding.only(top=16, bottom=20, left=8, right=8),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                controls=[
                    ft.Divider(height=1, color=PastelTheme.BORDER_LIGHT),
                    *(
                        [
                            ft.Container(
                                bgcolor=PastelTheme.SURFACE_VARIANT,
                                border_radius=10,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Icon(ft.Icons.VERIFIED_USER_ROUNDED, size=14, color=PastelTheme.ACCENT_MINT),
                                        ft.Text(
                                            self.current_username,
                                            size=11,
                                            weight=ft.FontWeight.BOLD,
                                            color=PastelTheme.TEXT_PRIMARY,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                    ],
                                ),
                            )
                        ]
                        if self.current_username
                        else []
                    ),
                    ft.Container(
                        bgcolor=PastelTheme.CORAL_PASTEL,
                        border_radius=12,
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        border=ft.Border.all(1, PastelTheme.ACCENT_CORAL),
                        ink=True,
                        tooltip="Cerrar sesión y desconectar base de datos del usuario",
                        on_click=lambda _: self._handle_logout_click(),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=3,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=20, color=PastelTheme.ACCENT_CORAL),
                                ft.Text(
                                    "Cerrar Sesión",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=PastelTheme.ACCENT_CORAL,
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        # Menú lateral persistente estilo NavigationRail moderno
        self.nav_rail = ft.NavigationRail(
            selected_index=self.current_index,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=110,
            min_extended_width=200,
            bgcolor=PastelTheme.SURFACE_WHITE,
            leading=ft.Container(
                padding=ft.Padding.only(top=16, bottom=12),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                    controls=[
                        ft.Container(
                            bgcolor=PastelTheme.PRIMARY_PASTEL,
                            border_radius=12,
                            padding=10,
                            content=ft.Icon(ft.Icons.POINT_OF_SALE_ROUNDED, size=28, color=PastelTheme.PRIMARY)
                        ),
                        ft.Text("VECI_AI", size=13, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                        ft.Text(f"v{APP_VERSION}", size=10, color=PastelTheme.TEXT_MUTED)
                    ]
                )
            ),
            trailing=trailing_section,
            group_alignment=-0.85,
            destinations=destinations,
            on_change=self._on_navigation_change
        )

        self.controls = [
            ft.Container(
                content=self.nav_rail,
                border=ft.Border.only(right=ft.BorderSide(1, PastelTheme.BORDER_LIGHT))
            ),
            self.content_container
        ]

    def _handle_logout_click(self) -> None:
        if self.on_logout is not None:
            self.on_logout()

    def _on_navigation_change(self, e) -> None:
        new_index = e.control.selected_index
        self.current_index = new_index

        target_view = self.views[new_index]

        # Si regresamos a Dashboard, refrescamos métricas según el filtro temporal activo
        if isinstance(target_view, DashboardView):
            target_view.refresh_data()
        # Si regresamos a Inventario, refrescamos tabla
        elif isinstance(target_view, InventoryView):
            target_view.load_products()
        # Si regresamos a Cartera, refrescamos clientes
        elif isinstance(target_view, CarteraView):
            target_view.load_data()
        # Si regresamos a POS, el borrador sigue intacto en target_view.pos!
        elif isinstance(target_view, PosView):
            target_view.on_cart_changed()
        # Si navegamos a Flujo de Caja / Transacciones, refrescamos el Libro Mayor
        elif isinstance(target_view, CashFlowView):
            target_view.load_transactions()

        self.content_container.content = target_view
        self.content_container.update()
