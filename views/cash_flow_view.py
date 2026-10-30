from datetime import datetime
from typing import Optional, Callable
import flet as ft

from config import PastelTheme
from controllers import DashboardController
from views.date_filter_bar import DateRangeFilterBar
from views.theme import create_card, create_metric_tile, create_badge, safe_update, SearchableDropdown


class CashFlowView(ft.Container):
    """
    Vista del Módulo de Libro Mayor y Flujo de Caja (Detalle Transaccional).
    - Consolida y ordena cronológicamente por Fecha y Hora exacta (DateTime):
      1. Ventas realizadas (Ingresos - Color Verde).
      2. Pagos a proveedores (Egresos de inventario - Color Rojo).
      3. Gastos generales (Egresos fijos/variables como servicios públicos, nómina, varios - Color Rojo).
    - Reacciona en tiempo real al Filtro Temporal Avanzado (estilo YouTube Studio / Google Calendar).
    - Permite registrar nuevos Gastos Generales, Pagos a Proveedores y Reversar Ventas restaurando stock.
    """

    def __init__(
        self,
        dashboard_controller: DashboardController,
        on_sale_reversed: Optional[Callable[[], None]] = None,
    ):
        super().__init__(expand=True)
        self.controller = dashboard_controller
        self.on_sale_reversed = on_sale_reversed
        self.padding = 24

        self.type_filter: str = "ALL"
        self.sort_descending: bool = True

        # Estado de Paginación Server-Side / SQLite (LIMIT 50 OFFSET X)
        self.current_page: int = 1
        self.page_size: int = 50
        self.total_pages: int = 1
        self.total_records: int = 0

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
            on_change=self._on_search_change,
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
                                ft.OutlinedButton(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.SHIELD_ROUNDED, size=18, color=PastelTheme.ACCENT_AMBER),
                                        ft.Text("Auditoría Anulaciones", color=PastelTheme.TEXT_PRIMARY),
                                    ]),
                                    style=ft.ButtonStyle(
                                        side=ft.BorderSide(1, PastelTheme.ACCENT_AMBER),
                                        shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                                    ),
                                    tooltip="Ver el registro inmutable de ventas anuladas / reversadas (Loss Prevention)",
                                    on_click=lambda _: self.show_audit_logs_modal(),
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

                # Tarjeta con la Tabla de Datos Unificada y Paginación (50 por página)
                create_card(
                    expand=True,
                    padding=12,
                    content=ft.Column(
                        expand=True,
                        spacing=8,
                        controls=[
                            ft.Column(
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
                            self._build_pagination_bar(),
                        ],
                    ),
                ),
            ],
        )

        self.load_transactions()

    def _build_pagination_bar(self) -> ft.Container:
        """Construye los controles inferiores de paginación ('Anterior' | 'Página X de Y' | 'Siguiente')."""
        self.prev_page_btn = ft.OutlinedButton(
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.CHEVRON_LEFT_ROUNDED, size=18),
                    ft.Text("Anterior", size=12, weight=ft.FontWeight.W_600),
                ],
            ),
            disabled=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            ),
            on_click=self._on_prev_page,
        )
        self.page_indicator_text = ft.Text(
            "Página 1 de 1",
            size=13,
            weight=ft.FontWeight.BOLD,
            color=PastelTheme.TEXT_PRIMARY,
        )
        self.records_range_text = ft.Text(
            "0 transacciones",
            size=12,
            color=PastelTheme.TEXT_SECONDARY,
        )
        self.next_page_btn = ft.OutlinedButton(
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Text("Siguiente", size=12, weight=ft.FontWeight.W_600),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=18),
                ],
            ),
            disabled=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            ),
            on_click=self._on_next_page,
        )
        return ft.Container(
            bgcolor=PastelTheme.SURFACE_VARIANT,
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            border_radius=8,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    self.records_range_text,
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            self.prev_page_btn,
                            self.page_indicator_text,
                            self.next_page_btn,
                        ],
                    ),
                ],
            ),
        )

    def _on_search_change(self, _=None) -> None:
        self.current_page = 1
        self.load_transactions()

    def _on_prev_page(self, _=None) -> None:
        if self.current_page > 1:
            self.current_page -= 1
            self.load_transactions()

    def _on_next_page(self, _=None) -> None:
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_transactions()

    def _on_date_range_changed(
        self,
        _start_date: Optional[datetime],
        _end_date: Optional[datetime],
        _label: str,
    ) -> None:
        self.current_page = 1
        self.load_transactions()

    def _on_external_filter_sync(self) -> None:
        self.date_filter_bar.sync_from_controller()
        self.current_page = 1
        self.load_transactions()

    def _on_type_filter_change(self, e) -> None:
        self.type_filter = self.type_dropdown.value or "ALL"
        self.current_page = 1
        self.load_transactions()

    def _toggle_sort_direction(self, _=None) -> None:
        self.sort_descending = not self.sort_descending
        self.sort_btn_text.value = "Más recientes" if self.sort_descending else "Más antiguos"
        self.current_page = 1
        self.load_transactions()

    def load_transactions(self) -> None:
        """
        Consulta el Libro Mayor consolidado para el rango temporal activo con paginación
        SQLite (LIMIT 50 OFFSET X) y renderiza solo 50 registros por página.
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
            page=self.current_page,
            page_size=self.page_size,
        )

        self.current_page = ledger["page"]
        self.total_pages = ledger["total_pages"]
        self.total_records = ledger["total_records"]
        offset_val = ledger["offset"]
        page_txs = ledger["transactions"]

        start_idx = (offset_val + 1) if self.total_records > 0 else 0
        end_idx = min(offset_val + len(page_txs), self.total_records)
        self.page_indicator_text.value = f"Página {self.current_page} de {self.total_pages}"
        self.records_range_text.value = (
            f"Mostrando {start_idx}–{end_idx} de {self.total_records:,} transacciones (50 por página)"
        )
        self.prev_page_btn.disabled = (self.current_page <= 1)
        self.next_page_btn.disabled = (self.current_page >= self.total_pages)

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

            # Acción: eliminar gasto/pago o ver detalle + reversar venta restaurando stock
            if source_type in ("GASTO", "PROVEEDOR"):
                action_ctrl = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_size=18,
                    icon_color=PastelTheme.ACCENT_CORAL,
                    tooltip="Eliminar registro de egreso",
                    on_click=lambda _, st=source_type, sid=source_id: self._delete_outflow_record(st, sid),
                )
            else:
                action_ctrl = ft.Row(
                    spacing=6,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.OutlinedButton(
                            content=ft.Row(
                                spacing=5,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.VISIBILITY_ROUNDED, size=15, color=PastelTheme.PRIMARY),
                                    ft.Text("Ver Detalle", size=11, weight=ft.FontWeight.W_600, color=PastelTheme.PRIMARY),
                                ],
                            ),
                            style=ft.ButtonStyle(
                                bgcolor=PastelTheme.PRIMARY_PASTEL,
                                side=ft.BorderSide(1, PastelTheme.PRIMARY),
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                            ),
                            tooltip="Ver qué productos se llevaron en esta factura",
                            on_click=lambda _, sid=source_id: self._show_invoice_detail_modal(sid),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                            icon_size=18,
                            icon_color=PastelTheme.ACCENT_CORAL,
                            tooltip="Eliminar / Reversar venta y restaurar stock en inventario",
                            on_click=lambda _, sid=source_id, desc=tx["descripcion"], amt=tx["monto"]: (
                                self._confirm_reverse_sale_modal(sid, desc, amt)
                            ),
                        ),
                    ],
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
                                ink=(source_type == "VENTA"),
                                tooltip="Clic para ver los productos de la factura" if source_type == "VENTA" else None,
                                on_click=(
                                    (lambda _, sid=source_id: self._show_invoice_detail_modal(sid))
                                    if source_type == "VENTA"
                                    else None
                                ),
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

    def _confirm_reverse_sale_modal(self, invoice_id: int, description: str, amount: float) -> None:
        """
        Muestra un Diálogo de Confirmación con control de Prevención de Pérdidas (Loss Prevention)
        antes de eliminar/reversar una factura de venta:
        - Exige el campo obligatorio "Motivo de la anulación" (mínimo 5 caracteres).
        - Mantiene bloqueado el botón "Confirmar Eliminación" o muestra error si el motivo es inválido.
        - Registra la anulación en `RegistroAnulaciones` y restaura el stock en una sola transacción.
        """
        motivo_validation_text = ft.Text(
            "⚠ Obligatorio: ingrese el motivo de la anulación (mínimo 5 caracteres).",
            size=11,
            weight=ft.FontWeight.W_600,
            color=PastelTheme.ACCENT_CORAL,
        )

        confirm_btn = ft.FilledButton(
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.DELETE_FOREVER_ROUNDED, size=18),
                    ft.Text("Confirmar Eliminación", weight=ft.FontWeight.BOLD),
                ],
            ),
            disabled=True,
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT: PastelTheme.ACCENT_CORAL,
                    ft.ControlState.DISABLED: PastelTheme.BORDER_LIGHT,
                },
                color={
                    ft.ControlState.DEFAULT: PastelTheme.TEXT_ON_PRIMARY,
                    ft.ControlState.DISABLED: PastelTheme.TEXT_MUTED,
                },
                shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
            ),
        )

        def _on_motivo_change(e) -> None:
            raw_motivo = (e.control.value or "").strip()
            if len(raw_motivo) >= 5:
                confirm_btn.disabled = False
                motivo_validation_text.value = "✓ Motivo válido para registro en auditoría inmutable."
                motivo_validation_text.color = PastelTheme.ACCENT_MINT
            else:
                confirm_btn.disabled = True
                faltan = 5 - len(raw_motivo)
                motivo_validation_text.value = (
                    f"⚠ El motivo debe tener al menos 5 caracteres (faltan {faltan})."
                )
                motivo_validation_text.color = PastelTheme.ACCENT_CORAL
            safe_update(confirm_btn)
            safe_update(motivo_validation_text)

        motivo_input = ft.TextField(
            label="Motivo de la anulación",
            hint_text='Ej: "Cliente devolvió el producto", "Error de digitación"...',
            prefix_icon=ft.Icons.POLICY_ROUNDED,
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=PastelTheme.BORDER_RADIUS_INPUT,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_color=PastelTheme.ACCENT_CORAL,
            focused_border_color=PastelTheme.PRIMARY,
            dense=True,
            autofocus=True,
            on_change=_on_motivo_change,
        )

        def _execute_reversal(_=None):
            clean_motivo = (motivo_input.value or "").strip()
            if len(clean_motivo) < 5:
                motivo_validation_text.value = (
                    "⚠ Error: Debe escribir un motivo de al menos 5 caracteres para confirmar la eliminación."
                )
                motivo_validation_text.color = PastelTheme.ACCENT_CORAL
                confirm_btn.disabled = True
                safe_update(motivo_validation_text)
                safe_update(confirm_btn)
                return

            self.page.pop_dialog()
            success, msg = self.controller.reverse_sale_invoice(invoice_id, clean_motivo)
            self.load_transactions()
            if self.on_sale_reversed is not None:
                try:
                    self.on_sale_reversed()
                except Exception as cb_err:
                    print(f"[CashFlowView] Error en callback on_sale_reversed: {cb_err}")

            feedback_dialog = ft.AlertDialog(
                title=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if success else ft.Icons.ERROR_OUTLINE_ROUNDED,
                            color=PastelTheme.ACCENT_MINT if success else PastelTheme.ACCENT_CORAL,
                            size=24,
                        ),
                        ft.Text(
                            "Venta Anulada, Auditada y Stock Restaurado" if success else "Error al Reversar Venta",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                content=ft.Text(msg, size=13, color=PastelTheme.TEXT_PRIMARY),
                actions=[
                    ft.FilledButton(
                        "Aceptar",
                        bgcolor=PastelTheme.PRIMARY,
                        color=PastelTheme.TEXT_ON_PRIMARY,
                        on_click=lambda _: self.page.pop_dialog(),
                    )
                ],
            )
            self.page.show_dialog(feedback_dialog)

        confirm_btn.on_click = _execute_reversal

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                spacing=10,
                controls=[
                    ft.Container(
                        bgcolor=PastelTheme.CORAL_PASTEL,
                        padding=8,
                        border_radius=10,
                        content=ft.Icon(ft.Icons.RESTORE_ROUNDED, color=PastelTheme.ACCENT_CORAL, size=22),
                    ),
                    ft.Text(
                        "Confirmar Eliminación / Reversión de Venta",
                        size=17,
                        weight=ft.FontWeight.BOLD,
                        color=PastelTheme.TEXT_PRIMARY,
                    ),
                ],
            ),
            content=ft.Container(
                width=460,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text(
                            "Esta acción reversará la venta, devolverá el stock al inventario y dejará un registro inmutable de auditoría.",
                            size=13,
                            color=PastelTheme.TEXT_PRIMARY,
                        ),
                        ft.Container(
                            bgcolor=PastelTheme.SURFACE_VARIANT,
                            border_radius=10,
                            padding=12,
                            border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
                            content=ft.Column(
                                spacing=4,
                                tight=True,
                                controls=[
                                    ft.Text(description, size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                    ft.Text(
                                        f"Monto total a anular: ${amount:,.2f}",
                                        size=12,
                                        color=PastelTheme.ACCENT_CORAL,
                                        weight=ft.FontWeight.W_600,
                                    ),
                                ],
                            ),
                        ),
                        motivo_input,
                        motivo_validation_text,
                        ft.Container(
                            bgcolor=PastelTheme.MINT_PASTEL,
                            border_radius=8,
                            padding=10,
                            content=ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, size=18, color=PastelTheme.ACCENT_MINT),
                                    ft.Text(
                                        "Las unidades vendidas se sumarán de vuelta al Inventario y el motivo quedará guardado en RegistroAnulaciones.",
                                        size=11,
                                        color=PastelTheme.TEXT_PRIMARY,
                                        expand=True,
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda _: self.page.pop_dialog(),
                ),
                confirm_btn,
            ],
        )
        self.page.show_dialog(confirm_dialog)

    def show_audit_logs_modal(self) -> None:
        """
        Muestra el historial inmutable de facturas anuladas/reversadas (RegistroAnulaciones),
        permitiendo visualizar el detalle completo de productos cargados en cada factura
        y retornar/restaurar la factura nuevamente al Flujo de Caja.
        """
        logs = self.controller.get_cancellation_audit_logs()
        items_controls = []
        for entry in logs:
            audit_id = entry["id"]
            is_restored = bool(entry.get("restaurada", False))
            has_snapshot = bool(entry.get("has_snapshot", False))
            snapshot_items = entry.get("items", []) or []

            status_badge = (
                create_badge("RESTAURADA EN CAJA", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)
                if is_restored
                else create_badge("ANULADA", PastelTheme.CORAL_PASTEL, PastelTheme.ACCENT_CORAL)
            )

            if snapshot_items:
                preview_parts = []
                for it in snapshot_items[:3]:
                    p_name = it.get("display_name") or it.get("product_name") or "Producto"
                    qty = it.get("quantity", 1)
                    preview_parts.append(f"{qty}x {p_name}")
                if len(snapshot_items) > 3:
                    preview_parts.append(f"(+{len(snapshot_items) - 3} más)")
                products_preview_str = "Productos: " + ", ".join(preview_parts)
            else:
                products_preview_str = (
                    f"Factura histórica (${entry['monto_total']:,.2f}) — Disponible para restaurar a Flujo de Caja"
                )

            items_controls.append(
                ft.Container(
                    bgcolor=PastelTheme.SURFACE_VARIANT,
                    border_radius=12,
                    padding=14,
                    border=ft.Border.all(
                        1,
                        PastelTheme.ACCENT_MINT if is_restored else PastelTheme.BORDER_LIGHT,
                    ),
                    content=ft.Column(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Icon(
                                                ft.Icons.RECEIPT_LONG_ROUNDED,
                                                size=18,
                                                color=PastelTheme.PRIMARY,
                                            ),
                                            ft.Text(
                                                f"Factura: {entry['factura_id_original']}",
                                                size=13,
                                                weight=ft.FontWeight.BOLD,
                                                color=PastelTheme.TEXT_PRIMARY,
                                            ),
                                            status_badge,
                                        ],
                                    ),
                                    ft.Text(
                                        f"${entry['monto_total']:,.2f}",
                                        size=15,
                                        weight=ft.FontWeight.BOLD,
                                        color=PastelTheme.ACCENT_MINT if is_restored else PastelTheme.ACCENT_CORAL,
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=16,
                                wrap=True,
                                controls=[
                                    ft.Text(
                                        f"Fecha de anulación: {entry['fecha_anulacion']}",
                                        size=11,
                                        color=PastelTheme.TEXT_SECONDARY,
                                    ),
                                    *(
                                        [
                                            ft.Text(
                                                f"Cliente: {entry['snapshot'].get('customer_name', 'Consumidor Final')}",
                                                size=11,
                                                weight=ft.FontWeight.W_600,
                                                color=PastelTheme.TEXT_SECONDARY,
                                            )
                                        ]
                                        if has_snapshot and isinstance(entry.get("snapshot"), dict)
                                        else []
                                    ),
                                ],
                            ),
                            ft.Text(
                                f"Motivo de anulación: {entry['motivo']}",
                                size=12,
                                weight=ft.FontWeight.W_500,
                                color=PastelTheme.TEXT_PRIMARY,
                            ),
                            ft.Container(
                                bgcolor=PastelTheme.SURFACE_WHITE,
                                border_radius=8,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
                                content=ft.Row(
                                    spacing=6,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.SHOPPING_BAG_OUTLINED,
                                            size=14,
                                            color=PastelTheme.PRIMARY,
                                        ),
                                        ft.Text(
                                            products_preview_str,
                                            size=11,
                                            color=PastelTheme.TEXT_SECONDARY,
                                            expand=True,
                                        ),
                                    ],
                                ),
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                spacing=8,
                                controls=[
                                    ft.OutlinedButton(
                                        "Ver Detalle / Productos",
                                        icon=ft.Icons.VISIBILITY_ROUNDED,
                                        style=ft.ButtonStyle(
                                            color=PastelTheme.PRIMARY,
                                            side=ft.BorderSide(1, PastelTheme.PRIMARY),
                                            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                                        ),
                                        on_click=lambda _, aid=audit_id: self._show_cancelled_invoice_detail_modal(aid),
                                    ),
                                    ft.FilledButton(
                                        "Ya Restaurada en Caja" if is_restored else "Retornar a Flujo de Caja",
                                        icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED if is_restored else ft.Icons.RESTORE_ROUNDED,
                                        disabled=is_restored,
                                        bgcolor=PastelTheme.ACCENT_MINT if not is_restored else PastelTheme.SURFACE_VARIANT,
                                        color=PastelTheme.TEXT_ON_PRIMARY if not is_restored else PastelTheme.TEXT_MUTED,
                                        on_click=lambda _, aid=audit_id: self._handle_restore_cancelled_invoice(aid),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            )

        if not items_controls:
            items_controls.append(
                ft.Container(
                    padding=24,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(
                        "No se han registrado anulaciones de facturas en este inquilino.",
                        size=13,
                        color=PastelTheme.TEXT_MUTED,
                    ),
                )
            )

        audit_dialog = ft.AlertDialog(
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.SHIELD_ROUNDED, color=PastelTheme.ACCENT_AMBER, size=24),
                    ft.Text("Auditoría de Anulaciones y Recuperación de Facturas", size=16, weight=ft.FontWeight.BOLD),
                ],
            ),
            content=ft.Container(
                width=680,
                height=440,
                content=ft.Column(
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    controls=items_controls,
                ),
            ),
            actions=[
                ft.FilledButton(
                    "Cerrar",
                    bgcolor=PastelTheme.PRIMARY,
                    color=PastelTheme.TEXT_ON_PRIMARY,
                    on_click=lambda _: self.page.pop_dialog(),
                )
            ],
        )
        self.page.show_dialog(audit_dialog)

    def _handle_restore_cancelled_invoice(self, audit_log_id: int) -> None:
        """
        Restaura una factura anulada de vuelta al Flujo de Caja y actualiza la vista.
        """
        self.page.pop_dialog()
        success, msg, restored_data = self.controller.restore_cancelled_invoice(audit_log_id)

        result_dialog = ft.AlertDialog(
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_ROUNDED if success else ft.Icons.ERROR_OUTLINE_ROUNDED,
                        color=PastelTheme.ACCENT_MINT if success else PastelTheme.ACCENT_CORAL,
                        size=24,
                    ),
                    ft.Text(
                        "Factura Retornada al Flujo de Caja" if success else "Aviso de Restauración",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            ),
            content=ft.Text(msg, size=13, color=PastelTheme.TEXT_PRIMARY),
            actions=[
                *(
                    [
                        ft.OutlinedButton(
                            "Ver Factura Restaurada",
                            icon=ft.Icons.VISIBILITY_ROUNDED,
                            on_click=lambda _, inv_id=restored_data["id"]: (
                                self.page.pop_dialog(),
                                self._show_invoice_detail_modal(inv_id),
                            ),
                        )
                    ]
                    if success and isinstance(restored_data, dict) and restored_data.get("id")
                    else []
                ),
                ft.FilledButton(
                    "Aceptar",
                    bgcolor=PastelTheme.PRIMARY,
                    color=PastelTheme.TEXT_ON_PRIMARY,
                    on_click=lambda _: self.page.pop_dialog(),
                ),
            ],
        )
        self.page.show_dialog(result_dialog)

    def _show_cancelled_invoice_detail_modal(self, audit_log_id: int) -> None:
        """
        Muestra el detalle completo de una factura anulada (productos que tenía cargados,
        cantidades, precios, cliente y motivo de anulación) con opción directa de retornarla
        al Flujo de Caja.
        """
        details = self.controller.get_audit_log_invoice_details(audit_log_id)
        if not details:
            return

        self.page.pop_dialog()

        is_restored = bool(details.get("restaurada", False))
        has_snapshot = bool(details.get("has_snapshot", False))
        pay_mode_label = "Crédito" if details.get("payment_type") == "CREDIT" else "Contado (Caja)"

        status_badge = (
            create_badge("RESTAURADA EN CAJA", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)
            if is_restored
            else create_badge("FACTURA ANULADA", PastelTheme.CORAL_PASTEL, PastelTheme.ACCENT_CORAL)
        )
        mode_badge = create_badge(
            pay_mode_label,
            PastelTheme.SKY_PASTEL,
            PastelTheme.ACCENT_SKY,
        )

        header_section = ft.Container(
            bgcolor=PastelTheme.CORAL_PASTEL if not is_restored else PastelTheme.MINT_PASTEL,
            border_radius=12,
            padding=16,
            border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
                controls=[
                    ft.Column(
                        spacing=6,
                        expand=True,
                        controls=[
                            ft.Row(
                                spacing=8,
                                wrap=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, color=PastelTheme.PRIMARY, size=22),
                                    ft.Text(
                                        f"Factura #{details['invoice_number']}",
                                        size=17,
                                        weight=ft.FontWeight.BOLD,
                                        color=PastelTheme.TEXT_PRIMARY,
                                    ),
                                    mode_badge,
                                    status_badge,
                                ],
                            ),
                            ft.Text(
                                f"Fecha original: {details['created_at']}  |  Anulada: {details['fecha_anulacion']}",
                                size=11,
                                color=PastelTheme.TEXT_SECONDARY,
                            ),
                            ft.Text(
                                f"Cliente: {details.get('customer_name') or 'Consumidor Final'}",
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=PastelTheme.TEXT_PRIMARY,
                            ),
                        ],
                    ),
                    ft.Container(
                        bgcolor=PastelTheme.SURFACE_WHITE,
                        border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                        border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
                        content=ft.Column(
                            spacing=3,
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            controls=[
                                ft.Text(
                                    "Total Factura",
                                    size=11,
                                    weight=ft.FontWeight.W_600,
                                    color=PastelTheme.TEXT_SECONDARY,
                                ),
                                ft.Text(
                                    f"${details['total']:,.2f}",
                                    size=20,
                                    weight=ft.FontWeight.BOLD,
                                    color=PastelTheme.PRIMARY,
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        motivo_section = ft.Container(
            bgcolor=PastelTheme.AMBER_PASTEL,
            border_radius=12,
            padding=12,
            border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
            content=ft.Column(
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Text(
                        f"Motivo de Anulación: {details.get('motivo') or 'Sin motivo especificado'}",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=PastelTheme.TEXT_PRIMARY,
                    ),
                    ft.Text(
                        details.get("description_display", ""),
                        size=12,
                        color=PastelTheme.TEXT_SECONDARY,
                    ),
                    *(
                        [
                            ft.Text(
                                "Nota: Esta factura fue eliminada antes de la actualización de respaldo detallado, pero puedes retornarla al Flujo de Caja con su valor total exacto.",
                                size=11,
                                italic=True,
                                color=PastelTheme.ACCENT_AMBER,
                            )
                        ]
                        if not has_snapshot
                        else []
                    ),
                ],
            ),
        )

        item_rows = []
        for item in details.get("items", []):
            item_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(
                                item.get("display_name") or item.get("product_name", ""),
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=PastelTheme.TEXT_PRIMARY,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                str(item.get("quantity", 0)),
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=PastelTheme.PRIMARY,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"${item.get('unit_price', 0.0):,.2f}",
                                size=12,
                                color=PastelTheme.TEXT_SECONDARY,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"${item.get('subtotal', 0.0):,.2f}",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=PastelTheme.TEXT_PRIMARY,
                            )
                        ),
                    ]
                )
            )

        products_data_table = ft.DataTable(
            width=670,
            heading_row_color=PastelTheme.SURFACE_VARIANT,
            heading_row_height=40,
            data_row_min_height=42,
            data_row_max_height=54,
            column_spacing=24,
            horizontal_lines=ft.BorderSide(1, PastelTheme.BORDER_LIGHT),
            columns=[
                ft.DataColumn(ft.Text("Producto", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY)),
                ft.DataColumn(
                    ft.Text("Cantidad", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                    numeric=True,
                ),
                ft.DataColumn(
                    ft.Text("Precio Unitario", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                    numeric=True,
                ),
                ft.DataColumn(
                    ft.Text("Subtotal", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                    numeric=True,
                ),
            ],
            rows=item_rows,
        )

        table_section = ft.Container(
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_radius=12,
            padding=14,
            border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
            content=ft.Column(
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.Icons.SHOPPING_BAG_OUTLINED, size=17, color=PastelTheme.PRIMARY),
                                    ft.Text(
                                        "Productos que tenía cargados esta Factura",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                        color=PastelTheme.TEXT_PRIMARY,
                                    ),
                                ],
                            ),
                            create_badge(
                                f"{details.get('items_count', 0)} unidades",
                                PastelTheme.MINT_PASTEL,
                                PastelTheme.ACCENT_MINT,
                            ),
                        ],
                    ),
                    ft.Container(
                        content=ft.Column(
                            scroll=ft.ScrollMode.AUTO,
                            controls=[products_data_table],
                        ),
                        height=210,
                    ),
                ],
            ),
        )

        detail_dialog = ft.AlertDialog(
            modal=False,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.HISTORY_ROUNDED, color=PastelTheme.ACCENT_AMBER, size=22),
                            ft.Text(
                                "Detalle de Factura Anulada (Auditoría)",
                                size=17,
                                weight=ft.FontWeight.BOLD,
                                color=PastelTheme.TEXT_PRIMARY,
                            ),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_color=PastelTheme.TEXT_SECONDARY,
                        tooltip="Cerrar ventana",
                        on_click=lambda _: self.page.pop_dialog(),
                    ),
                ],
            ),
            content=ft.Container(
                width=720,
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[
                        header_section,
                        motivo_section,
                        table_section,
                    ],
                ),
            ),
            actions=[
                ft.TextButton(
                    "Volver a Auditoría",
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    on_click=lambda _: (
                        self.page.pop_dialog(),
                        self.show_audit_logs_modal(),
                    ),
                ),
                ft.FilledButton(
                    "Ya Restaurada en Caja" if is_restored else "Retornar Factura a Flujo de Caja",
                    icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED if is_restored else ft.Icons.RESTORE_ROUNDED,
                    disabled=is_restored,
                    bgcolor=PastelTheme.ACCENT_MINT if not is_restored else PastelTheme.SURFACE_VARIANT,
                    color=PastelTheme.TEXT_ON_PRIMARY if not is_restored else PastelTheme.TEXT_MUTED,
                    on_click=lambda _, aid=audit_log_id: self._handle_restore_cancelled_invoice(aid),
                ),
            ],
        )
        self.page.show_dialog(detail_dialog)

    # ================= MODAL "DETALLE DE FACTURA" EN FLUJO DE CAJA =================

    def _show_invoice_detail_modal(self, invoice_id: int) -> None:
        """
        Abre un modal estilizado con el detalle completo de la factura desde Flujo de Caja:
        - Cabecera: Número de factura, Fecha y Hora, Modalidad (Contado/Crédito), Estado y Cliente
          (o 'Consumidor Final' si no se asignó cliente).
        - Descripción / Notas e historial de abonos (si aplica).
        - Tabla de Productos: Todos los artículos comprados con presentación, cantidad, precio unitario y subtotal.
        """
        details = self.controller.get_invoice_details(invoice_id)
        if not details:
            return

        is_pending = (details["payment_status"] == "PENDING" and details["balance_due"] > 0)
        has_abonos = (details["amount_paid"] > 0 and is_pending)
        pay_mode_label = "Crédito" if details.get("payment_type") == "CREDIT" else "Contado (Caja)"

        if not is_pending:
            status_badge = create_badge("Pagada", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)
        elif has_abonos:
            status_badge = create_badge("Pendiente (Con Abono)", PastelTheme.AMBER_PASTEL, PastelTheme.ACCENT_AMBER)
        else:
            status_badge = create_badge("Pendiente", PastelTheme.CORAL_PASTEL, PastelTheme.ACCENT_CORAL)

        mode_badge = create_badge(
            pay_mode_label,
            PastelTheme.SKY_PASTEL,
            PastelTheme.ACCENT_SKY,
        )

        # 1. Cabecera de la factura
        header_section = ft.Container(
            bgcolor=PastelTheme.PRIMARY_PASTEL,
            border_radius=12,
            padding=16,
            border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
                controls=[
                    ft.Column(
                        spacing=6,
                        expand=True,
                        controls=[
                            ft.Row(
                                spacing=8,
                                wrap=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, color=PastelTheme.PRIMARY, size=22),
                                    ft.Text(
                                        f"Factura #{details['invoice_number']}",
                                        size=17,
                                        weight=ft.FontWeight.BOLD,
                                        color=PastelTheme.TEXT_PRIMARY,
                                    ),
                                    mode_badge,
                                    status_badge,
                                ],
                            ),
                            ft.Row(
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.ACCESS_TIME_ROUNDED, size=14, color=PastelTheme.TEXT_SECONDARY),
                                    ft.Text(
                                        f"Fecha y Hora: {details['created_at']}",
                                        size=12,
                                        weight=ft.FontWeight.W_500,
                                        color=PastelTheme.TEXT_SECONDARY,
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.PERSON_OUTLINE_ROUNDED, size=14, color=PastelTheme.TEXT_SECONDARY),
                                    ft.Text(
                                        f"Cliente: {details.get('customer_name') or 'Consumidor Final'}",
                                        size=12,
                                        weight=ft.FontWeight.W_500,
                                        color=PastelTheme.TEXT_SECONDARY,
                                        expand=True,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Container(
                        bgcolor=PastelTheme.SURFACE_WHITE,
                        border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                        border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
                        content=ft.Column(
                            spacing=3,
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            controls=[
                                ft.Text(
                                    "Total Factura",
                                    size=11,
                                    weight=ft.FontWeight.W_600,
                                    color=PastelTheme.TEXT_SECONDARY,
                                ),
                                ft.Text(
                                    f"${details['total']:,.2f}",
                                    size=20,
                                    weight=ft.FontWeight.BOLD,
                                    color=PastelTheme.PRIMARY,
                                ),
                                *(
                                    [
                                        ft.Row(
                                            spacing=10,
                                            tight=True,
                                            controls=[
                                                ft.Text(
                                                    f"Abonado: ${details['amount_paid']:,.0f}",
                                                    size=11,
                                                    weight=ft.FontWeight.W_600,
                                                    color=PastelTheme.ACCENT_MINT,
                                                ),
                                                ft.Text(
                                                    f"Saldo: ${details['balance_due']:,.0f}",
                                                    size=11,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=PastelTheme.ACCENT_CORAL if is_pending else PastelTheme.ACCENT_MINT,
                                                ),
                                            ],
                                        )
                                    ]
                                    if details.get("payment_type") == "CREDIT" and (details["amount_paid"] > 0 or is_pending)
                                    else []
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        # 2. Sección de Notas / Abonos (si existen)
        payments = details.get("payments", [])
        payment_history_controls = []
        if payments:
            payment_history_controls.append(ft.Divider(height=8, color=PastelTheme.BORDER_LIGHT))
            payment_history_controls.append(
                ft.Text(
                    "Historial de Abonos / Pagos de esta Factura:",
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=PastelTheme.ACCENT_SKY,
                )
            )
            for pay in payments:
                kind_str = "Pago Total" if pay["payment_kind"] == "PAGO_TOTAL" else "Abono Parcial"
                note_str = f" — {pay['notes']}" if pay.get("notes") else ""
                payment_history_controls.append(
                    ft.Container(
                        bgcolor=PastelTheme.SURFACE_WHITE,
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                            controls=[
                                ft.Text(
                                    f"• [{pay['fecha_hora']}] {kind_str}{note_str}",
                                    size=11,
                                    color=PastelTheme.TEXT_PRIMARY,
                                    expand=True,
                                ),
                                ft.Text(
                                    f"-${pay['amount']:,.2f} (Saldo restante: ${pay['balance_after']:,.2f})",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=PastelTheme.ACCENT_MINT,
                                ),
                            ],
                        ),
                    )
                )

        description_section = ft.Container(
            bgcolor=PastelTheme.AMBER_PASTEL,
            border_radius=12,
            padding=14,
            border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
            content=ft.Column(
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Row(
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=16, color=PastelTheme.ACCENT_AMBER),
                            ft.Text(
                                "Observaciones / Detalle de la Venta",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=PastelTheme.TEXT_PRIMARY,
                            ),
                        ],
                    ),
                    ft.Text(
                        details.get("description_display", "Venta registrada en Punto de Venta (POS)"),
                        size=13,
                        color=PastelTheme.TEXT_PRIMARY,
                        italic=(not bool(details.get("credit_notes", "").strip())),
                    ),
                    *payment_history_controls,
                ],
            ),
        )

        # 3. Tabla de Productos llevados en la factura
        item_rows = []
        for item in details.get("items", []):
            item_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(
                                item.get("display_name") or item.get("product_name", ""),
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=PastelTheme.TEXT_PRIMARY,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                str(item.get("quantity", 0)),
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=PastelTheme.PRIMARY,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"${item.get('unit_price', 0.0):,.2f}",
                                size=12,
                                color=PastelTheme.TEXT_SECONDARY,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"${item.get('subtotal', 0.0):,.2f}",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=PastelTheme.TEXT_PRIMARY,
                            )
                        ),
                    ]
                )
            )

        products_data_table = ft.DataTable(
            width=670,
            heading_row_color=PastelTheme.SURFACE_VARIANT,
            heading_row_height=42,
            data_row_min_height=44,
            data_row_max_height=56,
            column_spacing=28,
            horizontal_lines=ft.BorderSide(1, PastelTheme.BORDER_LIGHT),
            columns=[
                ft.DataColumn(
                    ft.Text("Producto", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY)
                ),
                ft.DataColumn(
                    ft.Text("Cantidad", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                    numeric=True,
                ),
                ft.DataColumn(
                    ft.Text("Precio Unitario", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                    numeric=True,
                ),
                ft.DataColumn(
                    ft.Text("Subtotal", weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                    numeric=True,
                ),
            ],
            rows=item_rows,
        )

        table_section = ft.Container(
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_radius=12,
            padding=14,
            border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
            content=ft.Column(
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.Icons.SHOPPING_BAG_OUTLINED, size=17, color=PastelTheme.PRIMARY),
                                    ft.Text(
                                        "Productos Llevados en esta Factura",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                        color=PastelTheme.TEXT_PRIMARY,
                                    ),
                                ],
                            ),
                            create_badge(
                                f"{details.get('items_count', 0)} unidades",
                                PastelTheme.MINT_PASTEL,
                                PastelTheme.ACCENT_MINT,
                            ),
                        ],
                    ),
                    ft.Container(
                        content=ft.Column(
                            scroll=ft.ScrollMode.AUTO,
                            controls=[products_data_table],
                        ),
                        height=220,
                    ),
                ],
            ),
        )

        detail_dialog = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=PastelTheme.BG_LIGHT,
            inset_padding=ft.Padding.symmetric(horizontal=24, vertical=20),
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.VISIBILITY_ROUNDED, color=PastelTheme.PRIMARY, size=24),
                            ft.Text("Detalle de Factura de Venta", weight=ft.FontWeight.BOLD, size=18, color=PastelTheme.TEXT_PRIMARY),
                        ],
                    ),
                    create_badge("Flujo de Caja", PastelTheme.SURFACE_VARIANT, PastelTheme.TEXT_SECONDARY),
                ],
            ),
            content=ft.Container(
                width=710,
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        header_section,
                        description_section,
                        table_section,
                    ],
                ),
            ),
            actions=[
                ft.FilledButton(
                    "Cerrar",
                    style=ft.ButtonStyle(
                        bgcolor=PastelTheme.PRIMARY,
                        color=PastelTheme.TEXT_ON_PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                    on_click=lambda _: self.page.pop_dialog(),
                )
            ],
        )
        self.page.show_dialog(detail_dialog)

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
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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
        """Modal para registrar un Pago / Compra a Proveedor en supplier_purchases con filtro instantáneo desde la 1ª letra."""
        suppliers = self.controller.get_active_suppliers_list()
        supplier_options = [
            {
                "key": "",
                "label": "Proveedor General / Compra Directa",
                "subtitle": "Pago o compra directa sin proveedor específico",
            }
        ] + [
            {
                "key": str(s["id"]),
                "label": s["name"],
                "subtitle": f"Contacto: {s.get('contact_name') or 'N/A'}  •  Tel: {s.get('phone') or 'N/A'}",
            }
            for s in suppliers
        ]

        supplier_dd = SearchableDropdown(
            label="Seleccionar Proveedor",
            hint_text="Seleccione de la lista o escriba desde la 1ª letra...",
            prefix_icon=ft.Icons.LOCAL_SHIPPING_ROUNDED,
            options=supplier_options,
            value=str(suppliers[0]["id"]) if suppliers else "",
            max_list_height=160,
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

            sup_val = str(supplier_dd.value or "").strip()
            sup_id = int(sup_val) if sup_val.isdigit() else None

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
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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
