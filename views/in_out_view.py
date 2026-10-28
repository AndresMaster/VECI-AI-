import flet as ft
from typing import Optional, Dict, Any, Callable
from config import PastelTheme
from controllers import InventoryController
from views.theme import create_card, create_badge, create_metric_tile, safe_update


class InOutView(ft.Container):
    """
    Vista del Módulo 'In/Out' (Entradas y Salidas Rápidas de Inventario).
    - Muestra el listado completo de productos del inventario con filtro instantáneo por nombre o código.
    - Al hacer clic sobre cualquier producto, abre una ventana modal para Añadir (In) o Restar (Out)
      unidades del stock actual, actualizando automáticamente las cantidades y el Valor del Inventario.
    """

    def __init__(
        self,
        inventory_controller: InventoryController,
        on_inventory_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__(expand=True)
        self.controller = inventory_controller
        self.on_inventory_changed = on_inventory_changed
        self.padding = 24

        self.summary_kpi_row = ft.Row(spacing=16)

        # Estado de Paginación Server-Side / SQLite (LIMIT 50 OFFSET X)
        self.current_page: int = 1
        self.page_size: int = 50
        self.total_pages: int = 1
        self.total_records: int = 0

        self.search_field = ft.TextField(
            hint_text="Buscar producto por nombre, presentación o código de barras para ajustar cantidad...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=PastelTheme.BORDER_RADIUS_INPUT,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_color=PastelTheme.BORDER_LIGHT,
            dense=True,
            expand=True,
            on_change=self._on_search_change,
        )

        self.feedback_banner = ft.Container(
            visible=False,
            bgcolor=PastelTheme.MINT_PASTEL,
            border_radius=10,
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border=ft.Border.all(1, PastelTheme.ACCENT_MINT),
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18, color=PastelTheme.ACCENT_MINT),
                    ft.Text("", size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY, expand=True),
                ],
            ),
        )

        self.table_column = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

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
            "0 registros",
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
        self.pagination_bar = ft.Container(
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

        self.content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Cabecera de la sección In/Out
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text(
                                    "Control de Entradas y Salidas (In / Out)",
                                    size=24,
                                    weight=ft.FontWeight.BOLD,
                                    color=PastelTheme.TEXT_PRIMARY,
                                ),
                                ft.Text(
                                    "Haz clic sobre cualquier producto para sumar nuevas existencias (In) o descontar unidades (Out)",
                                    size=13,
                                    color=PastelTheme.TEXT_SECONDARY,
                                ),
                            ],
                        ),
                        ft.FilledButton(
                            content=ft.Row([
                                ft.Icon(ft.Icons.REFRESH_ROUNDED, size=18),
                                ft.Text("Actualizar"),
                            ]),
                            style=ft.ButtonStyle(
                                bgcolor=PastelTheme.PRIMARY_PASTEL,
                                color=PastelTheme.PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                elevation=0,
                            ),
                            on_click=lambda _: self.load_products(),
                        ),
                    ],
                ),

                # Casillas de resumen en vivo
                self.summary_kpi_row,

                # Barra de búsqueda por nombre o código
                create_card(
                    padding=10,
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Row(
                                controls=[
                                    self.search_field,
                                    ft.IconButton(
                                        icon=ft.Icons.CLEAR_ROUNDED,
                                        tooltip="Limpiar búsqueda",
                                        on_click=self._clear_search,
                                    ),
                                ]
                            ),
                            self.feedback_banner,
                        ],
                    ),
                ),

                # Tabla interactiva de productos
                create_card(
                    expand=True,
                    padding=14,
                    content=ft.Column(
                        expand=True,
                        controls=[
                            ft.Container(
                                bgcolor=PastelTheme.SURFACE_VARIANT,
                                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                                border_radius=8,
                                content=ft.Row(
                                    controls=[
                                        ft.Text(
                                            "Código",
                                            width=115,
                                            weight=ft.FontWeight.BOLD,
                                            size=12,
                                            color=PastelTheme.TEXT_SECONDARY,
                                        ),
                                        ft.Text(
                                            "Producto / Categoría (Clic para ajustar)",
                                            expand=3,
                                            weight=ft.FontWeight.BOLD,
                                            size=12,
                                            color=PastelTheme.TEXT_SECONDARY,
                                        ),
                                        ft.Text(
                                            "Presentación",
                                            width=100,
                                            weight=ft.FontWeight.BOLD,
                                            size=12,
                                            color=PastelTheme.TEXT_SECONDARY,
                                        ),
                                        ft.Text(
                                            "Costo Unit.",
                                            width=95,
                                            weight=ft.FontWeight.BOLD,
                                            size=12,
                                            color=PastelTheme.TEXT_SECONDARY,
                                        ),
                                        ft.Text(
                                            "Valor en Inv.",
                                            width=110,
                                            weight=ft.FontWeight.BOLD,
                                            size=12,
                                            color=PastelTheme.TEXT_SECONDARY,
                                        ),
                                        ft.Text(
                                            "Stock Actual",
                                            width=105,
                                            weight=ft.FontWeight.BOLD,
                                            size=12,
                                            color=PastelTheme.TEXT_SECONDARY,
                                        ),
                                        ft.Text(
                                            "Movimiento",
                                            width=130,
                                            text_align=ft.TextAlign.RIGHT,
                                            weight=ft.FontWeight.BOLD,
                                            size=12,
                                            color=PastelTheme.TEXT_SECONDARY,
                                        ),
                                    ]
                                ),
                            ),
                            self.table_column,
                            self.pagination_bar,
                        ],
                    ),
                ),
            ],
        )

        self.load_products()

    def _on_search_change(self, _=None) -> None:
        self.current_page = 1
        self.load_products()

    def _clear_search(self, _=None) -> None:
        self.search_field.value = ""
        self.current_page = 1
        self.load_products()

    def _on_prev_page(self, _=None) -> None:
        if self.current_page > 1:
            self.current_page -= 1
            self.load_products()

    def _on_next_page(self, _=None) -> None:
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_products()

    def load_products(self) -> None:
        """Carga únicamente 50 productos por página (LIMIT 50 OFFSET X) y actualiza métricas de inventario."""
        query = self.search_field.value or ""
        paginated = self.controller.get_products_paginated(
            search_query=query,
            page=self.current_page,
            page_size=self.page_size,
        )
        products = paginated["items"]
        self.current_page = paginated["page"]
        self.total_pages = paginated["total_pages"]
        self.total_records = paginated["total_records"]
        offset_val = paginated["offset"]

        total_units = paginated["total_units"]
        total_by_name = paginated["total_by_name"]
        total_inv_cost = paginated["total_inventory_cost"]

        start_idx = (offset_val + 1) if self.total_records > 0 else 0
        end_idx = min(offset_val + len(products), self.total_records)
        self.page_indicator_text.value = f"Página {self.current_page} de {self.total_pages}"
        self.records_range_text.value = (
            f"Mostrando {start_idx}–{end_idx} de {self.total_records:,} productos (50 por página)"
        )
        self.prev_page_btn.disabled = (self.current_page <= 1)
        self.next_page_btn.disabled = (self.current_page >= self.total_pages)

        self.summary_kpi_row.controls = [
            create_metric_tile(
                title="Total Unidades en Inventario",
                value=f"{total_units:,} productos",
                icon=ft.Icons.INVENTORY_ROUNDED,
                bg_pastel=PastelTheme.SKY_PASTEL,
                icon_color=PastelTheme.ACCENT_SKY,
                subtitle="Suma total de existencias actuales",
            ),
            create_metric_tile(
                title="Valor Total de Inventario",
                value=f"${total_inv_cost:,.0f}",
                icon=ft.Icons.MONETIZATION_ON_ROUNDED,
                bg_pastel=PastelTheme.PRIMARY_PASTEL,
                icon_color=PastelTheme.PRIMARY,
                subtitle="Capital actual en mercancía (Costo × Stock)",
            ),
            create_metric_tile(
                title="Productos por Nombre",
                value=f"{total_by_name:,} productos",
                icon=ft.Icons.CATEGORY_ROUNDED,
                bg_pastel=PastelTheme.MINT_PASTEL,
                icon_color=PastelTheme.ACCENT_MINT,
                subtitle="Referencias registradas en el catálogo",
            ),
        ]

        rows = []
        for p in products:
            is_low = p["is_low_stock"]
            stock_badge = (
                create_badge(f"{p['stock']} uds (Bajo)", PastelTheme.CORAL_PASTEL, PastelTheme.ACCENT_CORAL)
                if is_low
                else create_badge(f"{p['stock']} uds", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)
            )

            row = ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                border=ft.Border.only(bottom=ft.BorderSide(1, PastelTheme.BORDER_LIGHT)),
                border_radius=8,
                ink=True,
                tooltip=f"Clic para Añadir o Restar unidades de '{p['display_name']}'",
                on_click=lambda _, prod=p: self.show_in_out_modal(prod),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            p["barcode"],
                            width=115,
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=PastelTheme.TEXT_PRIMARY,
                        ),
                        ft.Column(
                            expand=3,
                            spacing=1,
                            controls=[
                                ft.Text(
                                    p["name"],
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=PastelTheme.TEXT_PRIMARY,
                                ),
                                ft.Text(
                                    p["category"] or "General",
                                    size=11,
                                    color=PastelTheme.TEXT_MUTED,
                                ),
                            ],
                        ),
                        ft.Container(
                            width=100,
                            content=(
                                create_badge(
                                    p.get("presentacion") or "N/A",
                                    PastelTheme.SURFACE_VARIANT,
                                    PastelTheme.TEXT_SECONDARY,
                                )
                                if p.get("presentacion")
                                else ft.Text("-", size=12, color=PastelTheme.TEXT_MUTED)
                            ),
                        ),
                        ft.Text(
                            f"${p['cost_price']:,.0f}",
                            width=95,
                            size=12,
                            color=PastelTheme.TEXT_SECONDARY,
                        ),
                        ft.Text(
                            f"${p['total_cost_value']:,.0f}",
                            width=110,
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=PastelTheme.PRIMARY,
                        ),
                        ft.Container(content=stock_badge, width=105),
                        ft.Container(
                            width=130,
                            alignment=ft.Alignment.CENTER_RIGHT,
                            content=ft.OutlinedButton(
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.SWAP_VERT_ROUNDED, size=16, color=PastelTheme.PRIMARY),
                                        ft.Text(
                                            "In / Out",
                                            size=12,
                                            weight=ft.FontWeight.BOLD,
                                            color=PastelTheme.PRIMARY,
                                        ),
                                    ],
                                ),
                                style=ft.ButtonStyle(
                                    bgcolor=PastelTheme.PRIMARY_PASTEL,
                                    side=ft.BorderSide(1, PastelTheme.PRIMARY),
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                ),
                                on_click=lambda _, prod=p: self.show_in_out_modal(prod),
                            ),
                        ),
                    ],
                ),
            )
            rows.append(row)

        if not rows:
            rows.append(
                ft.Container(
                    padding=30,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(
                        "No se encontraron productos con ese nombre o código.",
                        color=PastelTheme.TEXT_MUTED,
                    ),
                )
            )

        self.table_column.controls = rows
        safe_update(self)

    def show_in_out_modal(self, product: Dict[str, Any]) -> None:
        """
        Abre la ventana modal de Ajuste In/Out para Añadir (sumar) o Restar unidades
        al stock actual del producto seleccionado, actualizando su cantidad y el Valor en Inventario.
        """
        current_stock = int(product.get("stock", 0))
        cost_price = float(product.get("cost_price", 0.0))
        current_inv_val = round(current_stock * cost_price, 2)

        qty_tf = ft.TextField(
            label="Cantidad de unidades a Añadir (+) o Restar (-)",
            hint_text="Ej. 10",
            value="",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.Icons. EXPOSURE_ROUNDED,
            border_radius=10,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_color=PastelTheme.PRIMARY,
            autofocus=True,
            dense=True,
        )

        preview_in_text = ft.Text(
            f"Si Añades (+0): Stock quedará en {current_stock} uds (${current_inv_val:,.0f})",
            size=12,
            weight=ft.FontWeight.W_600,
            color=PastelTheme.ACCENT_MINT,
        )
        preview_out_text = ft.Text(
            f"Si Restas (-0): Stock quedará en {current_stock} uds (${current_inv_val:,.0f})",
            size=12,
            weight=ft.FontWeight.W_600,
            color=PastelTheme.ACCENT_CORAL,
        )

        error_text = ft.Text("", size=12, color=PastelTheme.ACCENT_CORAL, visible=False)

        def parse_qty() -> Optional[int]:
            raw = (qty_tf.value or "").strip()
            if not raw:
                return None
            try:
                val = int(float(raw))
                return val if val > 0 else None
            except ValueError:
                return None

        def update_preview(_=None):
            error_text.visible = False
            q = parse_qty() or 0
            stock_after_in = current_stock + q
            val_after_in = stock_after_in * cost_price
            preview_in_text.value = (
                f"• Si Añades (+{q}): Nuevo stock = {stock_after_in} uds  |  "
                f"Nuevo valor inv. = ${val_after_in:,.0f}"
            )

            stock_after_out = current_stock - q
            if stock_after_out >= 0:
                val_after_out = stock_after_out * cost_price
                preview_out_text.value = (
                    f"• Si Restas (-{q}): Nuevo stock = {stock_after_out} uds  |  "
                    f"Nuevo valor inv. = ${val_after_out:,.0f}"
                )
            else:
                preview_out_text.value = (
                    f"• Si Restas (-{q}): Excede el stock disponible ({current_stock} uds)"
                )
            safe_update(preview_in_text)
            safe_update(preview_out_text)
            safe_update(error_text)

        qty_tf.on_change = update_preview

        def set_quick_qty(amount: int):
            current_val = parse_qty() or 0
            qty_tf.value = str(current_val + amount)
            update_preview()
            safe_update(qty_tf)

        def apply_movement(is_addition: bool):
            qty = parse_qty()
            if qty is None or qty <= 0:
                error_text.value = "Por favor ingresa una cantidad válida mayor a 0."
                error_text.visible = True
                safe_update(error_text)
                return

            delta = qty if is_addition else -qty
            ok, msg, _ = self.controller.adjust_product_stock(
                product_id=product["id"],
                quantity_delta=delta,
            )
            if not ok:
                error_text.value = msg
                error_text.visible = True
                safe_update(error_text)
                return

            self.page.pop_dialog()
            self.feedback_banner.content.controls[1].value = msg
            self.feedback_banner.visible = True
            self.load_products()
            if self.on_inventory_changed is not None:
                try:
                    self.on_inventory_changed()
                except Exception:
                    pass

        dialog = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=PastelTheme.SURFACE_WHITE,
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.SWAP_VERT_CIRCLE_ROUNDED, color=PastelTheme.PRIMARY, size=26),
                    ft.Text(
                        "Ajustar Cantidad en Inventario (In / Out)",
                        weight=ft.FontWeight.BOLD,
                        size=17,
                    ),
                ],
            ),
            content=ft.Container(
                width=500,
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        # Tarjeta con estado actual del producto
                        ft.Container(
                            bgcolor=PastelTheme.PRIMARY_PASTEL,
                            border_radius=12,
                            padding=14,
                            border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
                            content=ft.Column(
                                spacing=6,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text(
                                                product.get("display_name") or product["name"],
                                                size=15,
                                                weight=ft.FontWeight.BOLD,
                                                color=PastelTheme.TEXT_PRIMARY,
                                                expand=True,
                                            ),
                                            create_badge(
                                                f"Código: {product['barcode']}",
                                                PastelTheme.SURFACE_WHITE,
                                                PastelTheme.TEXT_SECONDARY,
                                            ),
                                        ],
                                    ),
                                    ft.Divider(height=1, color=PastelTheme.BORDER_LIGHT),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text(
                                                f"Stock Actual: {current_stock} unidades",
                                                size=13,
                                                weight=ft.FontWeight.BOLD,
                                                color=PastelTheme.PRIMARY,
                                            ),
                                            ft.Text(
                                                f"Valor Actual Inv.: ${current_inv_val:,.0f} (${cost_price:,.0f} c/u)",
                                                size=12,
                                                weight=ft.FontWeight.W_600,
                                                color=PastelTheme.TEXT_SECONDARY,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ),

                        # Campo de cantidad y botones rápidos
                        qty_tf,
                        ft.Row(
                            spacing=8,
                            alignment=ft.MainAxisAlignment.START,
                            controls=[
                                ft.Text("Sumar rápido:", size=11, color=PastelTheme.TEXT_SECONDARY),
                                ft.OutlinedButton(
                                    "+1",
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                    ),
                                    on_click=lambda _: set_quick_qty(1),
                                ),
                                ft.OutlinedButton(
                                    "+5",
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                    ),
                                    on_click=lambda _: set_quick_qty(5),
                                ),
                                ft.OutlinedButton(
                                    "+10",
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                    ),
                                    on_click=lambda _: set_quick_qty(10),
                                ),
                                ft.OutlinedButton(
                                    "+24",
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                    ),
                                    on_click=lambda _: set_quick_qty(24),
                                ),
                            ],
                        ),

                        # Vista previa del ajuste
                        ft.Container(
                            bgcolor=PastelTheme.SURFACE_VARIANT,
                            border_radius=10,
                            padding=12,
                            content=ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Text(
                                        "Vista Previa del Movimiento:",
                                        size=11,
                                        weight=ft.FontWeight.BOLD,
                                        color=PastelTheme.TEXT_SECONDARY,
                                    ),
                                    preview_in_text,
                                    preview_out_text,
                                ],
                            ),
                        ),

                        error_text,

                        # Botones principales: Añadir (In) y Restar (Out)
                        ft.Row(
                            spacing=12,
                            controls=[
                                ft.FilledButton(
                                    expand=True,
                                    content=ft.Row(
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        spacing=6,
                                        controls=[
                                            ft.Icon(ft.Icons.ADD_CIRCLE_ROUNDED, size=18),
                                            ft.Text("Añadir Stock (+ In)", weight=ft.FontWeight.BOLD, size=13),
                                        ],
                                    ),
                                    style=ft.ButtonStyle(
                                        bgcolor=PastelTheme.ACCENT_MINT,
                                        color=PastelTheme.TEXT_ON_PRIMARY,
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        padding=ft.Padding.symmetric(vertical=14),
                                    ),
                                    on_click=lambda _: apply_movement(is_addition=True),
                                ),
                                ft.FilledButton(
                                    expand=True,
                                    content=ft.Row(
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        spacing=6,
                                        controls=[
                                            ft.Icon(ft.Icons.REMOVE_CIRCLE_ROUNDED, size=18),
                                            ft.Text("Restar Stock (- Out)", weight=ft.FontWeight.BOLD, size=13),
                                        ],
                                    ),
                                    style=ft.ButtonStyle(
                                        bgcolor=PastelTheme.ACCENT_CORAL,
                                        color=PastelTheme.TEXT_ON_PRIMARY,
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                        padding=ft.Padding.symmetric(vertical=14),
                                    ),
                                    on_click=lambda _: apply_movement(is_addition=False),
                                ),
                            ],
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialog)
