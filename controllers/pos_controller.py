import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from sqlalchemy import or_, select

from database import get_db_session
from models import Product, Customer, Invoice, InvoiceItem

@dataclass
class CartItem:
    """Representación en memoria de un ítem en el borrador de venta del POS."""
    product_id: int
    barcode: str
    name: str
    cost_price: float
    sale_price: float
    quantity: int = 1
    max_stock: int = 0
    presentacion: str = ""

    @property
    def display_name(self) -> str:
        """Nombre concatenado con presentación física (ej. 'Chocoramo - 65g')."""
        if self.presentacion and self.presentacion.strip():
            return f"{self.name} - {self.presentacion.strip()}"
        return self.name

    @property
    def subtotal(self) -> float:
        return round(self.sale_price * self.quantity, 2)

    @property
    def unit_profit(self) -> float:
        return round(self.sale_price - self.cost_price, 2)

    @property
    def total_profit(self) -> float:
        return round(self.unit_profit * self.quantity, 2)


class PosController:
    """
    Controlador de Punto de Venta (POS / Facturación).
    Mantiene el estado persistente del borrador (draft) para no perder la venta
    al navegar entre pestañas, y expone la API `create_invoice_from_ai`
    para futuras integraciones de transcripción por voz.
    """
    def __init__(self):
        # Estado persistente del carrito
        self.items: Dict[str, CartItem] = {} # Key: barcode
        self.customer_id: Optional[int] = None
        self.payment_type: str = "CASH" # 'CASH' o 'CREDIT'
        self.credit_notes: str = ""
        self.discount: float = 0.0

        # Suscriptores para reactividad en la UI de Flet
        self._change_listeners: List[Callable[[], None]] = []

    def subscribe(self, listener: Callable[[], None]) -> None:
        """Registra vistas que desean reaccionar cuando el borrador cambie."""
        if listener not in self._change_listeners:
            self._change_listeners.append(listener)

    def unsubscribe(self, listener: Callable[[], None]) -> None:
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)

    def _notify_change(self) -> None:
        for listener in self._change_listeners:
            try:
                listener()
            except Exception as e:
                print(f"[PosController] Error notificando listener: {e}")

    # ================= CÁLCULOS DEL BORRADOR =================

    @property
    def subtotal(self) -> float:
        return round(sum(item.subtotal for item in self.items.values()), 2)

    @property
    def total(self) -> float:
        return max(0.0, round(self.subtotal - self.discount, 2))

    @property
    def total_items_count(self) -> int:
        return sum(item.quantity for item in self.items.values())

    @property
    def total_estimated_profit(self) -> float:
        return round(sum(item.total_profit for item in self.items.values()), 2)

    # ================= BÚSQUEDA PREDICTIVA (AUTOCOMPLETADO POR NOMBRE) =================

    def search_products_by_name(self, search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Consulta dinámica e instantánea en SQLite usando LIKE '%término_de_búsqueda%' desde la
        primera letra digitada (len >= 1) para el buscador predictivo en Facturación.
        Concatena nombre y presentación física (display_name) para evitar confusiones.
        """
        term = (search_term or "").strip()
        if len(term) < 1:
            return []

        like_pattern = f"%{term}%"
        term_lower = term.lower()
        with get_db_session() as session:
            matches = (
                session.query(Product)
                .filter(
                    Product.is_active == True,
                    or_(
                        Product.name.ilike(like_pattern),
                        Product.presentacion.ilike(like_pattern),
                        Product.barcode.ilike(like_pattern),
                    ),
                )
                .order_by(Product.name.asc(), Product.presentacion.asc())
                .all()
            )
            # Priorizar productos cuyo nombre inicia con la letra/texto digitado
            matches.sort(
                key=lambda p: (
                    0 if (p.name or "").lower().startswith(term_lower) else 1,
                    (p.name or "").lower(),
                    (p.presentacion or "").lower(),
                )
            )
            return [p.to_dict() for p in matches[:limit]]

    # ================= GESTIÓN DEL CARRITO (BORRADOR) =================

    def add_item_to_invoice(self, barcode_or_id: str | int, quantity: int = 1) -> tuple[bool, str]:
        """
        Método unificado invocado tanto por el escáner de código de barras como por
        la selección en la barra de búsqueda predictiva por nombre.
        """
        if isinstance(barcode_or_id, int):
            with get_db_session() as session:
                prod = session.query(Product).filter_by(id=barcode_or_id, is_active=True).first()
                if not prod:
                    return False, "Producto no encontrado. Regístrelo en el módulo de Inventario."
                barcode_str = prod.barcode
            return self.add_product_by_barcode(barcode_str, quantity=quantity)
        return self.add_product_by_barcode(str(barcode_or_id), quantity=quantity)

    def add_product_by_barcode(self, barcode: str, quantity: int = 1) -> tuple[bool, str]:
        """
        Agrega un producto al borrador buscando por código de barras.
        Valida disponibilidad de stock.
        """
        code = barcode.strip()
        with get_db_session() as session:
            product = session.query(Product).filter(
                Product.barcode == code, 
                Product.is_active == True
            ).first()

            # RESTRICCIÓN ESTRICTA: Consultar EXCLUSIVAMENTE base de datos local SQLite (sin llamadas a internet)
            if not product:
                return False, "Producto no encontrado. Regístrelo en el módulo de Inventario."

            current_qty = self.items[code].quantity if code in self.items else 0
            if current_qty + quantity > product.stock:
                return False, f"Stock insuficiente para '{product.display_name}'. Disponible: {product.stock}"

            if code in self.items:
                self.items[code].quantity += quantity
            else:
                self.items[code] = CartItem(
                    product_id=product.id,
                    barcode=product.barcode,
                    name=product.name,
                    presentacion=product.presentacion or "",
                    cost_price=product.cost_price,
                    sale_price=product.sale_price,
                    quantity=quantity,
                    max_stock=product.stock
                )

        self._notify_change()
        return True, f"Agregado: {self.items[code].display_name}"

    def update_quantity(self, barcode: str, quantity: int) -> tuple[bool, str]:
        """Modifica la cantidad de un producto ya presente en el borrador."""
        if barcode not in self.items:
            return False, "El producto no está en el borrador."

        if quantity <= 0:
            return self.remove_item(barcode)

        item = self.items[barcode]
        if quantity > item.max_stock:
            return False, f"No puedes superar el stock disponible ({item.max_stock})."

        item.quantity = quantity
        self._notify_change()
        return True, "Cantidad actualizada."

    def remove_item(self, barcode: str) -> tuple[bool, str]:
        """Elimina un ítem del borrador."""
        if barcode in self.items:
            del self.items[barcode]
            self._notify_change()
            return True, "Producto retirado del borrador."
        return False, "Producto no encontrado en el carrito."

    def clear_draft(self) -> None:
        """Limpia todo el borrador actual."""
        self.items.clear()
        self.customer_id = None
        self.payment_type = "CASH"
        self.credit_notes = ""
        self.discount = 0.0
        self._notify_change()

    def set_customer(self, customer_id: Optional[int]) -> None:
        self.customer_id = customer_id
        self._notify_change()

    def set_payment_options(self, payment_type: str, credit_notes: str = "") -> None:
        self.payment_type = payment_type.upper()
        self.credit_notes = credit_notes
        self._notify_change()

    # ================= PROCESO DE CHECKOUT / FACTURACIÓN =================

    def checkout(self, created_via: str = "POS_DESKTOP") -> tuple[bool, str, Optional[Invoice]]:
        """
        Consolida el borrador en una Factura definitiva en la base de datos:
        1. Valida que haya ítems.
        2. Si es crédito, valida que haya cliente asignado y que no supere límite si aplica.
        3. Descuenta inventario atómicamente.
        4. Crea la factura y sus renglones.
        """
        if not self.items:
            return False, "El borrador de venta está vacío.", None

        if self.payment_type == "CREDIT" and not self.customer_id:
            return False, "Para facturas a crédito es obligatorio seleccionar un cliente.", None

        with get_db_session() as session:
            # Validación de cliente asignado
            customer = None
            if self.customer_id:
                customer = session.query(Customer).filter_by(id=self.customer_id).first()
                if not customer:
                    return False, f"Cliente ID {self.customer_id} no existe.", None

            # Generar número consecutivo de factura y hora exacta de la transacción
            now_dt = datetime.now()
            date_prefix = now_dt.strftime("%Y%m%d")
            count_today = session.query(Invoice).filter(Invoice.invoice_number.like(f"INV-{date_prefix}-%")).count()
            invoice_num = f"INV-{date_prefix}-{(count_today + 1):04d}"

            invoice = Invoice(
                invoice_number=invoice_num,
                created_at=now_dt,
                customer_id=self.customer_id,
                payment_type=self.payment_type,
                payment_status="PENDING" if self.payment_type == "CREDIT" else "PAID",
                subtotal=self.subtotal,
                discount=self.discount,
                tax=0.0,
                total=self.total,
                credit_notes=self.credit_notes if self.payment_type == "CREDIT" else None,
                created_via=created_via
            )
            session.add(invoice)
            session.flush() # Obtiene invoice.id

            # Descontar stock y registrar ítems históricos
            for item in self.items.values():
                product = session.query(Product).filter_by(id=item.product_id).with_for_update().first()
                if not product or product.stock < item.quantity:
                    session.rollback()
                    return False, f"Stock insuficiente en bodega para '{item.name}'.", None

                product.stock -= item.quantity

                invoice_item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_id=product.id,
                    barcode=product.barcode,
                    product_name=product.display_name, # Concatena nombre y presentación (ej. 'Chocoramo - 65g')
                    presentacion=product.presentacion or "",
                    unit_cost=product.cost_price,
                    unit_price=item.sale_price,
                    quantity=item.quantity,
                    subtotal=item.subtotal
                )
                session.add(invoice_item)

            session.commit()
            session.refresh(invoice)

            # Garantizar carga en memoria de relaciones antes de cerrar la sesión
            if invoice.customer:
                _ = invoice.customer.name
            for itm in invoice.items:
                _ = itm.product_name

            # Limpiar borrador tras venta exitosa
            self.clear_draft()
            return True, f"Venta registrada exitosamente con factura #{invoice.invoice_number}", invoice

    # ================= ESTRUCTURA PARA FUTURA IA (VOZ) =================

    def create_invoice_from_ai(
        self,
        json_data: dict | str,
        auto_checkout: bool = False
    ) -> Dict[str, Any]:
        """
        Endpoint desacoplado de la interfaz gráfica diseñado para integración
        con IA de procesamiento de lenguaje natural / voz.

        Estructura esperada de `json_data`:
        {
            "customer_id": 1,                      # Opcional (o nulo)
            "payment_type": "CASH" | "CREDIT",     # Opcional, default "CASH"
            "credit_notes": "Pedido por voz...",    # Opcional
            "items": [
                {"barcode": "7701001001", "quantity": 2},
                {"name": "Leche Entera 1L", "quantity": 1}   # Fallback por nombre si no hay código
            ]
        }

        Si `auto_checkout` es True: Liquida y guarda la factura de inmediato.
        Si `auto_checkout` es False: Carga los ítems al borrador del POS para que el
        cajero humano los vea y confirme en pantalla sin alterar la UI.
        """
        # 1. Parseo seguro de JSON
        try:
            if isinstance(json_data, str):
                payload = json.loads(json_data)
            elif isinstance(json_data, dict):
                payload = json_data
            else:
                return {"success": False, "error": "Formato de datos no válido. Se espera dict o JSON string."}
        except Exception as e:
            return {"success": False, "error": f"Error parseando JSON: {str(e)}"}

        # 2. Configurar cliente y método de pago
        customer_id = payload.get("customer_id")
        payment_type = payload.get("payment_type", "CASH").upper()
        credit_notes = payload.get("credit_notes", "")
        raw_items = payload.get("items", [])

        if not raw_items:
            return {"success": False, "error": "El arreglo 'items' no puede estar vacío."}

        # 3. Limpiar o mantener el borrador según se desee
        self.clear_draft()
        self.set_customer(customer_id)
        self.set_payment_options(payment_type, credit_notes)

        # 4. Procesar y resolver cada ítem en la base de datos
        processed_items = []
        errors = []

        with get_db_session() as session:
            for item_spec in raw_items:
                barcode = item_spec.get("barcode")
                name_query = item_spec.get("name")
                qty = int(item_spec.get("quantity", 1))

                product: Optional[Product] = None
                if barcode:
                    product = session.query(Product).filter(
                        Product.barcode == str(barcode).strip(),
                        Product.is_active == True
                    ).first()

                if not product and name_query:
                    # Búsqueda difusa/aproximada por nombre
                    product = session.query(Product).filter(
                        Product.name.ilike(f"%{name_query.strip()}%"),
                        Product.is_active == True
                    ).first()

                if not product:
                    errors.append(f"No se encontró producto con barcode='{barcode}' ni nombre='{name_query}'")
                    continue

                if product.stock < qty:
                    errors.append(f"Stock insuficiente para '{product.name}'. Solicitado: {qty}, Stock: {product.stock}")
                    continue

                # Añadir al borrador del POS
                self.items[product.barcode] = CartItem(
                    product_id=product.id,
                    barcode=product.barcode,
                    name=product.name,
                    presentacion=product.presentacion or "",
                    cost_price=product.cost_price,
                    sale_price=product.sale_price,
                    quantity=qty,
                    max_stock=product.stock
                )
                processed_items.append({
                    "barcode": product.barcode,
                    "name": product.display_name,
                    "presentacion": product.presentacion or "",
                    "quantity": qty,
                    "subtotal": round(product.sale_price * qty, 2)
                })

        # Notificar a la vista POS para refrescar pantalla si el usuario está viéndola
        self._notify_change()

        # Si no hubo ítems válidos
        if not self.items:
            return {
                "success": False,
                "error": "No se pudo agregar ningún producto al borrador.",
                "details": errors
            }

        # 5. Ejecutar checkout automático si se solicitó
        if auto_checkout:
            success, msg, invoice = self.checkout(created_via="AI_VOICE")
            if not success:
                return {"success": False, "error": msg, "details": errors}
            return {
                "success": True,
                "status": "CHECKOUT_COMPLETED",
                "message": msg,
                "invoice_number": invoice.invoice_number,
                "total": invoice.total,
                "items_processed": processed_items,
                "warnings": errors
            }

        # Si no fue auto-checkout, el borrador queda listo en el POS de la UI
        return {
            "success": True,
            "status": "DRAFT_LOADED_IN_POS",
            "message": "Borrador cargado exitosamente en el Punto de Venta para confirmación.",
            "draft_subtotal": self.subtotal,
            "draft_total": self.total,
            "items_count": self.total_items_count,
            "items_processed": processed_items,
            "warnings": errors
        }
