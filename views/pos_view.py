import base64
import threading
import flet as ft
from typing import Optional, Union, Dict, Any
from config import PastelTheme
from controllers import PosController, CustomerController
from services.barcode_manager import BarcodeManager, ScannerMode
from views.theme import create_card, create_badge, safe_update, SearchableDropdown

def _generate_placeholder_camera_uri() -> str:
    try:
        import cv2
        import numpy as np
        # Imagen inicial de 280x180 para evitar el error de Flutter "A valid src value must be specified."
        img = np.full((180, 280, 3), (40, 42, 54), dtype=np.uint8)
        cv2.putText(img, "Iniciando camara...", (35, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 1)
        _, buf = cv2.imencode('.jpg', img)
        b64 = base64.b64encode(buf.tobytes()).decode('ascii')
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        # Fallback a imagen JPEG válida de 1x1 en Base64 Data URI
        return "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="

_INITIAL_CAMERA_URI = _generate_placeholder_camera_uri()

class PosView(ft.Container):
    """
    Vista de Punto de Venta (POS / Facturación).
    - Interfaz de caja registradora con adición instantánea al escanear.
    - Preserva el borrador de la venta aun si el cajero navega a otras pestañas.
    - Soporte completo para ventas de Contado y ventas a Crédito (Cartera),
      asignando cliente y descripción opcional del crédito.
    - Conectado al BarcodeManager y preparado para el endpoint de IA de voz.
    """
    def __init__(
        self,
        pos_controller: PosController,
        customer_controller: CustomerController,
        barcode_manager: BarcodeManager
    ):
        super().__init__(expand=True)
        self.pos = pos_controller
        self.customer_ctrl = customer_controller
        self.barcode_mgr = barcode_manager
        self.padding = 20
        self._search_debounce_timer: Optional[threading.Timer] = None

        # Suscribir la vista a los cambios del controlador POS (para reactividad en tiempo real)
        self.pos.subscribe(self.on_cart_changed)

        # Entrada manual o de prueba de código de barras
        self.barcode_input = ft.TextField(
            hint_text="Escanear o ingresar código de barras...",
            prefix_icon=ft.Icons.QR_CODE_SCANNER_ROUNDED,
            border_radius=PastelTheme.BORDER_RADIUS_INPUT,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_color=PastelTheme.PRIMARY,
            dense=True,
            expand=True,
            on_submit=self._on_barcode_submit
        )

        # Barra de búsqueda predictiva por nombre instantánea desde la 1ª letra
        self.product_search_input = ft.TextField(
            label="Buscar producto por nombre...",
            hint_text="Escriba desde la 1ª letra para filtrar al instante (ej. Aceite Diana - 1000ml)...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=PastelTheme.BORDER_RADIUS_INPUT,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_color=PastelTheme.BORDER_LIGHT,
            focused_border_color=PastelTheme.PRIMARY,
            dense=True,
            expand=True,
            on_change=self._on_search_input_change,
            on_submit=self._on_search_input_submit,
        )

        # Contenedor dinámico de sugerencias de autocompletado (oculto por defecto)
        self.suggestions_list = ft.Column(spacing=4, tight=True, scroll=ft.ScrollMode.AUTO)
        self.suggestions_container = ft.Container(
            visible=False,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_radius=10,
            border=ft.Border.all(1, PastelTheme.PRIMARY_PASTEL),
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=10,
                color="#18000000",
                offset=ft.Offset(0, 4),
            ),
            content=self.suggestions_list,
        )

        # Componentes de la tabla del carrito
        self.cart_items_column = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        self.cart_count_text = ft.Text("0 productos en el borrador", size=13, color=PastelTheme.TEXT_SECONDARY)

        # Panel de Totales
        self.total_display = ft.Text("$0.00", size=36, weight=ft.FontWeight.BOLD, color=PastelTheme.PRIMARY)
        self.subtotal_display = ft.Text("$0.00", size=14, color=PastelTheme.TEXT_SECONDARY)
        self.profit_display = ft.Text("Utilidad est: $0.00", size=12, weight=ft.FontWeight.W_600, color=PastelTheme.ACCENT_MINT)

        # Modalidad de Pago: Contado / Crédito
        self.payment_type_dropdown = ft.Dropdown(
            label="Tipo de Pago",
            value=self.pos.payment_type,
            border_radius=8,
            dense=True,
            options=[
                ft.dropdown.Option("CASH", "Contado / Efectivo"),
                ft.dropdown.Option("CREDIT", "Crédito (Cartera)")
            ],
            on_select=self._on_payment_type_change
        )

        # Selector de Cliente con lista deslizante y filtrado en vivo desde la 1ª letra
        self.customer_dropdown = SearchableDropdown(
            label="Asignar Cliente",
            hint_text="Seleccione de la lista o escriba desde la 1ª letra...",
            prefix_icon=ft.Icons.PERSON_SEARCH_ROUNDED,
            visible=(self.pos.payment_type == "CREDIT"),
            options=[],
            value=str(self.pos.customer_id) if self.pos.customer_id else None,
            on_select=self._on_customer_change,
            max_list_height=160,
        )

        self.credit_notes_input = ft.TextField(
            label="Descripción opcional de la venta",
            hint_text="Observaciones, notas o condiciones de la venta...",
            border_radius=8,
            dense=True,
            multiline=True,
            max_lines=3,
            visible=True,
            value=self.pos.credit_notes,
            on_change=lambda e: self.pos.set_payment_options(self.pos.payment_type, e.control.value)
        )

        self.scanner_status_badge = create_badge("Modo: USB Wedge", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)

        # Componentes del escáner por cámara en vivo con filtros y verificación de 5 muestras
        self.camera_image = ft.Image(
            src=_INITIAL_CAMERA_URI,
            fit=ft.BoxFit.CONTAIN,
            width=280,
            height=180,
            border_radius=8,
            gapless_playback=True
        )
        self.camera_verification_text = ft.Text(
            f"Cámara activa (Índice {self.barcode_mgr.camera_index}). Enfoque el código de barras dentro del recuadro.",
            size=12,
            weight=ft.FontWeight.W_500,
            color=PastelTheme.TEXT_SECONDARY
        )
        self.scan_feedback_banner = ft.Text(
            "",
            size=12,
            weight=ft.FontWeight.BOLD,
            color=PastelTheme.ACCENT_MINT,
            visible=False
        )

        self.camera_preview_card = create_card(
            visible=False,
            padding=12,
            content=ft.Row(
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        content=self.camera_image,
                        bgcolor=PastelTheme.SURFACE_VARIANT,
                        border_radius=8,
                        alignment=ft.Alignment.CENTER,
                        width=280,
                        height=180
                    ),
                    ft.Column(
                        expand=True,
                        spacing=6,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.VIDEOCAM_ROUNDED, color=PastelTheme.PRIMARY, size=20),
                                ft.Text("Escáner por Cámara (LectorBarr.py)", weight=ft.FontWeight.BOLD, size=14, color=PastelTheme.TEXT_PRIMARY)
                            ]),
                            self.camera_verification_text,
                            ft.Text(
                                "Pipeline: Región central (400x200), filtro CLAHE anti-reflejos y confirmación de 5 lecturas consecutivas.",
                                size=11,
                                color=PastelTheme.TEXT_MUTED
                            ),
                            ft.Row([
                                ft.OutlinedButton(
                                    "Cámara 1 (PC)",
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                    on_click=lambda _: self._switch_camera_index(1)
                                ),
                                ft.OutlinedButton(
                                    "Cámara 0 (Secundaria)",
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                    on_click=lambda _: self._switch_camera_index(0)
                                ),
                                ft.FilledButton(
                                    content=ft.Row([ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=15), ft.Text("Ventana OpenCV (LectorBarr)")]),
                                    style=ft.ButtonStyle(
                                        bgcolor=PastelTheme.SKY_PASTEL,
                                        color=PastelTheme.ACCENT_SKY,
                                        shape=ft.RoundedRectangleBorder(radius=8)
                                    ),
                                    on_click=self._toggle_native_opencv_window
                                ),
                                ft.TextButton(
                                    "Ocultar Cámara",
                                    on_click=self._toggle_scanner_mode
                                )
                            ], wrap=True, spacing=8)
                        ]
                    )
                ]
            )
        )

        # Conectar callbacks de video y verificación de muestras desde BarcodeManager
        self.barcode_mgr.set_preview_callback(self._on_camera_preview_frame)
        self.barcode_mgr.set_verification_callback(self._on_camera_verification_progress)

        # Construcción del Layout Principal (Izquierda: Carrito, Derecha: Panel de Cobro)
        self.content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Header Superior con estado del hardware y barra de escaneo
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text("Punto de Venta (POS)", size=24, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                ft.Text("Caja registradora con persistencia de borrador y escáner automático", size=13, color=PastelTheme.TEXT_SECONDARY)
                            ]
                        ),
                        ft.Row([
                            self.scanner_status_badge,
                            ft.FilledButton(
                                content=ft.Row([ft.Icon(ft.Icons.CAMERA_ALT_ROUNDED, size=16), ft.Text("Cámara/USB")]),
                                style=ft.ButtonStyle(
                                    bgcolor=PastelTheme.PRIMARY_PASTEL,
                                    color=PastelTheme.PRIMARY,
                                    shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                    elevation=0
                                ),
                                on_click=self._toggle_scanner_mode
                            )
                        ])
                    ]
                ),

                # Tarjeta de Vista Previa de Cámara (Visible en modo Cámara)
                self.camera_preview_card,

                # Barra de escaneo rápido y búsqueda manual predictiva (Autocomplete)
                create_card(
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Row(
                                controls=[
                                    self.barcode_input,
                                    ft.FilledButton(
                                        content=ft.Row([ft.Icon(ft.Icons.ADD_SHOPPING_CART_ROUNDED, size=18), ft.Text("Agregar")]),
                                        style=ft.ButtonStyle(
                                            bgcolor=PastelTheme.PRIMARY,
                                            color=PastelTheme.TEXT_ON_PRIMARY,
                                            shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                        ),
                                        on_click=lambda _: self._on_barcode_submit()
                                    ),
                                    ft.TextButton(
                                        "Simular Escaneo (7701001001)",
                                        on_click=lambda _: self.barcode_mgr.scan_code("7701001001")
                                    )
                                ]
                            ),
                            self.product_search_input,
                            self.suggestions_container,
                            self.scan_feedback_banner
                        ]
                    ),
                    padding=10
                ),

                # Cuerpo: Carrito (expand=3) y Resumen de Cobro (expand=2)
                ft.Row(
                    expand=True,
                    spacing=16,
                    controls=[
                        # Columna Izquierda: Carrito
                        create_card(
                            expand=3,
                            padding=16,
                            content=ft.Column(
                                expand=True,
                                spacing=12,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text("Productos en la Factura", size=16, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                            self.cart_count_text
                                        ]
                                    ),
                                    ft.Divider(color=PastelTheme.BORDER_LIGHT, height=1),
                                    # Cabecera de columnas
                                    ft.Container(
                                        bgcolor=PastelTheme.SURFACE_VARIANT,
                                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                        border_radius=8,
                                        content=ft.Row(
                                            controls=[
                                                ft.Text("Producto", expand=3, size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_SECONDARY),
                                                ft.Text("Precio", width=80, size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_SECONDARY),
                                                ft.Text("Cant.", width=100, text_align=ft.TextAlign.CENTER, size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_SECONDARY),
                                                ft.Text("Subtotal", width=90, size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_SECONDARY),
                                                ft.Text("", width=40) # Espacio para botón eliminar
                                            ]
                                        )
                                    ),
                                    # Lista de Items
                                    self.cart_items_column
                                ]
                            )
                        ),

                        # Columna Derecha: Panel de Liquidación y Cobro (con scroll vertical adaptable a cualquier resolución)
                        create_card(
                            expand=2,
                            padding=20,
                            content=ft.Column(
                                expand=True,
                                spacing=14,
                                scroll=ft.ScrollMode.AUTO,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                controls=[
                                    ft.Text("Resumen de Cobro", size=18, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                    ft.Divider(color=PastelTheme.BORDER_LIGHT, height=1),

                                    # Caja de Total Grande
                                    ft.Container(
                                        bgcolor=PastelTheme.PRIMARY_PASTEL,
                                        border_radius=12,
                                        padding=16,
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Column(
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                            spacing=4,
                                            controls=[
                                                ft.Text("TOTAL A COBRAR", size=12, weight=ft.FontWeight.W_600, color=PastelTheme.PRIMARY),
                                                self.total_display,
                                                self.subtotal_display,
                                                self.profit_display
                                            ]
                                        )
                                    ),

                                    # Configuración de Pago y Crédito
                                    self.payment_type_dropdown,
                                    self.customer_dropdown,
                                    self.credit_notes_input,

                                    ft.Container(height=6),

                                    # Botones de Acción
                                    ft.FilledButton(
                                        content=ft.Row(
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            controls=[
                                                ft.Icon(ft.Icons.POINT_OF_SALE_ROUNDED, size=22),
                                                ft.Text("FINALIZAR VENTA", size=15, weight=ft.FontWeight.BOLD)
                                            ]
                                        ),
                                        style=ft.ButtonStyle(
                                            bgcolor=PastelTheme.PRIMARY,
                                            color=PastelTheme.TEXT_ON_PRIMARY,
                                            shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                            padding=ft.Padding.symmetric(vertical=16)
                                        ),
                                        on_click=self._process_checkout
                                    ),
                                    ft.OutlinedButton(
                                        content=ft.Row(
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            controls=[
                                                ft.Icon(ft.Icons.DELETE_SWEEP_ROUNDED, size=18, color=PastelTheme.ACCENT_CORAL),
                                                ft.Text("Vaciar Borrador", color=PastelTheme.ACCENT_CORAL)
                                            ]
                                        ),
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                                            padding=ft.Padding.symmetric(vertical=12)
                                        ),
                                        on_click=lambda _: self.pos.clear_draft()
                                    )
                                ]
                            )
                        )
                    ]
                )
            ]
        )

        self._refresh_customer_options()
        self.on_cart_changed()

    def _refresh_customer_options(self) -> None:
        """Carga clientes disponibles para venta a crédito en el selector filtrable."""
        customers = self.customer_ctrl.get_all_customers()
        options = [
            {
                "key": str(c["id"]),
                "label": f"{c['name']}" + (f" ({c['document_id']})" if c.get("document_id") else ""),
                "subtitle": f"Tel: {c['phone'] or 'S/T'}  •  Deuda actual: ${c['current_debt']:,.0f}",
            }
            for c in customers
        ]
        self.customer_dropdown.set_options(options, preserve_value=True)
        expected_val = str(self.pos.customer_id) if self.pos.customer_id else None
        if self.customer_dropdown.value != expected_val:
            self.customer_dropdown.value = expected_val

    # ================= LÓGICA DE AUTOCOMPLETADO Y BÚSQUEDA PREDICTIVA INSTANTÁNEA =================

    def _on_search_input_change(self, e) -> None:
        """
        Filtra productos instantáneamente (0ms delay) desde la primera letra digitada (len >= 1).
        Si el campo queda vacío, oculta inmediatamente el contenedor de sugerencias.
        """
        if self._search_debounce_timer is not None:
            self._search_debounce_timer.cancel()
            self._search_debounce_timer = None

        query = (self.product_search_input.value or "").strip()
        if len(query) < 1:
            self.suggestions_list.controls.clear()
            self.suggestions_container.visible = False
            safe_update(self.suggestions_container)
            return

        # Ejecución inmediata desde la primera letra para máxima velocidad de respuesta
        self._execute_debounced_search(query)

    def _on_search_input_submit(self, e=None) -> None:
        """Al presionar Enter en el buscador de productos, agrega la primera coincidencia."""
        query = (self.product_search_input.value or "").strip()
        if len(query) < 1:
            return
        matches = self.pos.search_products_by_name(query, limit=1)
        if matches:
            self._on_suggestion_selected(matches[0])

    def _execute_debounced_search(self, query: str) -> None:
        """Ejecuta la consulta SQL LIKE desde la 1ª letra y construye la lista desplegable."""
        current_val = (self.product_search_input.value or "").strip()
        if len(current_val) < 1:
            self.suggestions_list.controls.clear()
            self.suggestions_container.visible = False
            safe_update(self.suggestions_container)
            return

        matches = self.pos.search_products_by_name(query, limit=10)
        suggestion_tiles = []

        if not matches:
            suggestion_tiles.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    content=ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=16, color=PastelTheme.TEXT_MUTED),
                            ft.Text(
                                f"Sin coincidencias en inventario para «{query}»",
                                size=12,
                                color=PastelTheme.TEXT_MUTED,
                                italic=True,
                            ),
                        ],
                    ),
                )
            )
        else:
            is_single_match = len(matches) == 1
            for prod in matches:
                # Concatenar nombre y presentación para evitar confusiones (ej. "Aceite Diana - 1000ml")
                name_str = prod.get("name", "")
                pres_str = (prod.get("presentacion") or "").strip()
                concatenated_label = f"{name_str} - {pres_str}" if pres_str else name_str
                stock_qty = prod.get("stock", 0)
                stock_color = PastelTheme.ACCENT_MINT if stock_qty > 0 else PastelTheme.ACCENT_CORAL

                tile = ft.Container(
                    bgcolor=PastelTheme.PRIMARY_PASTEL if is_single_match else PastelTheme.SURFACE_VARIANT,
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    ink=True,
                    on_click=lambda _, p=prod: self._on_suggestion_selected(p),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=18, color=PastelTheme.PRIMARY),
                                    ft.Column(
                                        spacing=1,
                                        controls=[
                                            ft.Text(
                                                concatenated_label,
                                                size=13,
                                                weight=ft.FontWeight.BOLD,
                                                color=PastelTheme.PRIMARY if is_single_match else PastelTheme.TEXT_PRIMARY,
                                            ),
                                            ft.Text(
                                                f"Código: {prod.get('barcode', '')}  •  Stock disp.: {stock_qty}",
                                                size=11,
                                                color=stock_color if stock_qty <= 0 else PastelTheme.TEXT_SECONDARY,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    *(
                                        [create_badge("Enter / Clic", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)]
                                        if is_single_match
                                        else []
                                    ),
                                    ft.Text(
                                        f"${prod.get('sale_price', 0.0):,.0f}",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                        color=PastelTheme.PRIMARY,
                                    ),
                                    ft.Icon(ft.Icons.ADD_CIRCLE_ROUNDED, size=18, color=PastelTheme.ACCENT_MINT),
                                ],
                            ),
                        ],
                    ),
                )
                suggestion_tiles.append(tile)

        self.suggestions_list.controls = suggestion_tiles
        self.suggestions_container.height = 220 if len(suggestion_tiles) > 4 else None
        self.suggestions_container.visible = True
        safe_update(self.suggestions_container)

    def _on_suggestion_selected(self, product: Dict[str, Any]) -> None:
        """
        Acción al hacer clic en un producto sugerido:
        1. Cierra/oculta el contenedor dinámico de sugerencias.
        2. Limpia el campo de búsqueda.
        3. Invoca EXACTAMENTE la misma función del controlador usada por el escáner (add_item_to_invoice).
        """
        if self._search_debounce_timer is not None:
            self._search_debounce_timer.cancel()
            self._search_debounce_timer = None

        # 1. Ocultar contenedor dinámico de sugerencias
        self.suggestions_container.visible = False
        self.suggestions_list.controls.clear()

        # 2. Limpiar el campo de búsqueda
        self.product_search_input.value = ""
        safe_update(self.product_search_input)
        safe_update(self.suggestions_container)

        # 3. Invocar exactamente la misma función del controlador que usa el escáner
        barcode = str(product.get("barcode") or "").strip()
        target_key: Union[str, int] = barcode if barcode else int(product["id"])
        success, msg = self.pos.add_item_to_invoice(target_key)
        if not success:
            self.scan_feedback_banner.value = f"⚠ {msg}"
            self.scan_feedback_banner.color = PastelTheme.ACCENT_CORAL
            self.scan_feedback_banner.visible = True
            safe_update(self.scan_feedback_banner)
        else:
            item = self.pos.items.get(barcode)
            if item:
                self.scan_feedback_banner.value = f"✓ Agregado a factura: {item.display_name} — Precio: ${item.sale_price:,.0f}"
                self.scan_feedback_banner.color = PastelTheme.ACCENT_MINT
                self.scan_feedback_banner.visible = True
                safe_update(self.scan_feedback_banner)

    def _on_barcode_submit(self) -> None:
        code = (self.barcode_input.value or "").strip()
        self.barcode_input.value = ""
        safe_update(self.barcode_input)
        if code:
            success, msg = self.pos.add_item_to_invoice(code)
            if not success:
                self.scan_feedback_banner.value = f"⚠ {msg}"
                self.scan_feedback_banner.color = PastelTheme.ACCENT_CORAL
                self.scan_feedback_banner.visible = True
                safe_update(self.scan_feedback_banner)
            else:
                item = self.pos.items.get(code)
                if item:
                    self.scan_feedback_banner.value = f"✓ Agregado a factura: {item.display_name} — Precio: ${item.sale_price:,.0f}"
                    self.scan_feedback_banner.color = PastelTheme.ACCENT_MINT
                    self.scan_feedback_banner.visible = True
                    safe_update(self.scan_feedback_banner)

    def handle_external_scan(self, code: str) -> None:
        """Procesa una lectura proveniente de hardware (USB o cámara), limpiando el campo y alertando si no existe."""
        clean_code = (code or "").strip()
        self.barcode_input.value = ""
        safe_update(self.barcode_input)
        success, msg = self.pos.add_item_to_invoice(clean_code)
        if not success:
            self.scan_feedback_banner.value = f"⚠ {msg}"
            self.scan_feedback_banner.color = PastelTheme.ACCENT_CORAL
            self.scan_feedback_banner.visible = True
            safe_update(self.scan_feedback_banner)
        else:
            item = self.pos.items.get(clean_code)
            if item:
                self.scan_feedback_banner.value = f"✓ Escaneo verificado (5/5): {item.display_name} — Precio: ${item.sale_price:,.0f}"
                self.scan_feedback_banner.color = PastelTheme.ACCENT_MINT
                self.scan_feedback_banner.visible = True
                safe_update(self.scan_feedback_banner)

    def on_cart_changed(self) -> None:
        """Refresca la UI reactivamente cuando el borrador cambia."""
        self._refresh_customer_options()
        self.payment_type_dropdown.value = self.pos.payment_type
        is_credit = (self.pos.payment_type == "CREDIT")
        self.customer_dropdown.visible = is_credit
        self.credit_notes_input.visible = True
        self.credit_notes_input.label = (
            "Descripción opcional del crédito" if is_credit else "Descripción opcional de la venta"
        )
        self.credit_notes_input.value = self.pos.credit_notes

        items = list(self.pos.items.values())

        # Actualizar totales
        self.total_display.value = f"${self.pos.total:,.0f}"
        self.subtotal_display.value = f"Subtotal: ${self.pos.subtotal:,.0f}"
        self.profit_display.value = f"Utilidad estimada: +${self.pos.total_estimated_profit:,.0f}"
        self.cart_count_text.value = f"{len(items)} productos ({self.pos.total_items_count} unidades)"

        # Renderizar filas del carrito
        rows = []
        for item in items:
            row = ft.Container(
                bgcolor=PastelTheme.SURFACE_WHITE,
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Column(
                            expand=3,
                            spacing=1,
                            controls=[
                                ft.Text(item.display_name, size=13, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                ft.Text(f"Código: {item.barcode}", size=11, color=PastelTheme.TEXT_MUTED)
                            ]
                        ),
                        ft.Text(f"${item.sale_price:,.0f}", width=80, size=12, color=PastelTheme.TEXT_SECONDARY),
                        ft.Row(
                            width=100,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=2,
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED,
                                    icon_size=18,
                                    icon_color=PastelTheme.TEXT_SECONDARY,
                                    on_click=lambda _, b=item.barcode, q=item.quantity: self.pos.update_quantity(b, q - 1)
                                ),
                                ft.Text(str(item.quantity), size=13, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                ft.IconButton(
                                    icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
                                    icon_size=18,
                                    icon_color=PastelTheme.PRIMARY,
                                    on_click=lambda _, b=item.barcode, q=item.quantity: self.pos.update_quantity(b, q + 1)
                                )
                            ]
                        ),
                        ft.Text(f"${item.subtotal:,.0f}", width=90, size=13, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_size=16,
                            icon_color=PastelTheme.ACCENT_CORAL,
                            tooltip="Quitar",
                            on_click=lambda _, b=item.barcode: self.pos.remove_item(b)
                        )
                    ]
                )
            )
            rows.append(row)

        if not rows:
            rows.append(
                ft.Container(
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.SHOPPING_BAG_OUTLINED, size=48, color=PastelTheme.TEXT_MUTED),
                            ft.Text("El borrador de venta está vacío.", size=14, color=PastelTheme.TEXT_SECONDARY),
                            ft.Text("Escanee un código de barras o use el botón de simulación para comenzar.", size=12, color=PastelTheme.TEXT_MUTED)
                        ]
                    )
                )
            )

        self.cart_items_column.controls = rows
        safe_update(self)

    def _on_payment_type_change(self, e) -> None:
        ptype = e.control.value
        is_credit = (ptype == "CREDIT")
        self.customer_dropdown.visible = is_credit
        self.credit_notes_input.visible = True
        self.credit_notes_input.label = (
            "Descripción opcional del crédito" if is_credit else "Descripción opcional de la venta"
        )
        if is_credit:
            self._refresh_customer_options()
        self.pos.set_payment_options(ptype, self.credit_notes_input.value or "")
        safe_update(self)

    def _on_customer_change(self, selected_val: Optional[str]) -> None:
        cid = int(selected_val) if (selected_val and str(selected_val).isdigit()) else None
        self.pos.set_customer(cid)

    def _on_camera_preview_frame(self, frame_data: str) -> None:
        """Actualiza el fotograma de la cámara en vivo en la interfaz."""
        if self.camera_preview_card.visible:
            self.camera_image.src = frame_data
            safe_update(self.camera_image)

    def _on_camera_verification_progress(self, code: str, current: int, required: int) -> None:
        """Informa a la UI el avance de las muestras consecutivas requeridas para validar."""
        if not code or current == 0:
            new_text = f"Cámara activa (Índice {self.barcode_mgr.camera_index}). Enfoque el código dentro del recuadro."
            new_color = PastelTheme.TEXT_SECONDARY
        else:
            if current >= required:
                new_text = f"¡Código {code} confirmado (5/5)! Agregando a factura..."
                new_color = PastelTheme.ACCENT_MINT
            else:
                new_text = f"Detectando código: {code} | Muestras: {current}/{required} confirmadas"
                new_color = PastelTheme.ACCENT_AMBER

        if self.camera_verification_text.value != new_text:
            self.camera_verification_text.value = new_text
            self.camera_verification_text.color = new_color
            safe_update(self.camera_verification_text)

    def _switch_camera_index(self, index: int) -> None:
        """Cambia el dispositivo de cámara entre el índice 1 (PC) y 0 (Secundaria)."""
        try:
            if self.barcode_mgr.mode != ScannerMode.CAMERA:
                self._toggle_scanner_mode()
            if self.barcode_mgr.camera_index != index:
                self.barcode_mgr.set_camera_index(index)
            elif not self.barcode_mgr.is_running():
                self.barcode_mgr.start()

            cam_name = "Cámara 1 (PC)" if index == 1 else "Cámara 0 (Secundaria)"
            self.camera_verification_text.value = f"Dispositivo activo: {cam_name}. Enfocando código de barras..."
            self.camera_verification_text.color = PastelTheme.TEXT_SECONDARY
            self.scanner_status_badge.content.value = f"Modo: Webcam ({self.barcode_mgr.camera_index})"
            safe_update(self.camera_verification_text)
            safe_update(self.scanner_status_badge)
        except Exception as e:
            print(f"[PosView] Error al cambiar índice de cámara: {e}")

    def _toggle_scanner_mode(self, _=None) -> None:
        """Permite alternar entre escáner USB y escáner de cámara."""
        try:
            new_mode = ScannerMode.CAMERA if self.barcode_mgr.mode == ScannerMode.KEYBOARD_WEDGE else ScannerMode.KEYBOARD_WEDGE
            if new_mode == ScannerMode.KEYBOARD_WEDGE and hasattr(self.barcode_mgr, "stop_native_window"):
                self.barcode_mgr.stop_native_window()
            self.barcode_mgr.set_mode(new_mode)
            is_camera = (new_mode == ScannerMode.CAMERA)
            self.camera_preview_card.visible = is_camera

            badge_text = f"Modo: Webcam ({self.barcode_mgr.camera_index})" if is_camera else "Modo: USB Wedge"
            badge_bg = PastelTheme.SKY_PASTEL if is_camera else PastelTheme.MINT_PASTEL
            badge_color = PastelTheme.ACCENT_SKY if is_camera else PastelTheme.ACCENT_MINT
            self.scanner_status_badge.content.value = badge_text
            self.scanner_status_badge.bgcolor = badge_bg
            self.scanner_status_badge.content.color = badge_color

            safe_update(self.scanner_status_badge)
            safe_update(self.camera_preview_card)
        except Exception as e:
            print(f"[PosView] Error al alternar modo de escáner: {e}")

    def _toggle_native_opencv_window(self, _=None) -> None:
        """Abre o cierra la ventana nativa flotante de OpenCV (LectorBarr.py)."""
        try:
            is_open = self.barcode_mgr.toggle_native_window()
            if is_open:
                self.camera_verification_text.value = "Ventana flotante de LectorBarr abierta. Escanee allí los códigos (presione 'q' para cerrar)."
                self.camera_verification_text.color = PastelTheme.ACCENT_SKY
                self.scanner_status_badge.content.value = f"Modo: LectorBarr ({self.barcode_mgr.camera_index})"
            else:
                self.camera_verification_text.value = f"Cámara activa (Índice {self.barcode_mgr.camera_index}). Ubique el código en el recuadro."
                self.camera_verification_text.color = PastelTheme.TEXT_SECONDARY
                self.scanner_status_badge.content.value = f"Modo: Webcam ({self.barcode_mgr.camera_index})"
            safe_update(self.camera_verification_text)
            safe_update(self.scanner_status_badge)
        except Exception as e:
            print(f"[PosView] Error al alternar ventana OpenCV: {e}")

    def _process_checkout(self, _) -> None:
        """Ejecuta el proceso de cobro con manejo defensivo de errores."""
        try:
            success, message, invoice = self.pos.checkout()
            if not success:
                self._show_banner_error(message)
                return

            # Extracción segura de datos para evitar fallos por lazy-loading
            customer_name = None
            try:
                if invoice and invoice.customer:
                    customer_name = invoice.customer.name
            except Exception:
                customer_name = "Cliente Asignado"

            created_at_str = invoice.created_at.strftime('%Y-%m-%d %H:%M:%S') if invoice and invoice.created_at else "Hoy"
            payment_type_str = "Crédito (Cartera)" if invoice and invoice.payment_type == "CREDIT" else "Contado / Efectivo"
            credit_notes_str = invoice.credit_notes if invoice and invoice.credit_notes else None
            total_val = invoice.total if invoice else 0.0

            # Listado de productos para el ticket
            items_controls = []
            if invoice and invoice.items:
                items_controls.append(ft.Text("Productos Comprados:", size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_SECONDARY))
                for it in invoice.items:
                    items_controls.append(
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(f"{it.product_name} x{it.quantity}", size=12, color=PastelTheme.TEXT_PRIMARY),
                                ft.Text(f"${it.subtotal:,.0f}", size=12, weight=ft.FontWeight.W_500, color=PastelTheme.TEXT_PRIMARY)
                            ]
                        )
                    )

            # Modal de Confirmación de Factura / Ticket
            ticket_dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=PastelTheme.ACCENT_MINT, size=28),
                    ft.Text("Venta Exitosa", weight=ft.FontWeight.BOLD)
                ]),
                content=ft.Container(
                    width=420,
                    content=ft.Column(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.Text(f"Factura: #{invoice.invoice_number}", size=15, weight=ft.FontWeight.BOLD),
                            ft.Text(f"Fecha: {created_at_str}", size=12, color=PastelTheme.TEXT_MUTED),
                            ft.Text(f"Modalidad: {payment_type_str}", size=13),
                            *( [ft.Text(f"Cliente: {customer_name}", size=13, weight=ft.FontWeight.W_500)] if customer_name else [] ),
                            *( [ft.Text(f"Detalle Crédito: {credit_notes_str}", size=12, italic=True)] if credit_notes_str else [] ),
                            ft.Divider(color=PastelTheme.BORDER_LIGHT),
                            *items_controls,
                            ft.Divider(color=PastelTheme.BORDER_LIGHT),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("TOTAL COBRADO:", weight=ft.FontWeight.BOLD),
                                    ft.Text(f"${total_val:,.0f}", size=18, weight=ft.FontWeight.BOLD, color=PastelTheme.PRIMARY)
                                ]
                            )
                        ]
                    )
                ),
                actions=[
                    ft.FilledButton(
                        "Aceptar y Nueva Venta",
                        bgcolor=PastelTheme.PRIMARY,
                        color=PastelTheme.TEXT_ON_PRIMARY,
                        on_click=lambda _: self.page.pop_dialog()
                    )
                ]
            )
            self.page.show_dialog(ticket_dialog)
        except Exception as ex:
            print(f"[POS ERROR] Fallo inesperado en cobro: {ex}")
            self._show_banner_error(f"Ocurrió un error al registrar la venta: {str(ex)}")

    def _show_banner_error(self, message: str) -> None:
        err_dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=PastelTheme.ACCENT_CORAL, size=24),
                ft.Text("Aviso del Sistema", weight=ft.FontWeight.BOLD)
            ]),
            content=ft.Text(message),
            actions=[
                ft.TextButton("Entendido", on_click=lambda _: self.page.pop_dialog())
            ]
        )
        self.page.show_dialog(err_dialog)
