from typing import List, Optional, Dict, Any
from sqlalchemy import or_

from database import get_db_session
from models import Customer, Supplier, Invoice

class CustomerController:
    """Controlador para Cartera: Gestión de Clientes, Proveedores y Créditos."""

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

    def get_customer_credit_invoices(self, customer_id: int) -> List[Dict[str, Any]]:
        """Obtiene el historial de facturas a crédito de un cliente."""
        with get_db_session() as session:
            invoices = session.query(Invoice).filter(
                Invoice.customer_id == customer_id,
                Invoice.payment_type == "CREDIT"
            ).order_by(Invoice.created_at.desc()).all()
            return [inv.to_dict() for inv in invoices]

    def pay_credit_invoice(self, invoice_id: int) -> tuple[bool, str]:
        """Liquida/abona una factura a crédito marcándola como PAGADA."""
        with get_db_session() as session:
            invoice = session.query(Invoice).filter_by(id=invoice_id).first()
            if not invoice:
                return False, "Factura no encontrada."
            if invoice.payment_status == "PAID":
                return False, "La factura ya se encuentra cancelada/pagada."

            invoice.payment_status = "PAID"
            session.commit()
            return True, f"Factura #{invoice.invoice_number} liquidada exitosamente."

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
