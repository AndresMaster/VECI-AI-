from datetime import datetime
from typing import Optional
import flet as ft

from config import PastelTheme
from controllers import DashboardController
from views.date_filter_bar import DateRangeFilterBar
from views.theme import create_card, create_metric_tile, create_badge, safe_update


class CashFlowView(ft.Container):
    """
    Vista del Módulo de Libro Mayor y Flujo de Caja (Detalle Transaccional).
    - Consolida y ordena cronológicamente por Fecha y Hora exacta (DateTime):
      1. Ventas realizadas (Ingresos - Color Verde).
      2. Pagos a proveedores (Egresos de inventario - Color Rojo).
      3. Gastos generales (Egresos fijos/variables como servicios públicos, nómina, varios - Color Rojo).
    - Reacciona en tiempo real al Filtro Temporal Avanzado (estilo YouTube Studio / Google Calendar).
    - Permite registrar nuevos Gastos Generales y Pagos a Proveedores.
    """

    def __init__(self, dashboard_controller: DashboardController):
        super().__init__(expand=True)
        self.controller = dashboard_controller
        self.padding = 24

        self.type_filter: str = "ALL"
        self.sort_descending: bool = True

        # Barra de Filtrado Temporal Avanzado sincronizada con el Dashboard
        self.date_filter_bar = DateRangeFilterBar(
            dashboard_controller=self.controller,
            on_range_changed=self._on_date_range_changed,
        )
        self.controller.subscribe_filter_change(self._on_external_filter_sync)

        # Buscador y filtros del Libro Mayor
        self.search_field = ft.TextField(
            hint_text="Buscar por cliente, factura, proveedor, categoría o descripción...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=PastelTheme.BORDER_RADIUS_INPUT,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_color=PastelTheme.BORDER_LIGHT,
            dense=True,
            expand=True,
            on_change=lambda _: self.load_transactions(),
        )

        self.type_dropdown = ft.Dropdown(
            label="Tipo de Movimiento",
            value="ALL",
            width=230,
            dense=True,
            border_radius=10,
            bgcolor=PastelTheme.SURFACE_WHITE,
            text_size=13,
            options=[
                ft.dropdown.Option("ALL", "Todos los movimientos"),
                ft.dropdown.Option("VENTA", "Ingresos (Ventas POS)"),
                ft.dropdown.Option("PROVEEDOR", "Egresos (Pagos Proveedor)"),
                ft.dropdown.Option("GASTO", "Egresos (Gastos Generales)"),
            ],
            on_select=self._on_type_filter_change,
        )

        self.sort_btn_text = ft.Text("Más recientes", size=12)
        self.sort_btn = ft.OutlinedButton(
            content=ft.Row(
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.SWAP_VERT_ROUNDED, size=16, color=PastelTheme.PRIMARY),
                    self.sort_btn_text,
                ],
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            ),
            tooltip="Cambiar orden cronológico (Fecha y Hora)",
            on_click=self._toggle_sort_direction,
        )

        # Resumen KPI del periodo filtrado
        self.summary_kpi_row = ft.Row(spacing=14)

        # Tabla de Datos (DataTable) unificada del Libro Mayor
        self.data_table = ft.DataTable(
            expand=True,
            heading_row_color=PastelTheme.SURFACE_VARIANT,
            heading_row_height=44,
            data_row_min_height=48,
            data_row_max_height=64,
            column_spacing=24,
            horizontal_lines=ft.BorderSide(1, PastelTheme.BORDER_LIGHT),
            columns=[
                ft.DataColumn(
                    ft.Text("Fecha", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY)
                ),
                ft.DataColumn(
                    ft.Text("Hora", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY)
                ),
                ft.DataColumn(
                    ft.Text("Tipo", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY)
                ),
                ft.DataColumn(
                    ft.Text(
                        "Descripción / Cliente / Proveedor",
                        weight=ft.FontWeight.BOLD,
                        size=12,
                        color=PastelTheme.TEXT_SECONDARY,
                    )
                ),
                ft.DataColumn(
                    ft.Text("Monto", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                    numeric=True,
                ),
                ft.DataColumn(
                    ft.Text("Acciones", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY)
                ),
            ],
            rows=[],
        )

        self.empty_state_container = ft.Container(
            visible=False,
            padding=36,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=42, color=PastelTheme.TEXT_MUTED),
                    ft.Text(
                        "No se encontraron transacciones en el periodo seleccionado.",
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=PastelTheme.TEXT_SECONDARY,
                    ),
                    ft.Text(
                        "Prueba ampliando el rango de fechas o registra un nuevo movimiento.",
                        size=12,
                        color=PastelTheme.TEXT_MUTED,
                    ),
                ],
            ),
        )

        self.records_count_badge = create_badge(
            "0 transacciones",
            PastelTheme.PRIMARY_PASTEL,
            PastelTheme.PRIMARY,
        )

        self.content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Header con botones para registrar Gastos Generales y Pagos a Proveedores
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text(
                                    "Libro Mayor y Flujo de Caja (Transacciones)",
                                    size=24,
                                    weight=ft.FontWeight.BOLD,
                                    color=PastelTheme.TEXT_PRIMARY,
                                ),
                                ft.Text(
                                    "Consolidado cronológico exacto de Ventas (Ingresos), Pagos a Proveedores y Gastos Generales",
                                    size=13,
                                    color=PastelTheme.TEXT_SECONDARY,
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.FilledButton(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.RECEIPT_ROUNDED, size=18),
                                        ft.Text("Registrar Gasto General"),
                                    ]),
                                    style=ft.ButtonStyle(
                                        bgcolor=PastelTheme.ACCENT_CORAL,
                                        color=PastelTheme.TEXT_ON_PRIMARY,
                                        shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                                    ),
                                    on_click=lambda _: self.show_create_expense_modal(),
                                ),
                                ft.OutlinedButton(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.LOCAL_SHIPPING_ROUNDED, size=18),
                                        ft.Text("Registrar Pago Proveedor"),
                                    ]),
                                    style=ft.ButtonStyle(
                                        color=PastelTheme.PRIMARY,
                                        shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                                    ),
                                    on_click=lambda _: self.show_create_supplier_payment_modal(),
                                ),
                            ],
                        ),
                    ],
                ),

                # Filtro Temporal Avanzado (YouTube Studio / Google Calendar)
                self.date_filter_bar,

                # Resumen KPI del Flujo de Caja en el periodo
                self.summary_kpi_row,

                # Barra de búsqueda y filtro por tipo de transacción
                create_card(
                    padding=10,
                    content=ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            self.search_field,
                            self.type_dropdown,
                            self.sort_btn,
                            self.records_count_badge,
                        ],
                    ),
                ),

                # Tarjeta con la Tabla de Datos Unificada
                create_card(
                    expand=True,
                    padding=12,
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[
                            ft.Row(
                                controls=[self.data_table],
                                scroll=ft.ScrollMode.AUTO,
                            ),
                            self.empty_state_container,
                        ],
                    ),
                ),
            ],
        )

        self.load_transactions()

    def _on_date_range_changed(
        self,
        _start_date: Optional[datetime],
        _end_date: Optional[datetime],
        _label: str,
    ) -> None:
        self.load_transactions()

    def _on_external_filter_sync(self) -> None:
        self.date_filter_bar.sync_from_controller()
        self.load_transactions()

    def _on_type_filter_change(self, e) -> None:
        self.type_filter = self.type_dropdown.value or "ALL"
        self.load_transactions()

    def _toggle_sort_direction(self, _=None) -> None:
        self.sort_descending = not self.sort_descending
        self.sort_btn_text.value = "Más recientes" if self.sort_descending else "Más antiguos"
        self.load_transactions()

    def load_transactions(self) -> None:
        """
        Consulta el Libro Mayor consolidado para el rango temporal activo y renderiza
        la tabla de datos y los totales de flujo de caja.
        """
        self.date_filter_bar.sync_from_controller()
        start_dt, end_dt, _ = self.controller.get_active_date_range()
        query_text = self.search_field.value or ""

        ledger = self.controller.get_ledger_transactions(
            start_date=start_dt,
            end_date=end_dt,
            type_filter=self.type_filter,
            search_query=query_text,
            descending=self.sort_descending,
        )

        # 1. Actualizar KPIs de Flujo de Caja del Periodo
        ingresos = ledger["total_ingresos"]
        pagos_prov = ledger["total_pagos_proveedores"]
        gastos_gen = ledger["total_gastos_generales"]
        balance = ledger["balance_neto"]

        balance_bg = PastelTheme.MINT_PASTEL if balance >= 0 else PastelTheme.CORAL_PASTEL
        balance_color = PastelTheme.ACCENT_MINT if balance >= 0 else PastelTheme.ACCENT_CORAL
        balance_prefix = "+" if balance > 0 else ""

        self.summary_kpi_row.controls = [
            create_metric_tile(
                title="Ingresos (Ventas)",
                value=f"+${ingresos:,.0f}",
                icon=ft.Icons.ARROW_UPWARD_ROUNDED,
                bg_pastel=PastelTheme.MINT_PASTEL,
                icon_color=PastelTheme.ACCENT_MINT,
                subtitle="Entradas por facturación POS",
            ),
            create_metric_tile(
                title="Pagos a Proveedores",
                value=f"-${pagos_prov:,.0f}",
                icon=ft.Icons.LOCAL_SHIPPING_ROUNDED,
                bg_pastel=PastelTheme.CORAL_PASTEL,
                icon_color=PastelTheme.ACCENT_CORAL,
                subtitle="Egresos de inventario / compras",
            ),
            create_metric_tile(
                title="Gastos Generales",
                value=f"-${gastos_gen:,.0f}",
                icon=ft.Icons.RECEIPT_ROUNDED,
                bg_pastel=PastelTheme.AMBER_PASTEL,
                icon_color=PastelTheme.ACCENT_AMBER,
                subtitle="Servicios, nómina y varios",
            ),
            create_metric_tile(
                title="Flujo de Caja Neto",
                value=f"{balance_prefix}${balance:,.0f}",
                icon=ft.Icons.ACCOUNT_BALANCE_ROUNDED,
                bg_pastel=balance_bg,
                icon_color=balance_color,
                subtitle=f"{ledger['count']} movimientos en el periodo",
            ),
        ]

        self.records_count_badge.content.value = f"{ledger['count']} transacciones"

        # 2. Construir filas de la Tabla de Datos (DataTable)
        rows = []
        for tx in ledger["transactions"]:
            is_income = tx["is_income"]
            source_type = tx["source_type"]
            source_id = tx["source_id"]

            # Badge del Tipo de Movimiento
            if source_type == "VENTA":
                tipo_badge = create_badge(
                    "Venta (Ingreso)",
                    PastelTheme.MINT_PASTEL,
                    PastelTheme.ACCENT_MINT,
                )
            elif source_type == "PROVEEDOR":
                tipo_badge = create_badge(
                    "Pago Proveedor",
                    PastelTheme.SKY_PASTEL,
                    PastelTheme.ACCENT_SKY,
                )
            else:
                tipo_badge = create_badge(
                    "Gasto General",
                    PastelTheme.CORAL_PASTEL,
                    PastelTheme.ACCENT_CORAL,
                )

            # Monto con color VERDE para ingresos y ROJO para egresos
            amount_prefix = "+" if is_income else "-"
            amount_color = PastelTheme.ACCENT_MINT if is_income else PastelTheme.ACCENT_CORAL
            amount_text = ft.Text(
                f"{amount_prefix}${tx['monto']:,.2f}",
                weight=ft.FontWeight.BOLD,
                size=13,
                color=amount_color,
            )

            # Acción para eliminar gasto/pago si fue ingresado manualmente
            if source_type in ("GASTO", "PROVEEDOR"):
                action_ctrl = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_size=18,
                    icon_color=PastelTheme.ACCENT_CORAL,
                    tooltip="Eliminar registro de egreso",
                    on_click=lambda _, st=source_type, sid=source_id: self._delete_outflow_record(st, sid),
                )
            else:
                action_ctrl = ft.Icon(
                    ft.Icons.VERIFIED_ROUNDED,
                    size=18,
                    color=PastelTheme.ACCENT_MINT,
                    tooltip="Factura verificada en POS",
                )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(tx["fecha"], size=12, weight=ft.FontWeight.W_600, color=PastelTheme.TEXT_PRIMARY)
                        ),
                        ft.DataCell(
                            ft.Text(tx["hora"], size=12, color=PastelTheme.TEXT_SECONDARY)
                        ),
                        ft.DataCell(tipo_badge),
                        ft.DataCell(
                            ft.Container(
                                width=460,
                                content=ft.Text(
                                    tx["descripcion"],
                                    size=12,
                                    color=PastelTheme.TEXT_PRIMARY,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            )
                        ),
                        ft.DataCell(amount_text),
                        ft.DataCell(action_ctrl),
                    ]
                )
            )

        self.data_table.rows = rows
        self.empty_state_container.visible = (len(rows) == 0)
        safe_update(self)

    def _delete_outflow_record(self, source_type: str, source_id: int) -> None:
        if source_type == "GASTO":
            self.controller.delete_general_expense(source_id)
        elif source_type == "PROVEEDOR":
            self.controller.delete_supplier_purchase(source_id)
        self.load_transactions()

    # ================= MODALES PARA REGISTRAR EGRESOS =================

    def show_create_expense_modal(self) -> None:
        """Modal para registrar un nuevo Gasto General en la tabla gastos_generales."""
        categoria_dd = ft.Dropdown(
            label="Categoría del Gasto",
            value="Servicios Públicos",
            border_radius=8,
            dense=True,
            options=[
                ft.dropdown.Option("Servicios Públicos", "Servicios Públicos (Luz, Agua, Internet)"),
                ft.dropdown.Option("Nómina", "Nómina y Personal"),
                ft.dropdown.Option("Arriendo", "Arriendo / Local"),
                ft.dropdown.Option("Mantenimiento", "Mantenimiento y Reparaciones"),
                ft.dropdown.Option("Transporte", "Transporte y Fletes"),
                ft.dropdown.Option("Impuestos", "Impuestos y Tasas"),
                ft.dropdown.Option("Varios", "Varios / Insumos Operativos"),
            ],
        )

        descripcion_tf = ft.TextField(
            label="Descripción detallada",
            hint_text="Ej. Pago recibo de energía eléctrica del mes...",
            border_radius=8,
            dense=True,
            autofocus=True,
        )

        monto_tf = ft.TextField(
            label="Monto del Gasto ($)",
            value="",
            hint_text="0.00",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            dense=True,
        )

        error_text = ft.Text("", size=12, color=PastelTheme.ACCENT_CORAL, visible=False)

        def save_expense(_):
            try:
                amount = float(monto_tf.value or 0)
            except ValueError:
                error_text.value = "Ingresa un monto numérico válido."
                error_text.visible = True
                safe_update(error_text)
                return

            ok, msg, _ = self.controller.create_general_expense(
                categoria=categoria_dd.value or "Varios",
                descripcion=descripcion_tf.value or "",
                monto=amount,
                fecha_hora=datetime.now(),
            )
            if not ok:
                error_text.value = msg
                error_text.visible = True
                safe_update(error_text)
                return

            self.page.pop_dialog()
            self.load_transactions()

        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.RECEIPT_ROUNDED, color=PastelTheme.ACCENT_CORAL, size=24),
                ft.Text("Registrar Gasto General (Egreso)", weight=ft.FontWeight.BOLD, size=17),
            ]),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[
                        ft.Text(
                            f"Fecha y Hora de registro: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                            size=11,
                            color=PastelTheme.TEXT_MUTED,
                        ),
                        categoria_dd,
                        descripcion_tf,
                        monto_tf,
                        error_text,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.FilledButton(
                    "Guardar Gasto",
                    bgcolor=PastelTheme.ACCENT_CORAL,
                    color=PastelTheme.TEXT_ON_PRIMARY,
                    on_click=save_expense,
                ),
            ],
        )
        self.page.show_dialog(dialog)

    def show_create_supplier_payment_modal(self) -> None:
        """Modal para registrar un Pago / Compra a Proveedor en supplier_purchases."""
        suppliers = self.controller.get_active_suppliers_list()
        supplier_options = [ft.dropdown.Option("", "Proveedor General / Compra Directa")] + [
            ft.dropdown.Option(str(s["id"]), s["name"]) for s in suppliers
        ]

        supplier_dd = ft.Dropdown(
            label="Seleccionar Proveedor",
            value=str(suppliers[0]["id"]) if suppliers else "",
            border_radius=8,
            dense=True,
            options=supplier_options,
        )

        ref_tf = ft.TextField(
            label="Referencia / Nº Factura Proveedor (Opcional)",
            hint_text="Ej. FAC-PROV-1055",
            border_radius=8,
            dense=True,
        )

        descripcion_tf = ft.TextField(
            label="Descripción de Mercancía o Pago",
            hint_text="Ej. Compra de lote de bebidas y abarrotes...",
            border_radius=8,
            dense=True,
            autofocus=True,
        )

        monto_tf = ft.TextField(
            label="Monto Pagado ($)",
            value="",
            hint_text="0.00",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            dense=True,
        )

        method_dd = ft.Dropdown(
            label="Método de Pago",
            value="CASH",
            border_radius=8,
            dense=True,
            options=[
                ft.dropdown.Option("CASH", "Efectivo de Caja"),
                ft.dropdown.Option("TRANSFER", "Transferencia Bancaria"),
                ft.dropdown.Option("CARD", "Tarjeta Corporativa"),
            ],
        )

        error_text = ft.Text("", size=12, color=PastelTheme.ACCENT_CORAL, visible=False)

        def save_purchase(_):
            try:
                amount = float(monto_tf.value or 0)
            except ValueError:
                error_text.value = "Ingresa un monto numérico válido."
                error_text.visible = True
                safe_update(error_text)
                return

            sup_id = int(supplier_dd.value) if (supplier_dd.value and supplier_dd.value.isdigit()) else None

            ok, msg, _ = self.controller.create_supplier_purchase(
                supplier_id=sup_id,
                descripcion=descripcion_tf.value or "",
                monto=amount,
                invoice_reference=ref_tf.value or "",
                payment_method=method_dd.value or "CASH",
                fecha_hora=datetime.now(),
            )
            if not ok:
                error_text.value = msg
                error_text.visible = True
                safe_update(error_text)
                return

            self.page.pop_dialog()
            self.load_transactions()

        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.LOCAL_SHIPPING_ROUNDED, color=PastelTheme.PRIMARY, size=24),
                ft.Text("Registrar Pago a Proveedor (Egreso)", weight=ft.FontWeight.BOLD, size=17),
            ]),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[
                        ft.Text(
                            f"Fecha y Hora de registro: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                            size=11,
                            color=PastelTheme.TEXT_MUTED,
                        ),
                        supplier_dd,
                        ref_tf,
                        descripcion_tf,
                        monto_tf,
                        method_dd,
                        error_text,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.FilledButton(
                    "Guardar Pago",
                    bgcolor=PastelTheme.PRIMARY,
                    color=PastelTheme.TEXT_ON_PRIMARY,
                    on_click=save_purchase,
                ),
            ],
        )
        self.page.show_dialog(dialog)
