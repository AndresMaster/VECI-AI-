import flet as ft
from typing import Optional, Dict, Any
from config import PastelTheme
from controllers import InventoryController
from views.theme import create_card, create_badge, safe_update

class InventoryView(ft.Container):
    """
    Vista de Gestión de Inventario (CRUD Completo).
    - Agregar, Editar, Eliminar productos.
    - Campos: Código de barras, Nombre, Costo de Compra, Precio de Venta, Cantidad/Stock, Stock Mínimo.
    - Utilidad calculada automáticamente en tiempo real.
    - Búsqueda en vivo y alertas visuales de stock bajo.
    """
    def __init__(self, inventory_controller: InventoryController):
        super().__init__(expand=True)
        self.controller = inventory_controller
        self.padding = 24

        self.search_field = ft.TextField(
            hint_text="Buscar por nombre, código o categoría...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=PastelTheme.BORDER_RADIUS_INPUT,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_color=PastelTheme.BORDER_LIGHT,
            dense=True,
            expand=True,
            on_change=lambda _: self.load_products()
        )

        self.table_column = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

        self.content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Header & Actions
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text("Catálogo de Inventario", size=24, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                ft.Text("Control de existencias, cálculo de márgenes y administración de productos", size=13, color=PastelTheme.TEXT_SECONDARY)
                            ]
                        ),
                        ft.FilledButton(
                            content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, size=18), ft.Text("Nuevo Producto")]),
                            style=ft.ButtonStyle(
                                bgcolor=PastelTheme.PRIMARY,
                                color=PastelTheme.TEXT_ON_PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                padding=ft.Padding.symmetric(horizontal=16, vertical=12)
                            ),
                            on_click=lambda _: self.show_product_dialog()
                        )
                    ]
                ),

                # Search Bar Card
                create_card(
                    content=ft.Row(
                        controls=[
                            self.search_field,
                            ft.IconButton(
                                icon=ft.Icons.REFRESH_ROUNDED,
                                tooltip="Refrescar lista",
                                on_click=lambda _: self.load_products()
                            )
                        ]
                    ),
                    padding=10
                ),

                # Product Data Table Card
                create_card(
                    content=ft.Column(
                        expand=True,
                        controls=[
                            # Table Header
                            ft.Container(
                                bgcolor=PastelTheme.SURFACE_VARIANT,
                                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                                border_radius=8,
                                content=ft.Row(
                                    controls=[
                                        ft.Text("Código", width=110, weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                                        ft.Text("Producto / Categoría", expand=3, weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                                        ft.Text("Presentación", width=95, weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                                        ft.Text("Costo", width=85, weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                                        ft.Text("Venta", width=85, weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                                        ft.Text("Utilidad", width=85, weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                                        ft.Text("Margen", width=65, weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                                        ft.Text("Stock", width=85, weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                                        ft.Text("Acciones", width=80, text_align=ft.TextAlign.RIGHT, weight=ft.FontWeight.BOLD, size=12, color=PastelTheme.TEXT_SECONDARY),
                                    ]
                                )
                            ),
                            # Table Rows
                            self.table_column
                        ]
                    ),
                    expand=True,
                    padding=14
                )
            ]
        )

        self.load_products()

    def load_products(self) -> None:
        """Carga la lista de productos filtrada desde la base de datos."""
        query = self.search_field.value or ""
        products = self.controller.get_all_products(query)

        rows = []
        for p in products:
            is_low = p["is_low_stock"]
            stock_badge = (
                create_badge(f"{p['stock']} (Bajo)", PastelTheme.CORAL_PASTEL, PastelTheme.ACCENT_CORAL)
                if is_low else
                create_badge(f"{p['stock']} uds", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)
            )

            row = ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                border=ft.Border.only(bottom=ft.BorderSide(1, PastelTheme.BORDER_LIGHT)),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(p["barcode"], width=110, size=12, weight=ft.FontWeight.W_500, color=PastelTheme.TEXT_PRIMARY),
                        ft.Column(
                            expand=3,
                            spacing=1,
                            controls=[
                                ft.Text(p["name"], size=13, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                ft.Text(p["category"] or "General", size=11, color=PastelTheme.TEXT_MUTED)
                            ]
                        ),
                        ft.Container(
                            width=95,
                            content=create_badge(p.get("presentacion") or "N/A", PastelTheme.SURFACE_VARIANT, PastelTheme.TEXT_SECONDARY)
                            if p.get("presentacion") else
                            ft.Text("-", size=12, color=PastelTheme.TEXT_MUTED)
                        ),
                        ft.Text(f"${p['cost_price']:,.0f}", width=85, size=12, color=PastelTheme.TEXT_SECONDARY),
                        ft.Text(f"${p['sale_price']:,.0f}", width=85, size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.PRIMARY),
                        ft.Text(f"+${p['unit_profit']:,.0f}", width=85, size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.ACCENT_MINT),
                        ft.Text(f"{p['profit_margin_percent']:.1f}%", width=65, size=12, color=PastelTheme.TEXT_SECONDARY),
                        ft.Container(content=stock_badge, width=85),
                        ft.Row(
                            width=80,
                            spacing=2,
                            alignment=ft.MainAxisAlignment.END,
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.EDIT_ROUNDED,
                                    icon_color=PastelTheme.PRIMARY,
                                    icon_size=18,
                                    tooltip="Editar producto",
                                    on_click=lambda _, prod=p: self.show_product_dialog(prod)
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                    icon_color=PastelTheme.ACCENT_CORAL,
                                    icon_size=18,
                                    tooltip="Eliminar producto",
                                    on_click=lambda _, pid=p["id"], name=p["name"]: self.confirm_delete(pid, name)
                                )
                            ]
                        )
                    ]
                )
            )
            rows.append(row)

        if not rows:
            rows.append(
                ft.Container(
                    padding=30,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("No se encontraron productos registrados.", color=PastelTheme.TEXT_MUTED)
                )
            )

        self.table_column.controls = rows
        safe_update(self)

    def show_product_dialog(self, product: Optional[Dict[str, Any]] = None) -> None:
        """Modal interactivo para Crear o Editar producto con cálculo dinámico de utilidad y búsqueda en Open Food Facts."""
        is_edit = product is not None

        barcode_tf = ft.TextField(
            label="Código de barras",
            value=product["barcode"] if is_edit else "",
            border_radius=8,
            dense=True,
            expand=True
        )
        name_tf = ft.TextField(
            label="Nombre del producto",
            value=product["name"] if is_edit else "",
            border_radius=8,
            dense=True
        )
        presentacion_tf = ft.TextField(
            label="Presentación (ej. 65g, 500ml, 1kg)",
            value=product.get("presentacion", "") if is_edit else "",
            border_radius=8,
            dense=True
        )
        cost_tf = ft.TextField(
            label="Costo de Compra ($)",
            value=str(product["cost_price"]) if is_edit else "0",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            dense=True
        )
        sale_tf = ft.TextField(
            label="Precio de Venta ($)",
            value=str(product["sale_price"]) if is_edit else "0",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            dense=True
        )
        stock_tf = ft.TextField(
            label="Cantidad en Stock",
            value=str(product["stock"]) if is_edit else "0",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            dense=True
        )
        min_stock_tf = ft.TextField(
            label="Stock Mínimo (Alerta)",
            value=str(product["min_stock"]) if is_edit else "5",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            dense=True
        )
        category_tf = ft.TextField(
            label="Categoría",
            value=product["category"] if is_edit else "General",
            border_radius=8,
            dense=True
        )

        profit_preview = ft.Text("Utilidad: $0.00 (0%)", weight=ft.FontWeight.BOLD, color=PastelTheme.ACCENT_MINT)
        off_status_text = ft.Text("", size=11, visible=False)

        def recalculate_profit(_=None):
            try:
                c = float(cost_tf.value or 0)
                s = float(sale_tf.value or 0)
                profit = s - c
                pct = ((s - c) / s * 100) if s > 0 else 0
                profit_preview.value = f"Utilidad calculada: ${profit:,.2f} ({pct:.1f}%)"
                profit_preview.color = PastelTheme.ACCENT_MINT if profit >= 0 else PastelTheme.ACCENT_CORAL
            except ValueError:
                profit_preview.value = "Valores de precio no válidos"
                profit_preview.color = PastelTheme.ACCENT_CORAL
            safe_update(profit_preview)

        cost_tf.on_change = recalculate_profit
        sale_tf.on_change = recalculate_profit
        recalculate_profit()

        def lookup_open_food_facts(_=None):
            code = (barcode_tf.value or "").strip()
            if not code:
                off_status_text.value = "Ingresa un código de barras primero."
                off_status_text.color = PastelTheme.ACCENT_CORAL
                off_status_text.visible = True
                safe_update(off_status_text)
                return

            off_status_text.value = "Consultando Open Food Facts..."
            off_status_text.color = PastelTheme.TEXT_SECONDARY
            off_status_text.visible = True
            safe_update(off_status_text)

            res = self.controller.lookup_open_food_facts(code)
            if res.get("found"):
                if res.get("name"):
                    name_tf.value = res["name"]
                if res.get("quantity"):
                    presentacion_tf.value = res["quantity"]
                if res.get("category"):
                    category_tf.value = res["category"]
                off_status_text.value = f"¡Encontrado! {res.get('display_name', '')}"
                off_status_text.color = PastelTheme.ACCENT_MINT
            else:
                off_status_text.value = res.get("error", "No encontrado en Open Food Facts.")
                off_status_text.color = PastelTheme.ACCENT_CORAL

            safe_update(dialog)

        barcode_tf.on_submit = lookup_open_food_facts

        def save_product(_):
            try:
                c_val = float(cost_tf.value)
                s_val = float(sale_tf.value)
                stk_val = int(stock_tf.value)
                min_stk_val = int(min_stock_tf.value)
            except ValueError:
                return

            if is_edit:
                success, msg, _ = self.controller.update_product(
                    product_id=product["id"],
                    barcode=barcode_tf.value,
                    name=name_tf.value,
                    cost_price=c_val,
                    sale_price=s_val,
                    stock=stk_val,
                    min_stock=min_stk_val,
                    presentacion=presentacion_tf.value,
                    category=category_tf.value
                )
            else:
                success, msg, _ = self.controller.create_product(
                    barcode=barcode_tf.value,
                    name=name_tf.value,
                    cost_price=c_val,
                    sale_price=s_val,
                    stock=stk_val,
                    min_stock=min_stk_val,
                    presentacion=presentacion_tf.value,
                    category=category_tf.value
                )

            if success:
                self.page.pop_dialog()
                self.load_products()

        dialog = ft.AlertDialog(
            title=ft.Text("Editar Producto" if is_edit else "Registrar Nuevo Producto", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=460,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                barcode_tf,
                                ft.IconButton(
                                    icon=ft.Icons.TRAVEL_EXPLORE_ROUNDED,
                                    tooltip="Consultar Open Food Facts (autocompletar)",
                                    icon_color=PastelTheme.PRIMARY,
                                    on_click=lookup_open_food_facts
                                )
                            ]
                        ),
                        off_status_text,
                        name_tf,
                        presentacion_tf,
                        ft.Row([cost_tf, sale_tf]),
                        ft.Container(
                            bgcolor=PastelTheme.MINT_PASTEL,
                            padding=10,
                            border_radius=8,
                            content=profit_preview
                        ),
                        ft.Row([stock_tf, min_stock_tf]),
                        category_tf
                    ]
                )
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.FilledButton(
                    "Guardar",
                    bgcolor=PastelTheme.PRIMARY,
                    color=PastelTheme.TEXT_ON_PRIMARY,
                    on_click=save_product
                )
            ]
        )
        self.page.show_dialog(dialog)

    def confirm_delete(self, product_id: int, product_name: str) -> None:
        """Modal de confirmación para eliminar un producto."""
        def delete_confirmed(_):
            self.controller.delete_product(product_id)
            self.page.pop_dialog()
            self.load_products()

        dialog = ft.AlertDialog(
            title=ft.Text("Confirmar eliminación", weight=ft.FontWeight.BOLD),
            content=ft.Text(f"¿Estás seguro de que deseas eliminar '{product_name}' del inventario?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                ft.FilledButton(
                    "Eliminar",
                    bgcolor=PastelTheme.ACCENT_CORAL,
                    color=PastelTheme.TEXT_ON_PRIMARY,
                    on_click=delete_confirmed
                )
            ]
        )
        self.page.show_dialog(dialog)
