from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from database import get_db_session
from models import Customer, Supplier, Invoice, InvoiceItem, InvoicePayment


class CustomerController:
    """Controlador para Cartera: Gestión de Clientes, Proveedores, Créditos, Abonos y Detalle de Facturas."""

    # ================= CLIENTES =================

    def get_all_customers(self, search_query: str = "") -> List[Dict[str, Any]]:
        with get_db_session() as session:
            query = session.query(Customer).filter(Customer.is_active == True)
            if search_query.strip():
                term = f"%{search_query.strip()}%"
                query = query.filter(
                    or_(
                        Customer.name.ilike(term),
                        Customer.document_id.ilike(term),
                        Customer.phone.ilike(term)
                    )
                )
            customers = query.order_by(Customer.name.asc()).all()
            return [c.to_dict() for c in customers]

    def create_customer(
        self,
        name: str,
        document_id: str = "",
        phone: str = "",
        email: str = "",
        address: str = "",
        credit_limit: float = 0.0,
        notes: str = ""
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        if not name.strip():
            return False, "El nombre del cliente es obligatorio.", None

        with get_db_session() as session:
            customer = Customer(
                name=name.strip(),
                document_id=document_id.strip() if document_id else None,
                phone=phone.strip() if phone else None,
                email=email.strip() if email else None,
                address=address.strip() if address else None,
                credit_limit=float(credit_limit),
                notes=notes.strip() if notes else None
            )
            session.add(customer)
            session.commit()
            session.refresh(customer)
            return True, f"Cliente '{customer.name}' registrado exitosamente.", customer.to_dict()

    def update_customer(
        self,
        customer_id: int,
        name: str,
        document_id: str = "",
        phone: str = "",
        email: str = "",
        address: str = "",
        credit_limit: float = 0.0,
        notes: str = ""
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        with get_db_session() as session:
            customer = session.query(Customer).filter_by(id=customer_id).first()
            if not customer:
                return False, "Cliente no encontrado.", None

            customer.name = name.strip()
            customer.document_id = document_id.strip() if document_id else None
            customer.phone = phone.strip() if phone else None
            customer.email = email.strip() if email else None
            customer.address = address.strip() if address else None
            customer.credit_limit = float(credit_limit)
            customer.notes = notes.strip() if notes else None

            session.commit()
            session.refresh(customer)
            return True, f"Cliente '{customer.name}' actualizado.", customer.to_dict()

    # ================= CRÉDITOS, ABONOS Y DETALLE DE FACTURA (DRILL-DOWN) =================

    def get_customer_credit_invoices(self, customer_id: int) -> List[Dict[str, Any]]:
        """Obtiene el historial de facturas a crédito de un cliente con sus abonos y saldos."""
        with get_db_session() as session:
            invoices = (
                session.query(Invoice)
                .options(
                    joinedload(Invoice.customer),
                    joinedload(Invoice.items).joinedload(InvoiceItem.product),
                    joinedload(Invoice.payments),
                )
                .filter(
                    Invoice.customer_id == customer_id,
                    Invoice.payment_type == "CREDIT",
                )
                .order_by(Invoice.created_at.desc())
                .all()
            )
            return [inv.to_dict() for inv in invoices]

    def get_invoice_details(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        """
        Consulta mediante JOIN / relaciones SQLAlchemy el detalle profundo de una Factura
        (Cabecera, Descripción de la venta, Tabla de Productos con nombre + presentación,
        e historial justificado de Abonos con Fecha y Hora exacta).
        Diseñado en modo de solo lectura (Read-Only) para inspección en Cartera.
        """
        with get_db_session() as session:
            invoice = (
                session.query(Invoice)
                .options(
                    joinedload(Invoice.customer),
                    joinedload(Invoice.items).joinedload(InvoiceItem.product),
                    joinedload(Invoice.payments),
                )
                .filter(Invoice.id == invoice_id)
                .first()
            )
            if not invoice:
                return None

            data = invoice.to_dict()
            raw_desc = (invoice.credit_notes or "").strip()
            data["description_display"] = raw_desc if raw_desc else "Sin descripción adicional"
            return data

    def register_credit_abono(
        self,
        invoice_id: int,
        abono_amount: float,
        notes: str = "",
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Registra un abono parcial (o total) a una factura a crédito:
        - Descuenta el valor del abono del saldo pendiente de la factura sin alterar
          el valor original de la venta ni los abonos anteriores.
        - Registra la justificación con la Fecha y Hora exacta (DateTime) del abono.
        - Si el saldo llega a 0, marca automáticamente la factura como PAGADA.
        """
        if abono_amount <= 0:
            return False, "El valor del abono debe ser mayor a $0.", None

        with get_db_session() as session:
            invoice = (
                session.query(Invoice)
                .options(joinedload(Invoice.payments), joinedload(Invoice.items))
                .filter(Invoice.id == invoice_id)
                .first()
            )
            if not invoice:
                return False, "Factura no encontrada.", None
            if invoice.payment_status == "PAID" or invoice.balance_due <= 0:
                return False, "La factura ya se encuentra totalmente pagada.", None

            current_balance = invoice.balance_due
            if abono_amount > current_balance + 0.01:
                return (
                    False,
                    f"El abono (${abono_amount:,.0f}) no puede superar el saldo pendiente (${current_balance:,.0f}).",
                    None,
                )

            now_dt = datetime.now()
            applied_amount = min(round(float(abono_amount), 2), current_balance)
            new_paid = round(invoice.total_abonos + applied_amount, 2)
            new_balance = max(0.0, round(float(invoice.total) - new_paid, 2))
            is_fully_paid = (new_balance <= 0.0)

            clean_note = notes.strip() if notes and notes.strip() else (
                "Abono que liquida el saldo total" if is_fully_paid else "Abono parcial a factura de crédito"
            )

            payment_record = InvoicePayment(
                invoice_id=invoice.id,
                fecha_hora=now_dt,
                amount=applied_amount,
                balance_after=new_balance,
                payment_kind="PAGO_TOTAL" if is_fully_paid else "ABONO",
                notes=clean_note,
            )
            session.add(payment_record)

            invoice.amount_paid = new_paid
            if is_fully_paid:
                invoice.payment_status = "PAID"

            session.commit()
            session.refresh(invoice)
            return (
                True,
                (
                    f"Abono de ${applied_amount:,.0f} registrado el {now_dt.strftime('%Y-%m-%d %H:%M:%S')}. "
                    f"Saldo restante: ${new_balance:,.0f}."
                ),
                invoice.to_dict(),
            )

    def pay_credit_invoice(self, invoice_id: int) -> tuple[bool, str]:
        """
        Paga la totalidad del saldo pendiente de una factura a crédito,
        registrando la justificación con la Fecha y Hora exacta de la liquidación.
        """
        with get_db_session() as session:
            invoice = (
                session.query(Invoice)
                .options(joinedload(Invoice.payments))
                .filter_by(id=invoice_id)
                .first()
            )
            if not invoice:
                return False, "Factura no encontrada."
            if invoice.payment_status == "PAID":
                return False, "La factura ya se encuentra cancelada/pagada."

            remaining = invoice.balance_due
            now_dt = datetime.now()
            if remaining > 0:
                payment_record = InvoicePayment(
                    invoice_id=invoice.id,
                    fecha_hora=now_dt,
                    amount=remaining,
                    balance_after=0.0,
                    payment_kind="PAGO_TOTAL",
                    notes="Pago total de la factura",
                )
                session.add(payment_record)

            invoice.amount_paid = round(float(invoice.total), 2)
            invoice.payment_status = "PAID"
            session.commit()
            return (
                True,
                f"Factura #{invoice.invoice_number} pagada en su totalidad (${remaining:,.0f}) el {now_dt.strftime('%Y-%m-%d %H:%M:%S')}.",
            )

    # ================= PROVEEDORES =================

    def get_all_suppliers(self, search_query: str = "") -> List[Dict[str, Any]]:
        with get_db_session() as session:
            query = session.query(Supplier).filter(Supplier.is_active == True)
            if search_query.strip():
                term = f"%{search_query.strip()}%"
                query = query.filter(
                    or_(
                        Supplier.name.ilike(term),
                        Supplier.contact_name.ilike(term),
                        Supplier.phone.ilike(term)
                    )
                )
            suppliers = query.order_by(Supplier.name.asc()).all()
            return [s.to_dict() for s in suppliers]

    def create_supplier(
        self,
        name: str,
        contact_name: str = "",
        phone: str = "",
        email: str = "",
        address: str = "",
        notes: str = ""
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        if not name.strip():
            return False, "El nombre del proveedor es obligatorio.", None

        with get_db_session() as session:
            supplier = Supplier(
                name=name.strip(),
                contact_name=contact_name.strip() if contact_name else None,
                phone=phone.strip() if phone else None,
                email=email.strip() if email else None,
                address=address.strip() if address else None,
                notes=notes.strip() if notes else None
            )
            session.add(supplier)
            session.commit()
            session.refresh(supplier)
            return True, f"Proveedor '{supplier.name}' registrado.", supplier.to_dict()
