from datetime import datetime
from typing import Optional
import flet as ft

from config import PastelTheme
from controllers import DashboardController
from services.chart_service import ChartService
from views.date_filter_bar import DateRangeFilterBar
from views.theme import create_card, create_metric_tile, create_badge, safe_update


class DashboardView(ft.Container):
    """
    Vista del Dashboard Ejecutivo con Inteligencia Financiera Temporal:
    - Filtrado Temporal Avanzado (Estilo YouTube Studio / Google Calendar).
    - KPIs financieros recalculados dinámicamente según el periodo (Costos, Ventas Proyectadas,
      Ventas Realizadas, Egresos y Utilidad Real).
    - Gráficos integrados de Matplotlib (Barras y Torta) dinámicos por rango de fechas.
    - Alertas destacadas de productos con stock bajo.
    """

    def __init__(self, dashboard_controller: DashboardController):
        super().__init__(expand=True)
        self.controller = dashboard_controller
        self.padding = 24

        # Componente de Filtro Temporal Avanzado (Estilo YouTube Studio)
        self.date_filter_bar = DateRangeFilterBar(
            dashboard_controller=self.controller,
            on_range_changed=self._on_date_range_changed,
        )

        # Suscribir a cambios del filtro para mantener sincronización con Libro Mayor
        self.controller.subscribe_filter_change(self._on_external_filter_sync)

        # Contenedores dinámicos
        self.kpi_row = ft.Row(spacing=14)
        self.bar_chart_img = ft.Image(src=b"", fit=ft.BoxFit.CONTAIN, expand=True)
        self.pie_chart_img = ft.Image(src=b"", fit=ft.BoxFit.CONTAIN, expand=True)
        self.alerts_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

        self.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=18,
            controls=[
                # Header
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text(
                                    "Dashboard Ejecutivo e Inteligencia Financiera",
                                    size=24,
                                    weight=ft.FontWeight.BOLD,
                                    color=PastelTheme.TEXT_PRIMARY,
                                ),
                                ft.Text(
                                    "Métricas de rendimiento por periodo, valoración, egresos y alertas de reposición",
                                    size=13,
                                    color=PastelTheme.TEXT_SECONDARY,
                                ),
                            ],
                        ),
                        ft.FilledButton(
                            content=ft.Row([ft.Icon(ft.Icons.REFRESH_ROUNDED, size=18), ft.Text("Actualizar")]),
                            style=ft.ButtonStyle(
                                bgcolor=PastelTheme.PRIMARY_PASTEL,
                                color=PastelTheme.PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                elevation=0,
                            ),
                            on_click=lambda _: self.refresh_data(),
                        ),
                    ],
                ),

                # Barra de Filtrado Temporal Avanzado (YouTube Studio / Google Calendar)
                self.date_filter_bar,

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
                                        ft.Text(
                                            "Comparativa Financiera del Periodo",
                                            weight=ft.FontWeight.BOLD,
                                            color=PastelTheme.TEXT_PRIMARY,
                                        ),
                                    ]),
                                    self.bar_chart_img,
                                ],
                            ),
                            expand=True,
                            padding=16,
                        ),
                        create_card(
                            content=ft.Column(
                                spacing=10,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.Icons.PIE_CHART_ROUNDED, size=20, color=PastelTheme.ACCENT_MINT),
                                        ft.Text(
                                            "Distribución por Categorías del Periodo",
                                            weight=ft.FontWeight.BOLD,
                                            color=PastelTheme.TEXT_PRIMARY,
                                        ),
                                    ]),
                                    self.pie_chart_img,
                                ],
                            ),
                            expand=True,
                            padding=16,
                        ),
                    ],
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
                                        ft.Icon(
                                            ft.Icons.WARNING_AMBER_ROUNDED,
                                            color=PastelTheme.ACCENT_AMBER,
                                            size=22,
                                        ),
                                        ft.Text(
                                            "Alertas de Stock Bajo / Reorden",
                                            size=16,
                                            weight=ft.FontWeight.BOLD,
                                            color=PastelTheme.TEXT_PRIMARY,
                                        ),
                                    ]),
                                    create_badge(
                                        "Atención Prioritaria",
                                        PastelTheme.AMBER_PASTEL,
                                        PastelTheme.ACCENT_AMBER,
                                    ),
                                ],
                            ),
                            ft.Divider(color=PastelTheme.BORDER_LIGHT, height=1),
                            self.alerts_column,
                        ],
                    ),
                    padding=20,
                ),
            ],
        )

        self.refresh_data()

    def _on_date_range_changed(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        _label: str,
    ) -> None:
        self.refresh_data(start_date=start_date, end_date=end_date)

    def _on_external_filter_sync(self) -> None:
        self.date_filter_bar.sync_from_controller()
        self.refresh_data()

    def refresh_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> None:
        """
        Recalcula métricas para el rango (start_date, end_date), regenera gráficos
        y actualiza los componentes visuales.
        """
        self.date_filter_bar.sync_from_controller()
        if start_date is None and end_date is None:
            start_date, end_date, _ = self.controller.get_active_date_range()

        kpis = self.controller.get_kpis(start_date=start_date, end_date=end_date)

        real_profit = kpis["total_realized_profit"]
        profit_bg = PastelTheme.MINT_PASTEL if real_profit >= 0 else PastelTheme.CORAL_PASTEL
        profit_color = PastelTheme.ACCENT_MINT if real_profit >= 0 else PastelTheme.ACCENT_CORAL

        # 1. KPIs Dinámicos del Periodo
        self.kpi_row.controls = [
            create_metric_tile(
                title="Costos y Egresos",
                value=f"${kpis['period_cost']:,.0f}",
                icon=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                bg_pastel=PastelTheme.CORAL_PASTEL,
                icon_color=PastelTheme.ACCENT_CORAL,
                subtitle=(
                    f"Prov: ${kpis['supplier_expenses']:,.0f} | "
                    f"Gastos: ${kpis['general_expenses']:,.0f}"
                ),
            ),
            create_metric_tile(
                title="Ventas Proyectadas",
                value=f"${kpis['period_projected_sales']:,.0f}",
                icon=ft.Icons.POINT_OF_SALE_ROUNDED,
                bg_pastel=PastelTheme.SKY_PASTEL,
                icon_color=PastelTheme.ACCENT_SKY,
                subtitle=(
                    f"Facturado: ${kpis['total_realized_sales']:,.0f} "
                    f"({kpis['total_invoices_count']} ventas)"
                ),
            ),
            create_metric_tile(
                title="Utilidad Real Neta",
                value=f"${real_profit:,.0f}",
                icon=ft.Icons.TRENDING_UP_ROUNDED if real_profit >= 0 else ft.Icons.TRENDING_DOWN_ROUNDED,
                bg_pastel=profit_bg,
                icon_color=profit_color,
                subtitle=(
                    f"Margen ventas: ${kpis['gross_sales_profit']:,.0f} | "
                    f"Flujo: ${kpis['net_cash_flow']:,.0f}"
                ),
            ),
            create_metric_tile(
                title="Alertas de Stock",
                value=str(kpis["low_stock_count"]),
                icon=ft.Icons.NOTIFICATION_IMPORTANT_ROUNDED,
                bg_pastel=PastelTheme.AMBER_PASTEL,
                icon_color=PastelTheme.ACCENT_AMBER,
                subtitle=f"Bodega: ${kpis['total_inventory_cost']:,.0f} inv.",
            ),
        ]

        # 2. Gráficos de Matplotlib recalculados sólo para el periodo seleccionado
        bar_bytes = ChartService.generate_valuation_bar_chart(
            cost_val=kpis["period_cost"],
            retail_val=kpis["period_projected_sales"],
            profit_val=kpis["total_realized_profit"],
            realized_sales_val=kpis["total_realized_sales"],
            period_label=kpis["period_label"],
            as_bytes=True,
        )
        self.bar_chart_img.src = bar_bytes

        pie_bytes = ChartService.generate_category_pie_chart(
            categories_dict=kpis["categories_distribution"],
            period_label=kpis["period_label"],
            as_bytes=True,
        )
        self.pie_chart_img.src = pie_bytes

        # 3. Lista de Alertas de Stock Bajo
        low_stock_items = kpis["low_stock_items"]
        if not low_stock_items:
            self.alerts_column.controls = [
                ft.Container(
                    padding=16,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                                color=PastelTheme.ACCENT_MINT,
                                size=20,
                            ),
                            ft.Text(
                                "Todos los productos cuentan con niveles óptimos de stock.",
                                color=PastelTheme.TEXT_SECONDARY,
                            ),
                        ],
                    ),
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
                                    content=ft.Text(
                                        f"{item['stock']} uds",
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=PastelTheme.ACCENT_CORAL,
                                    ),
                                    bgcolor=PastelTheme.CORAL_PASTEL,
                                    border_radius=8,
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                ),
                                ft.Column(
                                    spacing=2,
                                    controls=[
                                        ft.Text(
                                            item.get("display_name", item["name"]),
                                            weight=ft.FontWeight.BOLD,
                                            size=13,
                                            color=PastelTheme.TEXT_PRIMARY,
                                        ),
                                        ft.Text(
                                            f"Código: {item['barcode']} | Categoría: {item['category']}",
                                            size=11,
                                            color=PastelTheme.TEXT_MUTED,
                                        ),
                                    ],
                                ),
                            ]),
                            ft.Text(
                                f"Mínimo requerido: {item['min_stock']} uds",
                                size=12,
                                color=PastelTheme.TEXT_SECONDARY,
                            ),
                        ],
                    ),
                )
                for item in low_stock_items
            ]

        safe_update(self)
