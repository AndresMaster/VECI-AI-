import flet as ft
from typing import Optional, Dict, Any
from config import PastelTheme
from controllers import InventoryController
from services.barcode_manager import BarcodeManager, ScannerMode
from views.theme import create_card, create_badge, safe_update
from views.pos_view import _INITIAL_CAMERA_URI

class InventoryView(ft.Container):
    """
    Vista de Gestión de Inventario (CRUD Completo).
    - Agregar, Editar, Eliminar productos.
    - Campos: Código de barras, Nombre, Costo de Compra, Precio de Venta, Cantidad/Stock, Stock Mínimo.
    - Utilidad calculada automáticamente en tiempo real.
    - Búsqueda en vivo y alertas visuales de stock bajo.
    - Integración de escaneo con cámara (LectorBarr) y autocompletado desde Open Food Facts.
    """
    def __init__(
        self,
        inventory_controller: InventoryController,
        barcode_manager: Optional[BarcodeManager] = None,
        pos_view: Optional[Any] = None
    ):
        super().__init__(expand=True)
        self.controller = inventory_controller
        self.barcode_mgr = barcode_manager
        self.pos_view = pos_view
        self.padding = 24
        self.active_barcode_callback = None

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
                # Header & Actions (Opciones: Escanear con Cámara o Registro Manual)
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
                        ft.Row([
                            ft.FilledButton(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.QR_CODE_SCANNER_ROUNDED, size=18),
                                    ft.Text("Agregar con Código de Barras")
                                ]),
                                style=ft.ButtonStyle(
                                    bgcolor=PastelTheme.PRIMARY,
                                    color=PastelTheme.TEXT_ON_PRIMARY,
                                    shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                    padding=ft.Padding.symmetric(horizontal=16, vertical=12)
                                ),
                                tooltip="Escanear con cámara y autocompletar automáticamente desde internet",
                                on_click=lambda _: self.show_scan_and_create_dialog()
                            ),
                            ft.OutlinedButton(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=18),
                                    ft.Text("Nuevo Producto (Manual)")
                                ]),
                                style=ft.ButtonStyle(
                                    color=PastelTheme.PRIMARY,
                                    shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                    padding=ft.Padding.symmetric(horizontal=16, vertical=12)
                                ),
                                tooltip="Ingresar todos los datos del producto manualmente",
                                on_click=lambda _: self.show_product_dialog()
                            )
                        ], spacing=10)
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

    def show_scan_and_create_dialog(self) -> None:
        """Modal interactivo para escanear un código de barras por cámara o USB y autocompletar desde internet."""
        if not self.barcode_mgr:
            self.show_product_dialog()
            return

        scan_img = ft.Image(
            src=_INITIAL_CAMERA_URI,
            fit=ft.BoxFit.CONTAIN,
            width=360,
            height=230,
            border_radius=8,
            gapless_playback=True
        )

        scan_status_text = ft.Text(
            f"Cámara activa (Índice {self.barcode_mgr.camera_index}). Ubique el código dentro del recuadro central.",
            size=12,
            weight=ft.FontWeight.W_500,
            color=PastelTheme.TEXT_SECONDARY
        )

        manual_code_tf = ft.TextField(
            hint_text="O digite el código de barras y presione Enter...",
            prefix_icon=ft.Icons.KEYBOARD_ROUNDED,
            border_radius=8,
            dense=True,
            expand=True
        )

        prev_mode = self.barcode_mgr.mode
        is_closing = False

        def on_cam_frame(b64_uri: str):
            if not is_closing:
                scan_img.src = b64_uri
                safe_update(scan_img)

        def on_cam_progress(code: str, current: int, required: int):
            if is_closing:
                return
            if not code or current == 0:
                scan_status_text.value = f"Cámara activa (Índice {self.barcode_mgr.camera_index}). Ubique el código dentro del recuadro."
                scan_status_text.color = PastelTheme.TEXT_SECONDARY
            elif current >= required:
                scan_status_text.value = f"¡Código {code} confirmado ({current}/{required})! Consultando información..."
                scan_status_text.color = PastelTheme.ACCENT_MINT
            else:
                scan_status_text.value = f"Detectando {code}... Muestras: {current}/{required}"
                scan_status_text.color = PastelTheme.ACCENT_AMBER
            safe_update(scan_status_text)

        def cleanup_scanner():
            nonlocal is_closing
            is_closing = True
            self.active_barcode_callback = None
            if hasattr(self.barcode_mgr, "stop_native_window") and self.barcode_mgr.is_native_window_running():
                self.barcode_mgr.stop_native_window()

            # Restaurar callbacks del POS si existen
            if self.pos_view:
                self.barcode_mgr.set_preview_callback(self.pos_view._on_camera_preview_frame)
                self.barcode_mgr.set_verification_callback(self.pos_view._on_camera_verification_progress)
            else:
                self.barcode_mgr.set_preview_callback(None)
                self.barcode_mgr.set_verification_callback(None)

            # Si el POS no estaba usando la cámara, regresar al modo previo
            if prev_mode != ScannerMode.CAMERA:
                self.barcode_mgr.set_mode(prev_mode)

        def close_dialog(_=None):
            cleanup_scanner()
            self.page.pop_dialog()

        def process_scanned_barcode(scanned_code: str):
            code = (scanned_code or "").strip()
            if not code:
                return

            # Cerrar el modal de escaneo y limpiar recursos de cámara
            close_dialog()

            # 1. Comprobar en SQLite local y Open Food Facts
            lookup = self.controller.scan_or_lookup_barcode_for_new(code)
            status = lookup.get("status")

            if status == "EXISTS_LOCAL":
                existing = lookup["product"]
                def edit_existing(_):
                    self.page.pop_dialog()
                    self.show_product_dialog(existing)

                alert_dialog = ft.AlertDialog(
                    title=ft.Row([
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=PastelTheme.ACCENT_AMBER, size=24),
                        ft.Text("Producto ya registrado", weight=ft.FontWeight.BOLD)
                    ]),
                    content=ft.Text(
                        f"El código {code} ya está registrado en tu inventario como:\n\n"
                        f"• {existing.get('display_name')}\n"
                        f"• Precio de Venta: ${existing.get('sale_price', 0):,.0f}\n"
                        f"• Stock actual: {existing.get('stock', 0)} unidades\n\n"
                        "¿Deseas editar el producto existente en lugar de duplicarlo?",
                        size=13
                    ),
                    actions=[
                        ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                        ft.FilledButton(
                            "Editar Producto Existente",
                            bgcolor=PastelTheme.PRIMARY,
                            color=PastelTheme.TEXT_ON_PRIMARY,
                            on_click=edit_existing
                        )
                    ]
                )
                self.page.show_dialog(alert_dialog)
                return

            elif status == "OFF_FOUND":
                data = lookup.get("data", {})
                p_name = data.get("product_name") or data.get("name") or ""
                p_brand = data.get("brands") or ""
                p_qty = data.get("quantity") or ""
                p_cat = data.get("category") or "General"
                init_data = {
                    "barcode": code,
                    "name": p_name,
                    "brand": p_brand,
                    "presentacion": p_qty,
                    "category": p_cat,
                    "is_off_found": True,
                    "status_message": f"✓ ¡Información autocompletada desde Open Food Facts! {p_name}"
                }
                self.show_product_dialog(initial_scan_data=init_data)
            else:
                init_data = {
                    "barcode": code,
                    "name": "",
                    "brand": "",
                    "presentacion": "",
                    "category": "General",
                    "is_off_found": False,
                    "status_message": f"⚠ Código {code} escaneado. No registrado en Open Food Facts. Por favor complete los datos manualmente."
                }
                self.show_product_dialog(initial_scan_data=init_data)

        self.active_barcode_callback = process_scanned_barcode
        manual_code_tf.on_submit = lambda _: process_scanned_barcode(manual_code_tf.value)

        # Configurar callbacks de video para este modal
        self.barcode_mgr.set_preview_callback(on_cam_frame)
        self.barcode_mgr.set_verification_callback(on_cam_progress)

        if not self.barcode_mgr.camera_scanner.is_running():
            self.barcode_mgr.set_mode(ScannerMode.CAMERA)

        def switch_cam_index(idx: int):
            if self.barcode_mgr.camera_index != idx:
                self.barcode_mgr.set_camera_index(idx)
            scan_status_text.value = f"Cámara cambiada a índice {idx}. Enfocando código..."
            safe_update(scan_status_text)

        def toggle_native_opencv(_=None):
            is_open = self.barcode_mgr.toggle_native_window()
            if is_open:
                scan_status_text.value = "Ventana OpenCV abierta. Enfoque el código allí (presione 'q' para cerrar)."
                scan_status_text.color = PastelTheme.ACCENT_SKY
            else:
                scan_status_text.value = f"Cámara activa (Índice {self.barcode_mgr.camera_index}). Ubique el código dentro del recuadro."
                scan_status_text.color = PastelTheme.TEXT_SECONDARY
            safe_update(scan_status_text)

        scan_dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.QR_CODE_SCANNER_ROUNDED, color=PastelTheme.PRIMARY, size=24),
                ft.Text("Escanear Código de Barras (Nuevo Producto)", weight=ft.FontWeight.BOLD, size=16)
            ]),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        ft.Container(
                            content=scan_img,
                            bgcolor=PastelTheme.SURFACE_VARIANT,
                            border_radius=8,
                            alignment=ft.Alignment.CENTER,
                            width=360,
                            height=230
                        ),
                        scan_status_text,
                        ft.Row([
                            ft.OutlinedButton(
                                "Cámara 1 (PC)",
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=lambda _: switch_cam_index(1)
                            ),
                            ft.OutlinedButton(
                                "Cámara 0 (Secundaria)",
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=lambda _: switch_cam_index(0)
                            ),
                            ft.FilledButton(
                                content=ft.Row([ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=14), ft.Text("Ventana OpenCV")]),
                                style=ft.ButtonStyle(
                                    bgcolor=PastelTheme.SKY_PASTEL,
                                    color=PastelTheme.ACCENT_SKY,
                                    shape=ft.RoundedRectangleBorder(radius=8)
                                ),
                                on_click=toggle_native_opencv
                            )
                        ], wrap=True, spacing=6),
                        ft.Divider(height=1, color=PastelTheme.BORDER_LIGHT),
                        ft.Row([
                            manual_code_tf,
                            ft.IconButton(
                                icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                                tooltip="Procesar código",
                                icon_color=PastelTheme.PRIMARY,
                                on_click=lambda _: process_scanned_barcode(manual_code_tf.value)
                            )
                        ])
                    ]
                )
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog)
            ]
        )
        self.page.show_dialog(scan_dialog)

    def show_product_dialog(
        self,
        product: Optional[Dict[str, Any]] = None,
        initial_scan_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Modal interactivo para Crear o Editar producto con cálculo dinámico de utilidad y búsqueda en Open Food Facts."""
        is_edit = product is not None
        has_initial = initial_scan_data is not None

        init_barcode = ""
        init_name = ""
        init_brand = ""
        init_presentacion = ""
        init_category = "General"
        init_cost = "0"
        init_sale = "0"
        init_stock = "0"
        init_min_stock = "5"

        if is_edit:
            init_barcode = product.get("barcode", "")
            init_name = product.get("name", "")
            init_brand = product.get("brand", "")
            init_presentacion = product.get("presentacion", "")
            init_category = product.get("category", "General")
            init_cost = str(product.get("cost_price", 0))
            init_sale = str(product.get("sale_price", 0))
            init_stock = str(product.get("stock", 0))
            init_min_stock = str(product.get("min_stock", 5))
        elif has_initial:
            init_barcode = initial_scan_data.get("barcode", "")
            init_name = initial_scan_data.get("name", "")
            init_brand = initial_scan_data.get("brand", "")
            init_presentacion = initial_scan_data.get("presentacion", "")
            init_category = initial_scan_data.get("category", "General")

        barcode_tf = ft.TextField(
            label="Código de barras",
            value=init_barcode,
            autofocus=not has_initial,
            border_radius=8,
            dense=True,
            expand=True
        )
        name_tf = ft.TextField(
            label="Nombre del producto (product_name)",
            value=init_name,
            border_radius=8,
            dense=True,
        )
        brand_tf = ft.TextField(
            label="Marca (brands)",
            value=init_brand,
            border_radius=8,
            dense=True,
            expand=True
        )
        presentacion_tf = ft.TextField(
            label="Presentación (ej. 65g, 500ml)",
            value=init_presentacion,
            border_radius=8,
            dense=True,
            expand=True
        )
        cost_tf = ft.TextField(
            label="Costo de Compra ($)",
            value=init_cost,
            autofocus=(has_initial and initial_scan_data.get("is_off_found", False)),
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            dense=True,
            expand=True
        )
        sale_tf = ft.TextField(
            label="Precio de Venta ($)",
            value=init_sale,
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            dense=True,
            expand=True
        )
        stock_tf = ft.TextField(
            label="Cantidad en Stock",
            value=init_stock,
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            dense=True,
            expand=True
        )
        min_stock_tf = ft.TextField(
            label="Stock Mínimo (Alerta)",
            value=init_min_stock,
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=8,
            dense=True,
            expand=True
        )
        category_tf = ft.TextField(
            label="Categoría",
            value=init_category,
            border_radius=8,
            dense=True,
        )

        profit_preview = ft.Text("Utilidad: $0.00 (0%)", weight=ft.FontWeight.BOLD, color=PastelTheme.ACCENT_MINT)
        off_status_text = ft.Text(
            initial_scan_data.get("status_message", "") if has_initial else "",
            size=11,
            weight=ft.FontWeight.W_500,
            color=PastelTheme.ACCENT_MINT if (has_initial and initial_scan_data.get("is_off_found")) else PastelTheme.TEXT_SECONDARY,
            visible=has_initial and bool(initial_scan_data.get("status_message"))
        )

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

        def on_barcode_scanned_or_entered(code_val: Optional[str] = None):
            code = (code_val or barcode_tf.value or "").strip()
            if not code:
                off_status_text.value = "Ingresa o escanea un código de barras primero."
                off_status_text.color = PastelTheme.ACCENT_CORAL
                off_status_text.visible = True
                safe_update(off_status_text)
                return

            barcode_tf.value = code
            safe_update(barcode_tf)

            # 1. Comprobación obligatoria en SQLite local para evitar duplicados
            lookup_result = self.controller.scan_or_lookup_barcode_for_new(code)
            status = lookup_result["status"]

            if status == "EXISTS_LOCAL":
                existing = lookup_result["product"]
                if is_edit and existing["id"] == product["id"]:
                    pass  # Está editando el mismo producto
                else:
                    off_status_text.value = f"Aviso: El artículo ya existe en SQLite local ('{existing['display_name']}'). Evite duplicarlo."
                    off_status_text.color = PastelTheme.ACCENT_CORAL
                    off_status_text.visible = True
                    safe_update(dialog)
                    return

            # 2. Si no está en SQLite, procesar datos de Open Food Facts vía requests
            if status == "OFF_FOUND":
                data = lookup_result["data"]
                p_name = data.get("product_name") or data.get("name") or ""
                p_brand = data.get("brands") or ""
                p_qty = data.get("quantity") or ""
                p_cat = data.get("category") or ""

                # Renderizar inmediatamente en los campos de texto del formulario
                name_tf.value = p_name
                brand_tf.value = p_brand
                if p_qty:
                    presentacion_tf.value = p_qty
                if p_cat:
                    category_tf.value = p_cat

                off_status_text.value = f"¡Encontrado en Open Food Facts! {p_name}"
                off_status_text.color = PastelTheme.ACCENT_MINT
                off_status_text.visible = True
                safe_update(dialog)

                # Dejar el cursor posicionado en el campo 'Costo de Compra'
                try:
                    cost_tf.focus()
                except Exception:
                    pass
            elif status == "NOT_FOUND":
                off_status_text.value = lookup_result.get("message", "Producto no registrado en Open Food Facts.")
                off_status_text.color = PastelTheme.ACCENT_CORAL
                off_status_text.visible = True
                safe_update(dialog)
                try:
                    name_tf.focus()
                except Exception:
                    pass

        self.active_barcode_callback = on_barcode_scanned_or_entered
        barcode_tf.on_submit = lambda _: on_barcode_scanned_or_entered()

        def close_dialog(_=None):
            self.active_barcode_callback = None
            self.page.pop_dialog()

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
                    brand=brand_tf.value,
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
                    brand=brand_tf.value,
                    presentacion=presentacion_tf.value,
                    category=category_tf.value
                )

            if success:
                close_dialog()
                self.load_products()
            else:
                off_status_text.value = msg
                off_status_text.color = PastelTheme.ACCENT_CORAL
                off_status_text.visible = True
                safe_update(off_status_text)

        dialog = ft.AlertDialog(
            title=ft.Text("Editar Producto" if is_edit else "Registrar Nuevo Producto", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=480,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                barcode_tf,
                                ft.IconButton(
                                    icon=ft.Icons.TRAVEL_EXPLORE_ROUNDED,
                                    tooltip="Consultar Open Food Facts (verificar SQLite y autocompletar)",
                                    icon_color=PastelTheme.PRIMARY,
                                    on_click=lambda _: on_barcode_scanned_or_entered()
                                )
                            ]
                        ),
                        off_status_text,
                        name_tf,
                        ft.Row([brand_tf, presentacion_tf], spacing=10),
                        ft.Row([cost_tf, sale_tf], spacing=10),
                        ft.Container(
                            bgcolor=PastelTheme.MINT_PASTEL,
                            padding=10,
                            border_radius=8,
                            content=profit_preview
                        ),
                        ft.Row([stock_tf, min_stock_tf], spacing=10),
                        category_tf
                    ]
                )
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.FilledButton(
                    "Guardar",
                    bgcolor=PastelTheme.PRIMARY,
                    color=PastelTheme.TEXT_ON_PRIMARY,
                    on_click=save_product
                )
            ]
        )
        self.page.show_dialog(dialog)
        if has_initial and initial_scan_data.get("is_off_found"):
            try:
                cost_tf.focus()
            except Exception:
                pass

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
