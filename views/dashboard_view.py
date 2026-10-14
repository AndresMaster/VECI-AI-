import flet as ft
from config import PastelTheme
from controllers import DashboardController
from services.chart_service import ChartService
from views.theme import create_card, create_metric_tile, create_badge, safe_update

class DashboardView(ft.Container):
    """
    Vista del Dashboard:
    - KPIs financieros en tiempo real.
    - Gráficos integrados de Matplotlib (Barras y Torta).
    - Alertas destacadas de productos con stock bajo.
    """
    def __init__(self, dashboard_controller: DashboardController):
        super().__init__(expand=True)
        self.controller = dashboard_controller
        self.padding = 24
        
        # Contenedores dinámicos
        self.kpi_row = ft.Row(spacing=16)
        self.bar_chart_img = ft.Image(src=b"", fit=ft.BoxFit.CONTAIN, expand=True)
        self.pie_chart_img = ft.Image(src=b"", fit=ft.BoxFit.CONTAIN, expand=True)
        self.alerts_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

        self.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
            controls=[
                # Header
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text("Dashboard Ejecutivo", size=24, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                ft.Text("Métricas de rendimiento, valoración de existencias y alertas de reposición", size=13, color=PastelTheme.TEXT_SECONDARY)
                            ]
                        ),
                        ft.FilledButton(
                            content=ft.Row([ft.Icon(ft.Icons.REFRESH_ROUNDED, size=18), ft.Text("Actualizar")]),
                            style=ft.ButtonStyle(
                                bgcolor=PastelTheme.PRIMARY_PASTEL,
                                color=PastelTheme.PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                elevation=0
                            ),
                            on_click=lambda _: self.refresh_data()
                        )
                    ]
                ),

                # KPI Metrics
                self.kpi_row,

                # Charts Section
                ft.Row(
                    spacing=16,
                    controls=[
                        create_card(
                            content=ft.Column(
                                spacing=10,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.Icons.BAR_CHART_ROUNDED, size=20, color=PastelTheme.PRIMARY),
                                        ft.Text("Comparativa Financiera", weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY)
                                    ]),
                                    self.bar_chart_img
                                ]
                            ),
                            expand=True,
                            padding=16
                        ),
                        create_card(
                            content=ft.Column(
                                spacing=10,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.Icons.PIE_CHART_ROUNDED, size=20, color=PastelTheme.ACCENT_MINT),
                                        ft.Text("Distribución por Categorías", weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY)
                                    ]),
                                    self.pie_chart_img
                                ]
                            ),
                            expand=True,
                            padding=16
                        )
                    ]
                ),

                # Low Stock Alerts Card
                create_card(
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=PastelTheme.ACCENT_AMBER, size=22),
                                        ft.Text("Alertas de Stock Bajo / Reorden", size=16, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY)
                                    ]),
                                    create_badge("Atención Prioritaria", PastelTheme.AMBER_PASTEL, PastelTheme.ACCENT_AMBER)
                                ]
                            ),
                            ft.Divider(color=PastelTheme.BORDER_LIGHT, height=1),
                            self.alerts_column
                        ]
                    ),
                    padding=20
                )
            ]
        )

        self.refresh_data()

    def refresh_data(self) -> None:
        """Recalcula métricas, genera gráficos y actualiza los componentes visuales."""
        kpis = self.controller.get_kpis()

        # 1. KPIs
        self.kpi_row.controls = [
            create_metric_tile(
                title="Costo de Inventario",
                value=f"${kpis['total_inventory_cost']:,.0f}",
                icon=ft.Icons.INVENTORY_2_ROUNDED,
                bg_pastel=PastelTheme.PRIMARY_PASTEL,
                icon_color=PastelTheme.PRIMARY,
                subtitle="Capital invertido en bodega"
            ),
            create_metric_tile(
                title="Venta Proyectada",
                value=f"${kpis['total_inventory_retail']:,.0f}",
                icon=ft.Icons.POINT_OF_SALE_ROUNDED,
                bg_pastel=PastelTheme.SKY_PASTEL,
                icon_color=PastelTheme.ACCENT_SKY,
                subtitle="Valor comercial total"
            ),
            create_metric_tile(
                title="Utilidad Estimada",
                value=f"${kpis['total_potential_profit']:,.0f}",
                icon=ft.Icons.TRENDING_UP_ROUNDED,
                bg_pastel=PastelTheme.MINT_PASTEL,
                icon_color=PastelTheme.ACCENT_MINT,
                subtitle="Margen bruto proyectado"
            ),
            create_metric_tile(
                title="Alertas de Stock",
                value=str(kpis['low_stock_count']),
                icon=ft.Icons.NOTIFICATION_IMPORTANT_ROUNDED,
                bg_pastel=PastelTheme.CORAL_PASTEL,
                icon_color=PastelTheme.ACCENT_CORAL,
                subtitle="Productos bajo mínimo"
            ),
        ]

        # 2. Gráficos de Matplotlib
        bar_bytes = ChartService.generate_valuation_bar_chart(
            kpis['total_inventory_cost'],
            kpis['total_inventory_retail'],
            kpis['total_potential_profit'],
            as_bytes=True
        )
        self.bar_chart_img.src = bar_bytes

        pie_bytes = ChartService.generate_category_pie_chart(kpis['categories_distribution'], as_bytes=True)
        self.pie_chart_img.src = pie_bytes

        # 3. Lista de Alertas
        low_stock_items = kpis['low_stock_items']
        if not low_stock_items:
            self.alerts_column.controls = [
                ft.Container(
                    padding=16,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, color=PastelTheme.ACCENT_MINT, size=20),
                            ft.Text("Todos los productos cuentan con niveles óptimos de stock.", color=PastelTheme.TEXT_SECONDARY)
                        ]
                    )
                )
            ]
        else:
            self.alerts_column.controls = [
                ft.Container(
                    bgcolor=PastelTheme.SURFACE_VARIANT,
                    border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row([
                                ft.Container(
                                    content=ft.Text(f"{item['stock']} uds", size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.ACCENT_CORAL),
                                    bgcolor=PastelTheme.CORAL_PASTEL,
                                    border_radius=8,
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=4)
                                ),
                                ft.Column(
                                    spacing=2,
                                    controls=[
                                        ft.Text(item.get("display_name", item["name"]), weight=ft.FontWeight.BOLD, size=13, color=PastelTheme.TEXT_PRIMARY),
                                        ft.Text(f"Código: {item['barcode']} | Categoría: {item['category']}", size=11, color=PastelTheme.TEXT_MUTED)
                                    ]
                                )
                            ]),
                            ft.Text(f"Mínimo requerido: {item['min_stock']} uds", size=12, color=PastelTheme.TEXT_SECONDARY)
                        ]
                    )
                ) for item in low_stock_items
            ]

        safe_update(self)
