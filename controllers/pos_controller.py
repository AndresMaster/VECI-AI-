import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from sqlalchemy import or_, select, case

from database import get_db_session, ensure_wildcard_product
from models import (
    Product,
    WILDCARD_PRODUCT_BARCODE,
    WILDCARD_PRODUCT_NAME,
    Customer,
    Invoice,
    InvoiceItem,
    RegistroAnulaciones,
)

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
    original_sale_price: float = 0.0
    stock_infinito: bool = False
    is_wildcard: bool = False

    def __post_init__(self) -> None:
        if self.original_sale_price <= 0:
            self.original_sale_price = float(self.sale_price)

    @property
    def is_promo_price(self) -> bool:
        """Indica si el precio unitario fue sobrescrito manualmente para esta venta."""
        return abs(float(self.sale_price) - float(self.original_sale_price)) > 0.009

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


@dataclass
class PosTabSession:
    """
    Sesión independiente de facturación (Pestaña / Tab de venta paralela).
    Mantiene su propio carrito, cliente asignado, modalidad de pago, notas y efectivo recibido.
    """
    tab_id: int
    title: str
    items: Dict[str, CartItem] = field(default_factory=dict)
    customer_id: Optional[int] = None
    payment_type: str = "CASH"
    credit_notes: str = ""
    discount: float = 0.0
    cash_received_str: str = ""

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


