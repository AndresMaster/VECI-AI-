import calendar
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, List, Optional, Tuple, Callable

from database import get_db_session
from models import (
    Product,
    Invoice,
    InvoiceItem,
    Supplier,
    SupplierPurchase,
    GastosGenerales,
)


class DateFilterPreset:
    TODAY = "TODAY"
    LAST_7_DAYS = "LAST_7_DAYS"
    LAST_30_DAYS = "LAST_30_DAYS"
    SPECIFIC_MONTH = "SPECIFIC_MONTH"
    SPECIFIC_YEAR = "SPECIFIC_YEAR"
    ALL_TIME = "ALL_TIME"
    CUSTOM = "CUSTOM"


SPANISH_MONTHS = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


class DashboardController:
    """
    Controlador analítico y financiero con soporte de filtrado temporal avanzado
    (estilo YouTube Studio / Google Calendar) y Libro Mayor unificado (Flujo de Caja).
    """

    def __init__(self):
        now = datetime.now()
        # Estado compartido del filtro temporal entre Dashboard y Libro Mayor
        self.current_preset: str = DateFilterPreset.ALL_TIME
        self.selected_year: int = now.year
        self.selected_month: int = now.month
        self.custom_start_date: date = (now - timedelta(days=7)).date()
        self.custom_end_date: date = now.date()

        self._filter_listeners: List[Callable[[], None]] = []

    # ================= SUSCRIPCIÓN REACTIVA DEL FILTRO TEMPORAL =================

    def subscribe_filter_change(self, callback: Callable[[], None]) -> None:
        if callback not in self._filter_listeners:
            self._filter_listeners.append(callback)

    def notify_filter_change(self) -> None:
        for cb in list(self._filter_listeners):
            try:
                cb()
            except Exception as e:
                print(f"[DashboardController] Error notificando listener: {e}")

    # ================= CÁLCULO DE RANGOS DE FECHAS =================

    def get_active_date_range(self) -> Tuple[Optional[datetime], Optional[datetime], str]:
        """
        Retorna (start_date, end_date, human_label) según el preajuste temporal activo.
        """
        return self.resolve_date_range(
            preset=self.current_preset,
            year=self.selected_year,
            month=self.selected_month,
            custom_start=self.custom_start_date,
            custom_end=self.custom_end_date,
        )

    @staticmethod
    def resolve_date_range(
        preset: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
        custom_start: Optional[date] = None,
        custom_end: Optional[date] = None,
    ) -> Tuple[Optional[datetime], Optional[datetime], str]:
        """
        Calcula (start_datetime, end_datetime, label) exactos al segundo para el filtro seleccionado.
        """
        now = datetime.now()
        today = now.date()

        if preset == DateFilterPreset.TODAY:
            start = datetime.combine(today, time.min)
            end = datetime.combine(today, time.max)
            label = f"Hoy ({today.strftime('%d/%m/%Y')})"
            return start, end, label

        if preset == DateFilterPreset.LAST_7_DAYS:
            start_day = today - timedelta(days=6)
            start = datetime.combine(start_day, time.min)
            end = datetime.combine(today, time.max)
            label = f"Últimos 7 días ({start_day.strftime('%d/%m/%Y')} - {today.strftime('%d/%m/%Y')})"
            return start, end, label

        if preset == DateFilterPreset.LAST_30_DAYS:
            start_day = today - timedelta(days=29)
            start = datetime.combine(start_day, time.min)
            end = datetime.combine(today, time.max)
            label = f"Últimos 30 días ({start_day.strftime('%d/%m/%Y')} - {today.strftime('%d/%m/%Y')})"
            return start, end, label

        if preset == DateFilterPreset.SPECIFIC_MONTH:
            y = year or today.year
            m = month or today.month
            last_day = calendar.monthrange(y, m)[1]
            start = datetime(y, m, 1, 0, 0, 0)
            end = datetime(y, m, last_day, 23, 59, 59, 999999)
            month_name = SPANISH_MONTHS.get(m, str(m))
            label = f"{month_name} {y} (01/{m:02d}/{y} - {last_day:02d}/{m:02d}/{y})"
            return start, end, label

        if preset == DateFilterPreset.SPECIFIC_YEAR:
            y = year or today.year
            start = datetime(y, 1, 1, 0, 0, 0)
            end = datetime(y, 12, 31, 23, 59, 59, 999999)
            label = f"Año {y} (01/01/{y} - 31/12/{y})"
            return start, end, label

        if preset == DateFilterPreset.CUSTOM:
            s_date = custom_start or (today - timedelta(days=7))
            e_date = custom_end or today
            if s_date > e_date:
                s_date, e_date = e_date, s_date
            start = datetime.combine(s_date, time.min)
            end = datetime.combine(e_date, time.max)
            label = f"Personalizado ({s_date.strftime('%d/%m/%Y')} - {e_date.strftime('%d/%m/%Y')})"
            return start, end, label

        # Por defecto: ALL_TIME (Desde el inicio)
        return None, None, "Desde el inicio (Todo el historial)"

    def set_filter_preset(
        self,
        preset: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
        custom_start: Optional[date] = None,
        custom_end: Optional[date] = None,
        notify: bool = True,
    ) -> Tuple[Optional[datetime], Optional[datetime], str]:
        self.current_preset = preset
        if year is not None:
            self.selected_year = int(year)
        if month is not None:
            self.selected_month = int(month)
        if custom_start is not None:
            self.custom_start_date = custom_start
        if custom_end is not None:
            self.custom_end_date = custom_end

        if notify:
            self.notify_filter_change()

        return self.get_active_date_range()

    # ================= MÉTRICAS Y GRÁFICAS DINÁMICAS DEL DASHBOARD =================

    def get_kpis(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_active_filter_if_none: bool = True,
    ) -> Dict[str, Any]:
        """
        Recalcula dinámicamente TODAS las métricas y gráficas (Costos, Ventas Proyectadas,
        Ventas Realizadas, Egresos, Utilidad Real y Distribución por Categorías)
        basándose únicamente en el rango (start_date, end_date).
        """
        period_label = "Desde el inicio (Todo el historial)"
        if start_date is None and end_date is None and use_active_filter_if_none:
            start_date, end_date, period_label = self.get_active_date_range()
        elif start_date is not None or end_date is not None:
            s_txt = start_date.strftime("%d/%m/%Y") if start_date else "Inicio"
            e_txt = end_date.strftime("%d/%m/%Y") if end_date else "Hoy"
            period_label = f"{s_txt} — {e_txt}"

        is_all_time = (start_date is None and end_date is None)

        with get_db_session() as session:
            # 1. Productos activos y valoración base de bodega
            products = session.query(Product).filter(Product.is_active == True).all()
            total_inventory_cost = sum(p.total_cost_value for p in products)
            total_inventory_retail = sum(p.total_retail_value for p in products)
            total_potential_profit = total_inventory_retail - total_inventory_cost
            low_stock_products = [p.to_dict() for p in products if p.is_low_stock]

            # Factor promedio de margen comercial de la tienda para proyectar compras del periodo
            avg_markup_factor = (
                (total_inventory_retail / total_inventory_cost)
                if total_inventory_cost > 0 else 1.38
            )

            # Mapa rápido de product_id -> categoría
            product_category_map: Dict[int, str] = {
                p.id: (p.category or "General") for p in products
            }

            # 2. Facturas / Ventas filtradas por el rango DateTime
            inv_query = session.query(Invoice).filter(Invoice.payment_status != "CANCELLED")
            if start_date is not None:
                inv_query = inv_query.filter(Invoice.created_at >= start_date)
            if end_date is not None:
                inv_query = inv_query.filter(Invoice.created_at <= end_date)
            invoices = inv_query.all()

            realized_sales = sum(inv.total for inv in invoices)
            sales_cogs = sum(inv.total_cost for inv in invoices)
            gross_sales_profit = realized_sales - sales_cogs

            pending_credits = sum(
                inv.balance_due for inv in invoices
                if inv.payment_type == "CREDIT" and inv.payment_status == "PENDING"
            )

            # 3. Compras / Pagos a Proveedores filtrados por DateTime
            sp_query = session.query(SupplierPurchase)
            if start_date is not None:
                sp_query = sp_query.filter(SupplierPurchase.fecha_hora >= start_date)
            if end_date is not None:
                sp_query = sp_query.filter(SupplierPurchase.fecha_hora <= end_date)
            supplier_purchases = sp_query.all()
            supplier_expenses = sum(sp.monto for sp in supplier_purchases)

            # 4. Gastos Generales filtrados por DateTime
            exp_query = session.query(GastosGenerales)
            if start_date is not None:
                exp_query = exp_query.filter(GastosGenerales.fecha_hora >= start_date)
            if end_date is not None:
                exp_query = exp_query.filter(GastosGenerales.fecha_hora <= end_date)
            general_expenses_list = exp_query.all()
            general_expenses = sum(g.monto for g in general_expenses_list)

            # 5. Productos registrados/actualizados dentro del periodo
            if is_all_time:
                period_products = products
            else:
                prod_period_q = session.query(Product).filter(Product.is_active == True)
                if start_date is not None:
                    prod_period_q = prod_period_q.filter(Product.updated_at >= start_date)
                if end_date is not None:
                    prod_period_q = prod_period_q.filter(Product.updated_at <= end_date)
                period_products = prod_period_q.all()

            period_products_cost = sum(p.total_cost_value for p in period_products)
            period_products_retail = sum(p.total_retail_value for p in period_products)

            # 6. Cálculo consolidado del periodo para KPIs y Gráficas
            # Costos Totales del Periodo:
            # - Costo de lo vendido (COGS) + Compras a proveedores + Gastos generales
            # (En All-Time incluye además el capital en bodega actual)
            total_operational_outflows = supplier_expenses + general_expenses
            if is_all_time:
                period_cost = total_inventory_cost + total_operational_outflows + sales_cogs
                period_projected_sales = total_inventory_retail + realized_sales
            else:
                period_cost = sales_cogs + supplier_expenses + general_expenses + period_products_cost
                projected_from_purchases = round(supplier_expenses * avg_markup_factor, 2)
                period_projected_sales = realized_sales + max(projected_from_purchases, period_products_retail)

            # Utilidad Real Neta del periodo:
            # Utilidad bruta de las ventas realizadas menos los gastos generales del periodo
            real_net_profit = gross_sales_profit - general_expenses
            # Flujo neto de caja del periodo (Ingresos por ventas - Pagos a proveedores - Gastos generales)
            net_cash_flow = realized_sales - supplier_expenses - general_expenses
            # Utilidad proyectada del periodo
            period_potential_profit = period_projected_sales - period_cost

            # 7. Distribución dinámica por categorías para el Gráfico de Torta del periodo
            categories_data: Dict[str, float] = {}

            # Aportación de las ventas del periodo por categoría de producto
            for inv in invoices:
                for item in inv.items:
                    cat = product_category_map.get(item.product_id, "Ventas Generales") if item.product_id else "Ventas POS"
                    categories_data[cat] = categories_data.get(cat, 0.0) + float(item.subtotal or 0.0)

            # Aportación de los gastos generales del periodo por categoría
            for exp in general_expenses_list:
                cat_key = f"Gasto: {exp.categoria}"
                categories_data[cat_key] = categories_data.get(cat_key, 0.0) + float(exp.monto or 0.0)

            # Aportación de compras a proveedores del periodo
            if supplier_expenses > 0:
                categories_data["Compras Proveedores"] = (
                    categories_data.get("Compras Proveedores", 0.0) + float(supplier_expenses)
                )

            # Si estamos en All-Time (o si aún no hay transacciones pero sí productos creados en el periodo),
            # complementar con la valoración por categoría de productos del periodo
            if is_all_time or not categories_data:
                for p in period_products:
                    cat = p.category or "Otros"
                    categories_data[cat] = categories_data.get(cat, 0.0) + p.total_retail_value

            return {
                "period_label": period_label,
                "is_all_time": is_all_time,
                # Métricas dinámicas del periodo
                "period_cost": round(period_cost, 2),
                "period_projected_sales": round(period_projected_sales, 2),
                "period_potential_profit": round(period_potential_profit, 2),
                "total_realized_sales": round(realized_sales, 2),
                "sales_cogs": round(sales_cogs, 2),
                "gross_sales_profit": round(gross_sales_profit, 2),
                "supplier_expenses": round(supplier_expenses, 2),
                "general_expenses": round(general_expenses, 2),
                "total_outflows": round(total_operational_outflows, 2),
                "total_realized_profit": round(real_net_profit, 2),
                "net_cash_flow": round(net_cash_flow, 2),
                "pending_credits": round(pending_credits, 2),
                # Métricas de inventario físico en bodega (compatibilidad y alertas)
                "total_inventory_cost": round(total_inventory_cost, 2),
                "total_inventory_retail": round(total_inventory_retail, 2),
                "total_potential_profit": round(total_potential_profit, 2),
                "low_stock_count": len(low_stock_products),
                "low_stock_items": low_stock_products,
                "categories_distribution": categories_data,
                "total_products_count": len(products),
                "total_invoices_count": len(invoices),
                "total_purchases_count": len(supplier_purchases),
                "total_expenses_count": len(general_expenses_list),
            }

    # ================= LIBRO MAYOR UNIFICADO (FLUJO DE CAJA / TRANSACCIONES) =================

    def get_ledger_transactions(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        type_filter: str = "ALL",
        search_query: str = "",
        use_active_filter_if_none: bool = True,
        descending: bool = True,
    ) -> Dict[str, Any]:
        """
        Consolida y ordena cronológicamente por Fecha y Hora exacta:
        1. Ventas realizadas (Ingresos).
        2. Pagos a proveedores (Egresos de inventario).
        3. Gastos generales (Egresos fijos/variables como recibos de luz).
        """
        period_label = "Desde el inicio (Todo el historial)"
        if start_date is None and end_date is None and use_active_filter_if_none:
            start_date, end_date, period_label = self.get_active_date_range()
        elif start_date is not None or end_date is not None:
            s_txt = start_date.strftime("%d/%m/%Y") if start_date else "Inicio"
            e_txt = end_date.strftime("%d/%m/%Y") if end_date else "Hoy"
            period_label = f"{s_txt} — {e_txt}"

        unified_rows: List[Dict[str, Any]] = []
        total_ingresos = 0.0
        total_pagos_proveedores = 0.0
        total_gastos_generales = 0.0

        with get_db_session() as session:
            # 1. Ventas realizadas (Ingresos)
            if type_filter in ("ALL", "VENTA"):
                inv_q = session.query(Invoice).filter(Invoice.payment_status != "CANCELLED")
                if start_date is not None:
                    inv_q = inv_q.filter(Invoice.created_at >= start_date)
                if end_date is not None:
                    inv_q = inv_q.filter(Invoice.created_at <= end_date)

                for inv in inv_q.all():
                    dt = inv.created_at or datetime.now()
                    customer_name = inv.customer.name if inv.customer else "Consumidor Final"
                    items_qty = sum(i.quantity for i in inv.items)
                    pay_badge = "Crédito" if inv.payment_type == "CREDIT" else "Contado"
                    desc = f"Factura #{inv.invoice_number} — {customer_name} ({items_qty} uds, {pay_badge})"
                    amount = round(float(inv.total or 0.0), 2)
                    total_ingresos += amount

                    unified_rows.append({
                        "uid": f"INV-{inv.id}",
                        "source_id": inv.id,
                        "source_type": "VENTA",
                        "tipo": "Venta",
                        "timestamp": dt,
                        "fecha": dt.strftime("%Y-%m-%d"),
                        "hora": dt.strftime("%H:%M:%S"),
                        "descripcion": desc,
                        "monto": amount,
                        "is_income": True,
                    })

            # 2. Pagos a proveedores (Egresos de inventario)
            if type_filter in ("ALL", "PROVEEDOR"):
                sp_q = session.query(SupplierPurchase)
                if start_date is not None:
                    sp_q = sp_q.filter(SupplierPurchase.fecha_hora >= start_date)
                if end_date is not None:
                    sp_q = sp_q.filter(SupplierPurchase.fecha_hora <= end_date)

                for sp in sp_q.all():
                    dt = sp.fecha_hora or datetime.now()
                    sup_name = sp.supplier.name if sp.supplier else "Proveedor General"
                    ref_txt = f" [Ref: {sp.invoice_reference}]" if sp.invoice_reference else ""
                    desc = f"{sup_name} — {sp.descripcion}{ref_txt}"
                    amount = round(float(sp.monto or 0.0), 2)
                    total_pagos_proveedores += amount

                    unified_rows.append({
                        "uid": f"SUP-{sp.id}",
                        "source_id": sp.id,
                        "source_type": "PROVEEDOR",
                        "tipo": "Pago Proveedor",
                        "timestamp": dt,
                        "fecha": dt.strftime("%Y-%m-%d"),
                        "hora": dt.strftime("%H:%M:%S"),
                        "descripcion": desc,
                        "monto": amount,
                        "is_income": False,
                    })

            # 3. Gastos Generales (Egresos fijos/variables)
            if type_filter in ("ALL", "GASTO"):
                exp_q = session.query(GastosGenerales)
                if start_date is not None:
                    exp_q = exp_q.filter(GastosGenerales.fecha_hora >= start_date)
                if end_date is not None:
                    exp_q = exp_q.filter(GastosGenerales.fecha_hora <= end_date)

                for g in exp_q.all():
                    dt = g.fecha_hora or datetime.now()
                    desc = f"[{g.categoria}] {g.descripcion}"
                    amount = round(float(g.monto or 0.0), 2)
                    total_gastos_generales += amount

                    unified_rows.append({
                        "uid": f"EXP-{g.id}",
                        "source_id": g.id,
                        "source_type": "GASTO",
                        "tipo": "Gasto General",
                        "timestamp": dt,
                        "fecha": dt.strftime("%Y-%m-%d"),
                        "hora": dt.strftime("%H:%M:%S"),
                        "descripcion": desc,
                        "monto": amount,
                        "is_income": False,
                    })

        # Filtro de búsqueda por texto en descripción, tipo o fecha
        if search_query and search_query.strip():
            term = search_query.strip().lower()
            unified_rows = [
                r for r in unified_rows
                if term in r["descripcion"].lower()
                or term in r["tipo"].lower()
                or term in r["fecha"].lower()
            ]
            # Recalcular subtotales sobre los resultados filtrados por búsqueda
            total_ingresos = sum(r["monto"] for r in unified_rows if r["source_type"] == "VENTA")
            total_pagos_proveedores = sum(r["monto"] for r in unified_rows if r["source_type"] == "PROVEEDOR")
            total_gastos_generales = sum(r["monto"] for r in unified_rows if r["source_type"] == "GASTO")

        # Ordenamiento cronológico exacto por Fecha y Hora (DateTime)
        unified_rows.sort(key=lambda r: r["timestamp"], reverse=descending)

        total_egresos = total_pagos_proveedores + total_gastos_generales
        balance_neto = total_ingresos - total_egresos

        return {
            "period_label": period_label,
            "transactions": unified_rows,
            "count": len(unified_rows),
            "total_ingresos": round(total_ingresos, 2),
            "total_pagos_proveedores": round(total_pagos_proveedores, 2),
            "total_gastos_generales": round(total_gastos_generales, 2),
            "total_egresos": round(total_egresos, 2),
            "balance_neto": round(balance_neto, 2),
        }

    # ================= REGISTRO DE GASTOS GENERALES Y PAGOS A PROVEEDORES =================

    def create_general_expense(
        self,
        categoria: str,
        descripcion: str,
        monto: float,
        fecha_hora: Optional[datetime] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Registra un nuevo Gasto General en la base de datos con Fecha y Hora exacta."""
        if not descripcion or not descripcion.strip():
            return False, "La descripción del gasto es obligatoria.", None
        if monto <= 0:
            return False, "El monto del gasto debe ser mayor a cero.", None

        with get_db_session() as session:
            expense = GastosGenerales(
                fecha_hora=fecha_hora or datetime.now(),
                categoria=(categoria or "Varios").strip(),
                descripcion=descripcion.strip(),
                monto=round(float(monto), 2),
            )
            session.add(expense)
            session.commit()
            session.refresh(expense)
            data = expense.to_dict()

        self.notify_filter_change()
        return True, f"Gasto general registrado (${monto:,.0f}).", data

    def delete_general_expense(self, expense_id: int) -> Tuple[bool, str]:
        with get_db_session() as session:
            exp = session.query(GastosGenerales).filter_by(id=expense_id).first()
            if not exp:
                return False, "Gasto no encontrado."
            session.delete(exp)
            session.commit()

        self.notify_filter_change()
        return True, "Gasto general eliminado."

    def create_supplier_purchase(
        self,
        supplier_id: Optional[int],
        descripcion: str,
        monto: float,
        invoice_reference: str = "",
        payment_method: str = "CASH",
        fecha_hora: Optional[datetime] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Registra un Pago / Compra a Proveedor con Fecha y Hora exacta."""
        if not descripcion or not descripcion.strip():
            return False, "La descripción de la compra/pago es obligatoria.", None
        if monto <= 0:
            return False, "El monto del pago a proveedor debe ser mayor a cero.", None

        with get_db_session() as session:
            purchase = SupplierPurchase(
                supplier_id=supplier_id,
                fecha_hora=fecha_hora or datetime.now(),
                invoice_reference=invoice_reference.strip() if invoice_reference else None,
                descripcion=descripcion.strip(),
                monto=round(float(monto), 2),
                payment_method=payment_method or "CASH",
            )
            session.add(purchase)
            session.commit()
            session.refresh(purchase)
            if purchase.supplier:
                _ = purchase.supplier.name
            data = purchase.to_dict()

        self.notify_filter_change()
        return True, f"Pago a proveedor registrado (${monto:,.0f}).", data

    def delete_supplier_purchase(self, purchase_id: int) -> Tuple[bool, str]:
        with get_db_session() as session:
            sp = session.query(SupplierPurchase).filter_by(id=purchase_id).first()
            if not sp:
                return False, "Registro de pago a proveedor no encontrado."
            session.delete(sp)
            session.commit()

        self.notify_filter_change()
        return True, "Pago a proveedor eliminado."

    def get_active_suppliers_list(self, search_query: str = "") -> List[Dict[str, Any]]:
        with get_db_session() as session:
            query = session.query(Supplier).filter(Supplier.is_active == True)
            if search_query and search_query.strip():
                term = f"%{search_query.strip()}%"
                query = query.filter(
                    Supplier.name.ilike(term)
                    | Supplier.contact_name.ilike(term)
                    | Supplier.phone.ilike(term)
                )
            suppliers = query.order_by(Supplier.name.asc()).all()
            return [s.to_dict() for s in suppliers]
