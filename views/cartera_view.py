import flet as ft
from typing import Optional
from config import PastelTheme
from controllers import CustomerController
from views.theme import create_card, create_badge, safe_update

class CarteraView(ft.Container):
    """
    Vista del Módulo de Cartera (Clientes, Proveedores y Créditos).
    - Registro y administración de perfiles de clientes y proveedores.
    - Control de límites de crédito, consulta de facturas a crédito pendientes y liquidación.
    """
    def __init__(self, customer_controller: CustomerController):
        super().__init__(expand=True)
        self.controller = customer_controller
        self.padding = 24

        self.current_tab = "CLIENTES" # "CLIENTES" o "PROVEEDORES"

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
                                ft.Text("Administración de clientes, cupos de crédito y relación con proveedores", size=13, color=PastelTheme.TEXT_SECONDARY)
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
                create_badge(f"Deuda: ${c['current_debt']:,.0f}", PastelTheme.CORAL_PASTEL, PastelTheme.ACCENT_CORAL)
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
                                ft.Text(f"Doc: {c['document_id'] or 'S/N'} | Tel: {c['phone'] or 'S/T'} | Cupo: ${c['credit_limit']:,.0f}", size=12, color=PastelTheme.TEXT_SECONDARY),
                                *( [ft.Text(f"Notas: {c['notes']}", size=11, color=PastelTheme.TEXT_MUTED, italic=True)] if c["notes"] else [] )
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
                                *( [ft.Text(f"Condiciones: {s['notes']}", size=11, color=PastelTheme.TEXT_MUTED, italic=True)] if s["notes"] else [] )
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

    def _show_credit_history(self, customer_id: int, customer_name: str) -> None:
        """Modal con el historial de facturas a crédito del cliente y opción de liquidación."""
        invoices = self.controller.get_customer_credit_invoices(customer_id)

        rows = []
        for inv in invoices:
            is_pending = (inv["payment_status"] == "PENDING")
            status_badge = (
                create_badge("PENDIENTE", PastelTheme.CORAL_PASTEL, PastelTheme.ACCENT_CORAL)
                if is_pending else
                create_badge("PAGADA", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)
            )

            row = ft.Container(
                bgcolor=PastelTheme.SURFACE_WHITE,
                border_radius=8,
                padding=10,
                border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Row([
                                    ft.Text(f"#{inv['invoice_number']}", weight=ft.FontWeight.BOLD, size=13),
                                    status_badge
                                ]),
                                ft.Text(f"Fecha: {inv['created_at']}", size=11, color=PastelTheme.TEXT_MUTED),
                                *( [ft.Text(f"Descripción: {inv['credit_notes']}", size=11, italic=True)] if inv["credit_notes"] else [] )
                            ]
                        ),
                        ft.Row([
                            ft.Text(f"${inv['total']:,.0f}", size=14, weight=ft.FontWeight.BOLD, color=PastelTheme.PRIMARY),
                            *( [
                                ft.FilledButton(
                                    "Abonar / Pagar",
                                    style=ft.ButtonStyle(
                                        bgcolor=PastelTheme.MINT_PASTEL,
                                        color=PastelTheme.ACCENT_MINT,
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        elevation=0
                                    ),
                                    on_click=lambda _, iid=inv["id"]: self._pay_credit(iid)
                                )
                            ] if is_pending else [] )
                        ])
                    ]
                )
            )
            rows.append(row)

        if not rows:
            rows.append(ft.Text("No hay facturas a crédito asociadas a este cliente.", color=PastelTheme.TEXT_MUTED))

        dialog = ft.AlertDialog(
            title=ft.Text(f"Créditos de {customer_name}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=550,
                content=ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, tight=True, controls=rows)
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda _: self.page.pop_dialog())
            ]
        )
        self.page.show_dialog(dialog)

    def _pay_credit(self, invoice_id: int) -> None:
        self.controller.pay_credit_invoice(invoice_id)
        self.page.pop_dialog()
        self.load_data()