class PosController:
    """
    Controlador de Punto de Venta (POS / Facturación).
    Mantiene el estado persistente de múltiples pestañas/borradores (tabs) en paralelo
    para no perder ninguna venta en curso al cambiar de cliente o navegar hacia Inventario,
    y expone la API `create_invoice_from_ai` para futuras integraciones de voz.
    """
    def __init__(self):
        # Suscriptores para reactividad en la UI de Flet
        self._change_listeners: List[Callable[[], None]] = []

        # Variable de estado para Prevención de Doble Escaneo (Scanner Cooldown de 1.0s)
        self.ultimo_tiempo_escaneo: float = 0.0

        # Sistema de Facturación Múltiple (Pestañas / Sesiones concurrentes)
        self._next_tab_number: int = 1
        self._wildcard_seq: int = 1
        self.tabs: List[PosTabSession] = []
        self.active_tab_id: int = 0
        self.create_new_tab(notify=False)

    # ================= GESTIÓN DE PESTAÑAS (MÚLTIPLES VENTAS EN PARALELO) =================

    @property
    def active_tab(self) -> PosTabSession:
        """Retorna la sesión/pestaña de venta actualmente activa."""
        if not self.tabs:
            self.create_new_tab(notify=False)
        for tab in self.tabs:
            if tab.tab_id == self.active_tab_id:
                return tab
        self.active_tab_id = self.tabs[0].tab_id
        return self.tabs[0]

    def create_new_tab(self, notify: bool = True) -> PosTabSession:
        """Crea una nueva pestaña de venta en blanco (ej. Venta 1, Venta 2) y la activa."""
        tab_num = self._next_tab_number
        self._next_tab_number += 1
        new_tab = PosTabSession(
            tab_id=tab_num,
            title=f"Venta {tab_num}",
        )
        self.tabs.append(new_tab)
        self.active_tab_id = new_tab.tab_id
        if notify:
            self._notify_change()
        return new_tab

    def switch_tab(self, tab_id: int) -> bool:
        """Cambia la pestaña activa conservando intacto el estado de las demás pestañas."""
        for tab in self.tabs:
            if tab.tab_id == tab_id:
                self.active_tab_id = tab_id
                self._notify_change()
                return True
        return False

    def close_tab(self, tab_id: int) -> None:
        """
        Cierra una pestaña de venta. Si es la única pestaña abierta, limpia su borrador
        para mantener siempre al menos una sesión activa disponible.
        """
        if len(self.tabs) <= 1:
            self.clear_draft()
            return

        idx_to_remove = None
        for idx, tab in enumerate(self.tabs):
            if tab.tab_id == tab_id:
                idx_to_remove = idx
                break

        if idx_to_remove is None:
            return

        was_active = (self.active_tab_id == tab_id)
        self.tabs.pop(idx_to_remove)

        if was_active and self.tabs:
            new_idx = min(idx_to_remove, len(self.tabs) - 1)
            self.active_tab_id = self.tabs[new_idx].tab_id

        self._notify_change()

    # ================= PROPIEDADES DELEGADAS A LA PESTAÑA ACTIVA =================

    @property
    def items(self) -> Dict[str, CartItem]:
        return self.active_tab.items

    @items.setter
    def items(self, value: Dict[str, CartItem]) -> None:
        self.active_tab.items = value

    @property
    def customer_id(self) -> Optional[int]:
        return self.active_tab.customer_id

    @customer_id.setter
    def customer_id(self, value: Optional[int]) -> None:
        self.active_tab.customer_id = value

    @property
    def payment_type(self) -> str:
        return self.active_tab.payment_type

    @payment_type.setter
    def payment_type(self, value: str) -> None:
        self.active_tab.payment_type = value

    @property
    def credit_notes(self) -> str:
        return self.active_tab.credit_notes

    @credit_notes.setter
    def credit_notes(self, value: str) -> None:
        self.active_tab.credit_notes = value

    @property
    def discount(self) -> float:
        return self.active_tab.discount

    @discount.setter
    def discount(self, value: float) -> None:
        self.active_tab.discount = value

    @property
    def cash_received_str(self) -> str:
        return self.active_tab.cash_received_str

    @cash_received_str.setter
    def cash_received_str(self, value: str) -> None:
        self.active_tab.cash_received_str = value

    @staticmethod
    def parse_currency_input(raw_str: str) -> float:
        """Convierte cadenas numéricas de entrada en un valor flotante seguro."""
        cleaned = (raw_str or "").strip().replace("$", "").replace(" ", "").replace(",", "")
        if not cleaned:
            return 0.0
        try:
            return max(0.0, float(cleaned))
        except ValueError:
            return 0.0

    @property
    def cash_received_amount(self) -> float:
        return self.parse_currency_input(self.active_tab.cash_received_str)

    @property
    def change_due(self) -> float:
        """Vueltas = Efectivo Recibido - Total Factura."""
        return round(self.cash_received_amount - self.total, 2)

    def set_cash_received(self, raw_value: str, notify: bool = False) -> tuple[float, float]:
        """Actualiza el efectivo recibido en la pestaña activa y retorna (efectivo, vueltas)."""
        self.active_tab.cash_received_str = raw_value or ""
        if notify:
            self._notify_change()
        return self.cash_received_amount, self.change_due

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

    # ================= CÁLCULOS DEL BORRADOR ACTIVO =================

    @property
    def subtotal(self) -> float:
        return self.active_tab.subtotal

    @property
    def total(self) -> float:
        return self.active_tab.total

    @property
    def total_items_count(self) -> int:
        return self.active_tab.total_items_count

    @property
    def total_estimated_profit(self) -> float:
        return self.active_tab.total_estimated_profit

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
        prefix_pattern = f"{term}%"
        with get_db_session() as session:
            matches = (
                session.query(Product)
                .filter(
                    Product.is_active == True,
                    Product.barcode != WILDCARD_PRODUCT_BARCODE,
                    or_(
                        Product.name.ilike(like_pattern),
                        Product.presentacion.ilike(like_pattern),
                        Product.barcode.ilike(like_pattern),
                    ),
                )
                .order_by(
                    case((Product.name.ilike(prefix_pattern), 0), else_=1),
                    Product.name.asc(),
                    Product.presentacion.asc(),
                )
                .limit(limit)
                .all()
            )
            return [p.to_dict() for p in matches]

    # ================= GESTIÓN DEL CARRITO (BORRADOR) =================

    def add_wildcard_item_to_invoice(
        self,
        description: str = "",
        sale_price: float = 0.0,
        unit_cost: Optional[float] = None,
        quantity: int = 1,
    ) -> tuple[bool, str, Optional[CartItem]]:
        """
        Agrega un artículo de 'Venta Libre' (Comodín / Open Ring) al borrador activo:
        1. Descripción opcional (por defecto 'Artículo Venta Libre').
        2. Precio de Venta requerido (> 0).
        3. Costo Unitario opcional: si es None, aplica la regla matemática de fallback
           Costo = Precio de Venta / 1.2; si el usuario digitó el costo manualmente, lo respeta.
        4. Usa el único Producto de sistema 'Comodín / Venta Libre' (stock_infinito = True)
           en la base de datos y sobrescribe nombre, precio y costo en la línea del carrito/factura.
        """
        clean_desc = (description or "").strip() or "Artículo Venta Libre"
        try:
            s_price = round(float(sale_price), 2)
        except (TypeError, ValueError):
            return False, "El Precio de Venta debe ser un valor numérico válido.", None

        if s_price <= 0:
            return False, "El Precio de Venta debe ser mayor a $0.", None

        if unit_cost is None:
            final_cost = round(s_price / 1.2, 2)
        else:
            try:
                final_cost = round(float(unit_cost), 2)
            except (TypeError, ValueError):
                return False, "El Costo Unitario debe ser un valor numérico válido.", None
            if final_cost < 0:
                return False, "El Costo Unitario no puede ser negativo.", None

        qty = max(1, int(quantity or 1))
        wildcard_prod = ensure_wildcard_product()

        # Si ya existe en el carrito activo una línea Venta Libre con igual descripción, precio y costo, sumar cantidad
        for existing_item in self.items.values():
            if (
                existing_item.is_wildcard
                and existing_item.name == clean_desc
                and abs(existing_item.sale_price - s_price) < 0.01
                and abs(existing_item.cost_price - final_cost) < 0.01
            ):
                existing_item.quantity += qty
                self._notify_change()
                return (
                    True,
                    f"Venta Libre agregada: {clean_desc} (${s_price:,.0f} | Costo: ${final_cost:,.0f})",
                    existing_item,
                )

        cart_key = f"{WILDCARD_PRODUCT_BARCODE}-{self._wildcard_seq}"
        self._wildcard_seq += 1

        new_item = CartItem(
            product_id=wildcard_prod.id,
            barcode=cart_key,
            name=clean_desc,
            presentacion="",
            cost_price=final_cost,
            sale_price=s_price,
            original_sale_price=s_price,
            quantity=qty,
            max_stock=0,
            stock_infinito=True,
            is_wildcard=True,
        )
        self.items[cart_key] = new_item
        self._notify_change()
        return (
            True,
            f"Venta Libre agregada: {clean_desc} (${s_price:,.0f} | Costo: ${final_cost:,.0f})",
            new_item,
        )

    def add_item_to_invoice(
        self,
        barcode_or_id: str | int,
        quantity: int = 1,
        apply_cooldown: bool = True,
    ) -> tuple[bool, str]:
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
            return self.add_product_by_barcode(barcode_str, quantity=quantity, apply_cooldown=apply_cooldown)
        return self.add_product_by_barcode(str(barcode_or_id), quantity=quantity, apply_cooldown=apply_cooldown)

    def add_product_by_barcode(
        self,
        barcode: str,
        quantity: int = 1,
        apply_cooldown: bool = True,
    ) -> tuple[bool, str]:
        """
        Agrega un producto al borrador buscando por código de barras.
        Incluye prevención de doble escaneo por rebote de hardware (Cooldown de 1.0 segundo)
        y valida disponibilidad de stock.
        """
        if apply_cooldown:
            if time.time() - self.ultimo_tiempo_escaneo < 1.0:
                return False, "Escaneo duplicado ignorado (bloqueo anti-rebote de 1s)."

        code = barcode.strip()
        with get_db_session() as session:
            product = session.query(Product).filter(
                Product.barcode == code, 
                Product.is_active == True
            ).first()

            # RESTRICCIÓN ESTRICTA: Consultar EXCLUSIVAMENTE base de datos local SQLite (sin llamadas a internet)
            if not product:
                return False, "Producto no encontrado. Regístrelo en el módulo de Inventario."

            is_infinite = bool(product.stock_infinito)
            current_qty = self.items[code].quantity if code in self.items else 0
            if (not is_infinite) and (current_qty + quantity > product.stock):
                return False, f"Stock insuficiente para '{product.display_name}'. Disponible: {product.stock}"

            if code in self.items:
                self.items[code].max_stock = product.stock
                self.items[code].stock_infinito = is_infinite
                self.items[code].quantity += quantity
            else:
                self.items[code] = CartItem(
                    product_id=product.id,
                    barcode=product.barcode,
                    name=product.name,
                    presentacion=product.presentacion or "",
                    cost_price=product.cost_price,
                    sale_price=product.sale_price,
                    original_sale_price=product.sale_price,
                    quantity=quantity,
                    max_stock=product.stock,
                    stock_infinito=is_infinite,
                )

        if apply_cooldown:
            self.ultimo_tiempo_escaneo = time.time()

        self._notify_change()
        return True, f"Agregado: {self.items[code].display_name}"

    def update_quantity(self, barcode: str, quantity: int, notify: bool = True) -> tuple[bool, str]:
        """Modifica la cantidad de un producto ya presente en el borrador activo."""
        if barcode not in self.items:
            return False, "El producto no está en el borrador."

        if quantity <= 0:
            return self.remove_item(barcode)

        item = self.items[barcode]
        # Sincronizar stock disponible actual desde SQLite por si hubo ajustes en Inventario o In/Out
        with get_db_session() as session:
            prod = session.query(Product).filter_by(id=item.product_id).first()
            if prod is not None:
                item.max_stock = int(prod.stock or 0)
                item.stock_infinito = bool(prod.stock_infinito)

        if (not item.stock_infinito) and quantity > item.max_stock:
            if notify:
                self._notify_change()
            return False, f"No puedes superar el stock disponible ({item.max_stock} uds)."

        item.quantity = int(quantity)
        if notify:
            self._notify_change()
        return True, "Cantidad actualizada."

    def update_unit_price(self, barcode: str, new_price: float, notify: bool = True) -> tuple[bool, str]:
        """
        Sobrescribe manualmente el precio unitario de un ítem en el carrito activo (Modo Promoción).
        REGLA CRÍTICA: Este cambio SOLO afecta a CartItem.sale_price (y posteriormente a InvoiceItem.unit_price
        al facturar esta venta). BAJO NINGUNA CIRCUNSTANCIA modifica Product.sale_price en el Inventario general.
        """
        if barcode not in self.items:
            return False, "El producto no está en el borrador."

        if new_price < 0:
            if notify:
                self._notify_change()
            return False, "El precio unitario no puede ser negativo."

        item = self.items[barcode]
        item.sale_price = round(float(new_price), 2)
        if notify:
            self._notify_change()
        return True, f"Precio unitario ajustado a ${item.sale_price:,.0f} para esta venta."

    def remove_item(self, barcode: str) -> tuple[bool, str]:
        """Elimina un ítem del borrador."""
        if barcode in self.items:
            del self.items[barcode]
            self._notify_change()
            return True, "Producto retirado del borrador."
        return False, "Producto no encontrado en el carrito."

    def clear_draft(self) -> None:
        """Limpia todo el borrador de la pestaña activa."""
        self.items.clear()
        self.customer_id = None
        self.payment_type = "CASH"
        self.credit_notes = ""
        self.discount = 0.0
        self.cash_received_str = ""
        self._notify_change()

    def set_customer(self, customer_id: Optional[int]) -> None:
        self.customer_id = customer_id
        self._notify_change()

    def set_payment_options(self, payment_type: str, credit_notes: str = "") -> None:
        self.payment_type = payment_type.upper()
        self.credit_notes = credit_notes
        self._notify_change()

    # ================= PROCESO DE CHECKOUT / FACTURACIÓN =================

    @staticmethod
    def _generate_unique_invoice_number(session, now_dt: datetime) -> str:
        """
        Genera un número consecutivo de factura único (INV-YYYYMMDD-XXXX) a prueba de colisiones
        aun cuando se hayan eliminado/anulado facturas previas del mismo día.
        """
        date_prefix = now_dt.strftime("%Y%m%d")
        prefix_str = f"INV-{date_prefix}-"
        max_seq = 0

        existing_numbers = (
            session.query(Invoice.invoice_number)
            .filter(Invoice.invoice_number.like(f"{prefix_str}%"))
            .all()
        )
        for (inv_num,) in existing_numbers:
            if inv_num and inv_num.startswith(prefix_str):
                suffix = inv_num[len(prefix_str):].split()[0].strip()
                if suffix.isdigit():
                    max_seq = max(max_seq, int(suffix))

        cancelled_numbers = (
            session.query(RegistroAnulaciones.factura_id_original)
            .filter(RegistroAnulaciones.factura_id_original.like(f"{prefix_str}%"))
            .all()
        )
        for (orig_str,) in cancelled_numbers:
            if orig_str and orig_str.startswith(prefix_str):
                token = orig_str.split()[0].strip()
                suffix = token[len(prefix_str):].strip()
                if suffix.isdigit():
                    max_seq = max(max_seq, int(suffix))

        next_seq = max_seq + 1
        candidate = f"{prefix_str}{next_seq:04d}"
        while session.query(Invoice.id).filter(Invoice.invoice_number == candidate).first() is not None:
            next_seq += 1
            candidate = f"{prefix_str}{next_seq:04d}"
        return candidate

    def checkout(self, created_via: str = "POS_DESKTOP") -> tuple[bool, str, Optional[Invoice]]:
        """
        Consolida el borrador activo en una Factura definitiva en la base de datos:
        1. Valida que haya ítems.
        2. Si es crédito, valida que haya cliente asignado y que no supere límite si aplica.
        3. Descuenta inventario atómicamente (sin alterar jamás Product.sale_price).
        4. Crea la factura y sus renglones (InvoiceItems guardan el unit_price de esta venta).
        """
        if not self.items:
            return False, "El borrador de venta está vacío.", None

        if self.payment_type == "CREDIT" and not self.customer_id:
            return False, "Para facturas a crédito es obligatorio seleccionar un cliente.", None

        completed_tab_id = self.active_tab.tab_id

        with get_db_session() as session:
            # Validación de cliente asignado
            customer = None
            if self.customer_id:
                customer = session.query(Customer).filter_by(id=self.customer_id).first()
                if not customer:
                    return False, f"Cliente ID {self.customer_id} no existe.", None

            # Generar número consecutivo único de factura (a prueba de colisiones tras anulaciones)
            now_dt = datetime.now()
            invoice_num = self._generate_unique_invoice_number(session, now_dt)

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
                credit_notes=self.credit_notes.strip() if (self.credit_notes and self.credit_notes.strip()) else None,
                created_via=created_via
            )
            session.add(invoice)
            session.flush() # Obtiene invoice.id

            # Descontar stock (solo si stock_infinito == False) y registrar ítems históricos
            for item in self.items.values():
                product = session.query(Product).filter_by(id=item.product_id).with_for_update().first()
                if not product:
                    session.rollback()
                    return False, f"Producto '{item.name}' no encontrado en el inventario.", None

                if not bool(product.stock_infinito):
                    if product.stock < item.quantity:
                        session.rollback()
                        return False, f"Stock insuficiente en bodega para '{item.name}'.", None
                    product.stock -= item.quantity

                invoice_item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_id=product.id,
                    barcode=WILDCARD_PRODUCT_BARCODE if item.is_wildcard else product.barcode,
                    product_name=item.display_name,  # Snapshot exacto: Descripción de Venta Libre o nombre con presentación
                    presentacion="" if item.is_wildcard else (product.presentacion or ""),
                    unit_cost=round(float(item.cost_price), 2),   # Snapshot exacto: Costo calculado/digitado en Venta Libre o costo de inventario
                    unit_price=round(float(item.sale_price), 2),  # Snapshot exacto: Precio de venta definido en la factura
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

            # Limpiar o cerrar la pestaña liquidada tras venta exitosa
            if len(self.tabs) > 1:
                self.close_tab(completed_tab_id)
            else:
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

                is_infinite = bool(product.stock_infinito)
                if (not is_infinite) and product.stock < qty:
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
                    max_stock=product.stock,
                    stock_infinito=is_infinite,
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
