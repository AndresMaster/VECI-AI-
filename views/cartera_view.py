import flet as ft
from typing import Optional
from config import PastelTheme
from controllers import CustomerController
from views.theme import create_card, create_badge, safe_update


class CarteraView(ft.Container):
    """
    Vista del Módulo de Cartera (Clientes, Proveedores y Créditos).
    - Registro y administración de perfiles de clientes y proveedores.
    - Control de límites de crédito, consulta de facturas a crédito pendientes,
      registro de Abonos parciales justificados con fecha/hora exacta, Pago Total,
      y modal de inspección profunda ("Ver Detalle" / Drill-Down Read-Only) de cada factura.
    """
    def __init__(self, customer_controller: CustomerController):
        super().__init__(expand=True)
        self.controller = customer_controller
        self.padding = 24

        self.current_tab = "CLIENTES"  # "CLIENTES" o "PROVEEDORES"

        self.list_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

        self.tab_clientes_btn = ft.FilledButton(
            "Clientes y Créditos",
            style=ft.ButtonStyle(
                bgcolor=PastelTheme.PRIMARY,
                color=PastelTheme.TEXT_ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
            ),
            on_click=lambda _: self._switch_tab("CLIENTES")
        )

        self.tab_proveedores_btn = ft.OutlinedButton(
            "Proveedores",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
            ),
            on_click=lambda _: self._switch_tab("PROVEEDORES")
        )

        self.content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Header
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text("Cartera y Contactos", size=24, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                ft.Text("Administración de clientes, cupos de crédito, abonos e inspección de facturas", size=13, color=PastelTheme.TEXT_SECONDARY)
                            ]
                        ),
                        ft.FilledButton(
                            content=ft.Row([ft.Icon(ft.Icons.PERSON_ADD_ROUNDED, size=18), ft.Text("Nuevo Registro")]),
                            style=ft.ButtonStyle(
                                bgcolor=PastelTheme.PRIMARY,
                                color=PastelTheme.TEXT_ON_PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=PastelTheme.BORDER_RADIUS_BUTTON),
                            ),
                            on_click=lambda _: self._open_create_modal()
                        )
                    ]
                ),

                # Selector de Pestaña
                ft.Row(
                    spacing=10,
                    controls=[
                        self.tab_clientes_btn,
                        self.tab_proveedores_btn
                    ]
                ),

                # Tarjeta de Listado
                create_card(
                    expand=True,
                    padding=16,
                    content=self.list_column
                )
            ]
        )

        self.load_data()

    def _switch_tab(self, tab: str) -> None:
        self.current_tab = tab
        if tab == "CLIENTES":
            self.tab_clientes_btn.style.bgcolor = PastelTheme.PRIMARY
            self.tab_clientes_btn.style.color = PastelTheme.TEXT_ON_PRIMARY
            self.tab_proveedores_btn.style.bgcolor = None
            self.tab_proveedores_btn.style.color = PastelTheme.TEXT_PRIMARY
        else:
            self.tab_proveedores_btn.style.bgcolor = PastelTheme.PRIMARY
            self.tab_proveedores_btn.style.color = PastelTheme.TEXT_ON_PRIMARY
            self.tab_clientes_btn.style.bgcolor = None
            self.tab_clientes_btn.style.color = PastelTheme.TEXT_PRIMARY

        self.load_data()
        self.update()

    def load_data(self) -> None:
        if self.current_tab == "CLIENTES":
            self._render_customers()
        else:
            self._render_suppliers()

        safe_update(self)

    def _render_customers(self) -> None:
        customers = self.controller.get_all_customers()
        items = []
        for c in customers:
            has_debt = c["current_debt"] > 0
            debt_badge = (
                create_badge(f"Deuda Pendiente: ${c['current_debt']:,.0f}", PastelTheme.CORAL_PASTEL, PastelTheme.ACCENT_CORAL)
                if has_debt else
                create_badge("Al Día", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)
            )

            card = ft.Container(
                bgcolor=PastelTheme.SURFACE_VARIANT,
                border_radius=12,
                padding=14,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=3,
                            controls=[
                                ft.Row([
                                    ft.Text(c["name"], size=15, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                    debt_badge
                                ]),
                                ft.Text(
                                    f"Doc: {c['document_id'] or 'S/N'} | Tel: {c['phone'] or 'S/T'} | "
                                    f"Cupo: ${c['credit_limit']:,.0f} (Disp: ${c['available_credit']:,.0f})",
                                    size=12,
                                    color=PastelTheme.TEXT_SECONDARY
                                ),
                                *([ft.Text(f"Notas: {c['notes']}", size=11, color=PastelTheme.TEXT_MUTED, italic=True)] if c["notes"] else [])
                            ]
                        ),
                        ft.FilledButton(
                            content=ft.Row([ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, size=16), ft.Text("Ver Créditos")]),
                            style=ft.ButtonStyle(
                                bgcolor=PastelTheme.PRIMARY_PASTEL,
                                color=PastelTheme.PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                elevation=0
                            ),
                            on_click=lambda _, cid=c["id"], cname=c["name"]: self._show_credit_history(cid, cname)
                        )
                    ]
                )
            )
            items.append(card)

        if not items:
            items.append(ft.Container(padding=30, alignment=ft.Alignment.CENTER, content=ft.Text("No hay clientes registrados.")))
        self.list_column.controls = items

    def _render_suppliers(self) -> None:
        suppliers = self.controller.get_all_suppliers()
        items = []
        for s in suppliers:
            card = ft.Container(
                bgcolor=PastelTheme.SURFACE_VARIANT,
                border_radius=12,
                padding=14,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=3,
                            controls=[
                                ft.Text(s["name"], size=15, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                ft.Text(f"Contacto: {s['contact_name'] or 'N/A'} | Tel: {s['phone'] or 'N/A'} | Email: {s['email'] or 'N/A'}", size=12, color=PastelTheme.TEXT_SECONDARY),
                                *([ft.Text(f"Condiciones: {s['notes']}", size=11, color=PastelTheme.TEXT_MUTED, italic=True)] if s["notes"] else [])
                            ]
                        ),
                        create_badge("Proveedor Activo", PastelTheme.SKY_PASTEL, PastelTheme.ACCENT_SKY)
                    ]
                )
            )
            items.append(card)

        if not items:
            items.append(ft.Container(padding=30, alignment=ft.Alignment.CENTER, content=ft.Text("No hay proveedores registrados.")))
        self.list_column.controls = items

    def _open_create_modal(self) -> None:
        if self.current_tab == "CLIENTES":
            name_tf = ft.TextField(label="Nombre Completo", border_radius=8, dense=True)
            doc_tf = ft.TextField(label="Documento (Cédula/NIT)", border_radius=8, dense=True)
            phone_tf = ft.TextField(label="Teléfono", border_radius=8, dense=True)
            credit_tf = ft.TextField(label="Cupo de Crédito ($)", value="0", border_radius=8, dense=True)
            notes_tf = ft.TextField(label="Notas / Condiciones", border_radius=8, dense=True, multiline=True)

            def save_c(_):
                c_val = float(credit_tf.value or 0)
                self.controller.create_customer(name_tf.value, doc_tf.value, phone_tf.value, credit_limit=c_val, notes=notes_tf.value)
                self.page.pop_dialog()
                self.load_data()

            dialog = ft.AlertDialog(
                title=ft.Text("Registrar Cliente (Cartera)", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    width=400,
                    content=ft.Column(tight=True, spacing=10, controls=[name_tf, doc_tf, phone_tf, credit_tf, notes_tf])
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                    ft.FilledButton("Guardar", bgcolor=PastelTheme.PRIMARY, color=PastelTheme.TEXT_ON_PRIMARY, on_click=save_c)
                ]
            )
            self.page.show_dialog(dialog)
        else:
            name_tf = ft.TextField(label="Razón Social / Nombre", border_radius=8, dense=True)
            contact_tf = ft.TextField(label="Persona de Contacto", border_radius=8, dense=True)
            phone_tf = ft.TextField(label="Teléfono", border_radius=8, dense=True)
            email_tf = ft.TextField(label="Correo Electrónico", border_radius=8, dense=True)
            notes_tf = ft.TextField(label="Notas / Días de entrega", border_radius=8, dense=True)

            def save_s(_):
                self.controller.create_supplier(name_tf.value, contact_tf.value, phone_tf.value, email_tf.value, notes=notes_tf.value)
                self.page.pop_dialog()
                self.load_data()

            dialog = ft.AlertDialog(
                title=ft.Text("Registrar Proveedor", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    width=400,
                    content=ft.Column(tight=True, spacing=10, controls=[name_tf, contact_tf, phone_tf, email_tf, notes_tf])
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: self.page.pop_dialog()),
                    ft.FilledButton("Guardar", bgcolor=PastelTheme.PRIMARY, color=PastelTheme.TEXT_ON_PRIMARY, on_click=save_s)
                ]
            )
            self.page.show_dialog(dialog)

    # ================= HISTORIAL DE CRÉDITOS, ABONOS, PAGO TOTAL Y DRILL-DOWN =================

    def _show_credit_history(self, customer_id: int, customer_name: str) -> None:
        """
        Modal con el historial de facturas a crédito del cliente:
        - Botones separados para 'Abonar' (pago parcial con justificación de fecha/hora) y 'Pagar' (pago total).
        - Botón de acción 'Ver Detalle' (icono de ojo) al final de cada fila para inspección profunda (Read-Only).
        """
        invoices = self.controller.get_customer_credit_invoices(customer_id)

        rows = []
        for inv in invoices:
            is_pending = (inv["payment_status"] == "PENDING" and inv["balance_due"] > 0)
            has_abonos = (inv["amount_paid"] > 0 and is_pending)
            payments_list = inv.get("payments", [])

            if not is_pending:
                status_badge = create_badge("PAGADA", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)
            elif has_abonos:
                status_badge = create_badge("ABONO PARCIAL", PastelTheme.AMBER_PASTEL, PastelTheme.ACCENT_AMBER)
            else:
                status_badge = create_badge("PENDIENTE", PastelTheme.CORAL_PASTEL, PastelTheme.ACCENT_CORAL)

            # Bloque de justificación de abonos realizados dentro de la factura (sin eliminar lo anterior)
            abonos_justification_controls = []
            if payments_list:
                abono_lines = []
                for pay in payments_list:
                    kind_label = "Pago Total" if pay["payment_kind"] == "PAGO_TOTAL" else "Abono"
                    note_suffix = f" ({pay['notes']})" if pay.get("notes") else ""
                    abono_lines.append(
                        ft.Row(
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                ft.Icon(ft.Icons.HISTORY_EDU_ROUNDED, size=14, color=PastelTheme.ACCENT_SKY),
                                ft.Text(
                                    f"[{pay['fecha_hora']}] {kind_label}: -${pay['amount']:,.0f} "
                                    f"→ Saldo: ${pay['balance_after']:,.0f}{note_suffix}",
                                    size=11,
                                    color=PastelTheme.TEXT_SECONDARY,
                                    expand=True,
                                ),
                            ],
                        )
                    )
                abonos_justification_controls.append(
                    ft.Container(
                        bgcolor=PastelTheme.SKY_PASTEL,
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        margin=ft.Margin.only(top=4),
                        content=ft.Column(
                            spacing=3,
                            controls=[
                                ft.Text(
                                    f"Historial de Abonos (Total original: ${inv['total']:,.0f} | Abonado: ${inv['amount_paid']:,.0f}):",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=PastelTheme.ACCENT_SKY,
                                ),
                                *abono_lines,
                            ],
                        ),
                    )
                )

            # Monto visible a la derecha: muestra el Saldo Pendiente actual (y el total original si hubo abonos)
            amount_column = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                content=ft.Column(
                    spacing=1,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        ft.Text(
                            "Saldo Pendiente" if is_pending else "Total Pagado",
                            size=10,
                            color=PastelTheme.TEXT_SECONDARY,
                        ),
                        ft.Text(
                            f"${inv['balance_due']:,.0f}" if is_pending else f"${inv['total']:,.0f}",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            color=PastelTheme.ACCENT_CORAL if is_pending else PastelTheme.PRIMARY,
                        ),
                        *(
                            [
                                ft.Text(
                                    f"De ${inv['total']:,.0f} orig.",
                                    size=10,
                                    color=PastelTheme.TEXT_MUTED,
                                )
                            ]
                            if has_abonos
                            else []
                        ),
                    ],
                ),
            )

            # Botones de acción separados: [Abonar] [Pagar] [Ver Detalle (Ojo)]
            action_buttons = []
            if is_pending:
                action_buttons.append(
                    ft.FilledButton(
                        content=ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.ADD_CARD_ROUNDED, size=15),
                                ft.Text("Abonar", size=12),
                            ],
                        ),
                        tooltip="Registrar un abono parcial justificado con fecha y hora",
                        style=ft.ButtonStyle(
                            bgcolor=PastelTheme.SKY_PASTEL,
                            color=PastelTheme.ACCENT_SKY,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                            elevation=0,
                        ),
                        on_click=lambda _, inv_dict=inv: self._open_abono_modal(
                            inv_dict, customer_id, customer_name
                        ),
                    )
                )
                action_buttons.append(
                    ft.FilledButton(
                        content=ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=15),
                                ft.Text("Pagar", size=12),
                            ],
                        ),
                        tooltip="Pagar la totalidad del saldo pendiente de esta factura",
                        style=ft.ButtonStyle(
                            bgcolor=PastelTheme.MINT_PASTEL,
                            color=PastelTheme.ACCENT_MINT,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                            elevation=0,
                        ),
                        on_click=lambda _, iid=inv["id"]: self._pay_credit_full(
                            iid, customer_id, customer_name
                        ),
                    )
                )

            # Botón de inspección profunda "Ver Detalle" (Icono de ojo) al final de cada fila
            action_buttons.append(
                ft.OutlinedButton(
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.VISIBILITY_ROUNDED, size=16, color=PastelTheme.PRIMARY),
                            ft.Text("Ver Detalle", size=12, weight=ft.FontWeight.W_600, color=PastelTheme.PRIMARY),
                        ],
                    ),
                    tooltip="Inspeccionar productos, cantidades y precios de esta factura (Solo lectura)",
                    style=ft.ButtonStyle(
                        bgcolor=PastelTheme.PRIMARY_PASTEL,
                        side=ft.BorderSide(1, PastelTheme.PRIMARY),
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    ),
                    on_click=lambda _, iid=inv["id"]: self._show_invoice_detail_modal(
                        iid, customer_id, customer_name
                    ),
                )
            )

            row = ft.Container(
                bgcolor=PastelTheme.SURFACE_WHITE,
                border_radius=12,
                padding=14,
                border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                            controls=[
                                ft.Column(
                                    spacing=3,
                                    expand=True,
                                    controls=[
                                        ft.Row(
                                            spacing=8,
                                            wrap=True,
                                            controls=[
                                                ft.Text(f"#{inv['invoice_number']}", weight=ft.FontWeight.BOLD, size=14, color=PastelTheme.TEXT_PRIMARY),
                                                status_badge,
                                            ],
                                        ),
                                        ft.Text(f"Fecha y Hora: {inv['created_at']}", size=11, color=PastelTheme.TEXT_MUTED),
                                        *(
                                            [
                                                ft.Text(
                                                    f"Descripción: {inv['credit_notes']}",
                                                    size=11,
                                                    color=PastelTheme.TEXT_SECONDARY,
                                                    italic=True,
                                                )
                                            ]
                                            if inv["credit_notes"]
                                            else []
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        amount_column,
                                        *action_buttons,
                                    ],
                                ),
                            ],
                        ),
                        *abonos_justification_controls,
                    ],
                ),
            )
            rows.append(row)

        if not rows:
            rows.append(
                ft.Container(
                    padding=24,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("No hay facturas a crédito asociadas a este cliente.", color=PastelTheme.TEXT_MUTED),
                )
            )

        dialog = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=PastelTheme.BG_LIGHT,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=8,
                        expand=True,
                        controls=[
                            ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=PastelTheme.PRIMARY, size=24),
                            ft.Text(
                                f"Créditos de {customer_name}",
                                weight=ft.FontWeight.BOLD,
                                size=18,
                                expand=True,
                            ),
                        ],
                    ),
                    create_badge(f"{len(invoices)} facturas", PastelTheme.PRIMARY_PASTEL, PastelTheme.PRIMARY),
                ],
            ),
            content=ft.Container(
                width=780,
                content=ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, tight=True, controls=rows),
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda _: self.page.pop_dialog())
            ],
        )
        self.page.show_dialog(dialog)

    def _open_abono_modal(self, invoice_data: dict, customer_id: int, customer_name: str) -> None:
        """
        Ventana modal para ingresar el valor de un Abono a la factura.
        El abono se resta del saldo pendiente de la factura sin eliminar el historial anterior,
        quedando justificado dentro de la factura con fecha y hora exacta.
        """
        self.page.pop_dialog()

        invoice_id = invoice_data["id"]
        invoice_num = invoice_data["invoice_number"]
        original_total = invoice_data["total"]
        already_paid = invoice_data["amount_paid"]
        balance_due = invoice_data["balance_due"]

        amount_tf = ft.TextField(
            label="Valor del Abono ($)",
            hint_text=f"Máximo: {balance_due:,.0f}",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=10,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_color=PastelTheme.PRIMARY,
            autofocus=True,
            dense=True,
        )

        notes_tf = ft.TextField(
            label="Justificación / Observación del Abono (Opcional)",
            hint_text="Ej. Abono en efectivo recibido en caja...",
            border_radius=10,
            bgcolor=PastelTheme.SURFACE_WHITE,
            dense=True,
        )

        error_text = ft.Text("", size=12, color=PastelTheme.ACCENT_CORAL, visible=False)

        def return_to_credits(_=None):
            self.page.pop_dialog()
            self._show_credit_history(customer_id, customer_name)

        def confirm_abono(_=None):
            try:
                val = float((amount_tf.value or "").replace(",", "").strip())
            except ValueError:
                error_text.value = "Por favor ingresa un monto numérico válido."
                error_text.visible = True
                safe_update(error_text)
                return

            ok, msg, _ = self.controller.register_credit_abono(
                invoice_id=invoice_id,
                abono_amount=val,
                notes=notes_tf.value or "",
            )
            if not ok:
                error_text.value = msg
                error_text.visible = True
                safe_update(error_text)
                return

            self.page.pop_dialog()
            self.load_data()
            self._show_credit_history(customer_id, customer_name)

        amount_tf.on_submit = confirm_abono

        abono_dialog = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=PastelTheme.SURFACE_WHITE,
            title=ft.Row([
                ft.Icon(ft.Icons.ADD_CARD_ROUNDED, color=PastelTheme.ACCENT_SKY, size=24),
                ft.Text(f"Registrar Abono — #{invoice_num}", weight=ft.FontWeight.BOLD, size=17),
            ]),
            content=ft.Container(
                width=460,
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[
                        ft.Container(
                            bgcolor=PastelTheme.SKY_PASTEL,
                            border_radius=10,
                            padding=12,
                            content=ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text("Total Original Factura:", size=12, color=PastelTheme.TEXT_SECONDARY),
                                            ft.Text(f"${original_total:,.0f}", size=12, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text("Total Abonado Previamente:", size=12, color=PastelTheme.TEXT_SECONDARY),
                                            ft.Text(f"-${already_paid:,.0f}", size=12, weight=ft.FontWeight.BOLD, color=PastelTheme.ACCENT_MINT),
                                        ],
                                    ),
                                    ft.Divider(height=1, color=PastelTheme.BORDER_LIGHT),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text("Saldo Pendiente Actual:", size=13, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                                            ft.Text(f"${balance_due:,.0f}", size=15, weight=ft.FontWeight.BOLD, color=PastelTheme.ACCENT_CORAL),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                        amount_tf,
                        notes_tf,
                        ft.Text(
                            "El abono quedará justificado dentro de la factura con la fecha y hora exacta sin eliminar los registros previos.",
                            size=11,
                            color=PastelTheme.TEXT_MUTED,
                            italic=True,
                        ),
                        error_text,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Volver", on_click=return_to_credits),
                ft.FilledButton(
                    "Aplicar Abono",
                    bgcolor=PastelTheme.PRIMARY,
                    color=PastelTheme.TEXT_ON_PRIMARY,
                    on_click=confirm_abono,
                ),
            ],
        )
        self.page.show_dialog(abono_dialog)

    def _pay_credit_full(self, invoice_id: int, customer_id: int, customer_name: str) -> None:
        """Paga la totalidad del saldo de la factura y refresca tanto la vista como el modal de créditos."""
        self.controller.pay_credit_invoice(invoice_id)
        self.page.pop_dialog()
        self.load_data()
        self._show_credit_history(customer_id, customer_name)

    # ================= MODAL "DETALLE DE FACTURA" (DRILL-DOWN READ-ONLY) =================

    def _show_invoice_detail_modal(self, invoice_id: int, customer_id: int, customer_name: str) -> None:
        """
        Modal estilizado de Solo Lectura (Read-Only) con las 3 secciones visuales requeridas:
        1. Cabecera: Número de Factura, Fecha y Hora exacta, y Estado (Pendiente / Abono Parcial / Pagada).
        2. Descripción: Bloque destacado con la descripción de creación de la factura (o 'Sin descripción adicional')
           más el historial justificado de abonos con fecha y hora.
        3. Tabla de Productos (DataTable): Producto (Nombre concatenado con Presentación, ej. 'Chocoramo - 65g'),
           Cantidad, Precio Unitario y Subtotal.
        """
        details = self.controller.get_invoice_details(invoice_id)
        if not details:
            return

        self.page.pop_dialog()

        is_pending = (details["payment_status"] == "PENDING" and details["balance_due"] > 0)
        has_abonos = (details["amount_paid"] > 0 and is_pending)

        if not is_pending:
            status_badge = create_badge("Pagada", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)
        elif has_abonos:
            status_badge = create_badge("Pendiente (Con Abono)", PastelTheme.AMBER_PASTEL, PastelTheme.ACCENT_AMBER)
        else:
            status_badge = create_badge("Pendiente", PastelTheme.CORAL_PASTEL, PastelTheme.ACCENT_CORAL)

        # 1. SECCIÓN CABECERA (Encuadrada responsivamente con expand=True a la izquierda y tarjeta de totales fija a la derecha)
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
                    # Columna izquierda expandible para que nunca empuje el bloque derecho fuera del modal
                    ft.Column(
                        spacing=6,
                        expand=True,
                        controls=[
                            ft.Row(
                                spacing=10,
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
                                        f"Cliente: {details['customer_name']}",
                                        size=12,
                                        weight=ft.FontWeight.W_500,
                                        color=PastelTheme.TEXT_SECONDARY,
                                        expand=True,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Tarjeta derecha bien encuadrada con Total Original, Total Abonado y Saldo Pendiente
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
                                    if details["amount_paid"] > 0 or is_pending
                                    else []
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        # 2. SECCIÓN DESCRIPCIÓN (Contexto de la venta + Justificación de abonos si existen)
        payments = details.get("payments", [])
        payment_history_controls = []
        if payments:
            payment_history_controls.append(ft.Divider(height=8, color=PastelTheme.BORDER_LIGHT))
            payment_history_controls.append(
                ft.Text(
                    "Abonos y Pagos Justificados en esta Factura:",
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
                                "Descripción / Justificación del Crédito",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=PastelTheme.TEXT_PRIMARY,
                            ),
                        ],
                    ),
                    ft.Text(
                        details.get("description_display", "Sin descripción adicional"),
                        size=13,
                        color=PastelTheme.TEXT_PRIMARY,
                        italic=(not bool(details.get("credit_notes", "").strip())),
                    ),
                    *payment_history_controls,
                ],
            ),
        )

        # 3. SECCIÓN TABLA DE PRODUCTOS (Data Table de Solo Lectura / Read-Only)
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
                                        "Artículos Comprados en la Factura (Solo Lectura)",
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

        def back_to_credit_list(_=None):
            self.page.pop_dialog()
            self._show_credit_history(customer_id, customer_name)

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
                            ft.Text("Detalle de Factura", weight=ft.FontWeight.BOLD, size=18, color=PastelTheme.TEXT_PRIMARY),
                        ],
                    ),
                    create_badge("Modo Solo Lectura", PastelTheme.SURFACE_VARIANT, PastelTheme.TEXT_SECONDARY),
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
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=16),
                            ft.Text("Volver a Créditos"),
                        ],
                    ),
                    style=ft.ButtonStyle(
                        bgcolor=PastelTheme.PRIMARY,
                        color=PastelTheme.TEXT_ON_PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                    on_click=back_to_credit_list,
                )
            ],
        )
        self.page.show_dialog(detail_dialog)
