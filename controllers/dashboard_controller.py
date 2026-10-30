import calendar
import json
import math
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, List, Optional, Tuple, Callable
from sqlalchemy import func, case, literal, union_all
from sqlalchemy.orm import joinedload

from database import get_db_session, ensure_wildcard_product
from models import (
    Product,
    WILDCARD_PRODUCT_BARCODE,
    Customer,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    Supplier,
    SupplierPurchase,
    GastosGenerales,
    RegistroAnulaciones,
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
        low_stock_page: int = 1,
        low_stock_page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Recalcula dinámicamente TODAS las métricas y gráficas (Costos, Ventas Proyectadas,
        Ventas Realizadas, Egresos, Utilidad Real y Distribución por Categorías)
        basándose únicamente en el rango (start_date, end_date).
        Usa agregación SQL directa y paginación LIMIT 50 OFFSET X para evitar congelamientos con >900 productos.
        """
        period_label = "Desde el inicio (Todo el historial)"
        if start_date is None and end_date is None and use_active_filter_if_none:
            start_date, end_date, period_label = self.get_active_date_range()
        elif start_date is not None or end_date is not None:
            s_txt = start_date.strftime("%d/%m/%Y") if start_date else "Inicio"
            e_txt = end_date.strftime("%d/%m/%Y") if end_date else "Hoy"
            period_label = f"{s_txt} — {e_txt}"

        is_all_time = (start_date is None and end_date is None)
        low_stock_page_size = max(1, int(low_stock_page_size or 50))
        requested_ls_page = max(1, int(low_stock_page or 1))

        with get_db_session() as session:
            # 1. Valoración de inventario mediante agregación SQL directa (sin instanciar 900+ objetos ORM)
            # Los productos con stock_infinito=True no suman unidades físicas ni valoración de stock
            is_physical = (Product.stock_infinito == False) & (Product.stock > 0)
            inv_agg = (
                session.query(
                    func.count(Product.id),
                    func.coalesce(
                        func.sum(case((is_physical, Product.cost_price * Product.stock), else_=0.0)),
                        0.0,
                    ),
                    func.coalesce(
                        func.sum(case((is_physical, Product.sale_price * Product.stock), else_=0.0)),
                        0.0,
                    ),
                    func.coalesce(
                        func.sum(case((is_physical, Product.stock), else_=0)),
                        0,
                    ),
                )
                .filter(
                    Product.is_active == True,
                    Product.barcode != WILDCARD_PRODUCT_BARCODE,
                )
                .first()
            )
            total_products_count = int(inv_agg[0] or 0) if inv_agg else 0
            total_inventory_cost = float(inv_agg[1] or 0.0) if inv_agg else 0.0
            total_inventory_retail = float(inv_agg[2] or 0.0) if inv_agg else 0.0
            total_inventory_units = int(inv_agg[3] or 0) if inv_agg else 0
            total_potential_profit = total_inventory_retail - total_inventory_cost

            # 1.1 Alertas de Stock Bajo paginadas con LIMIT 50 OFFSET X en SQLite
            # Excluye productos con stock_infinito == True
            low_stock_q = session.query(Product).filter(
                Product.is_active == True,
                Product.stock_infinito == False,
                Product.stock <= Product.min_stock,
            )
            low_stock_count = int(low_stock_q.count() or 0)
            low_stock_total_pages = max(1, math.ceil(low_stock_count / low_stock_page_size))
            current_ls_page = min(requested_ls_page, low_stock_total_pages)
            low_stock_offset = (current_ls_page - 1) * low_stock_page_size
            low_stock_products = [
                p.to_dict()
                for p in low_stock_q.order_by(Product.stock.asc(), Product.name.asc())
                .limit(low_stock_page_size)
                .offset(low_stock_offset)
                .all()
            ]

            # Factor promedio de margen comercial de la tienda para proyectar compras del periodo
            avg_markup_factor = (
                (total_inventory_retail / total_inventory_cost)
                if total_inventory_cost > 0 else 1.38
            )

            # Mapa ligero de product_id -> categoría (tuplas SQL sin construir objetos ORM)
            product_category_map: Dict[int, str] = {
                pid: (cat or "General")
                for pid, cat in session.query(Product.id, Product.category)
                .filter(Product.is_active == True)
                .all()
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
            cash_sales = max(0.0, realized_sales - pending_credits)

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

            # 5. Productos registrados/actualizados dentro del periodo (vía agregación SQL)
            if is_all_time:
                period_products_cost = total_inventory_cost
                period_products_retail = total_inventory_retail
            else:
                prod_period_agg = session.query(
                    func.coalesce(func.sum(Product.cost_price * Product.stock), 0.0),
                    func.coalesce(func.sum(Product.sale_price * Product.stock), 0.0),
                ).filter(Product.is_active == True)
                if start_date is not None:
                    prod_period_agg = prod_period_agg.filter(Product.updated_at >= start_date)
                if end_date is not None:
                    prod_period_agg = prod_period_agg.filter(Product.updated_at <= end_date)
                pp_row = prod_period_agg.first()
                period_products_cost = float(pp_row[0] or 0.0) if pp_row else 0.0
                period_products_retail = float(pp_row[1] or 0.0) if pp_row else 0.0

            # 6. Cálculo consolidado del periodo para KPIs y Gráficas
            total_operational_outflows = supplier_expenses + general_expenses
            period_cost = total_operational_outflows
            if is_all_time:
                period_projected_sales = total_inventory_retail + realized_sales
            else:
                projected_from_purchases = round(supplier_expenses * avg_markup_factor, 2)
                period_projected_sales = realized_sales + max(projected_from_purchases, period_products_retail)

            real_net_profit = gross_sales_profit - general_expenses
            net_cash_flow = realized_sales - supplier_expenses - general_expenses
            period_potential_profit = period_projected_sales - period_cost

            # 7. Distribución dinámica por categorías para el Gráfico de Torta del periodo
            categories_data: Dict[str, float] = {}

            for inv in invoices:
                for item in inv.items:
                    cat = product_category_map.get(item.product_id, "Ventas Generales") if item.product_id else "Ventas POS"
                    categories_data[cat] = categories_data.get(cat, 0.0) + float(item.subtotal or 0.0)

            for exp in general_expenses_list:
                cat_key = f"Gasto: {exp.categoria}"
                categories_data[cat_key] = categories_data.get(cat_key, 0.0) + float(exp.monto or 0.0)

            if supplier_expenses > 0:
                categories_data["Compras Proveedores"] = (
                    categories_data.get("Compras Proveedores", 0.0) + float(supplier_expenses)
                )

            if is_all_time or not categories_data:
                cat_q = (
                    session.query(
                        Product.category,
                        func.coalesce(func.sum(Product.sale_price * Product.stock), 0.0),
                    )
                    .filter(Product.is_active == True)
                )
                if not is_all_time:
                    if start_date is not None:
                        cat_q = cat_q.filter(Product.updated_at >= start_date)
                    if end_date is not None:
                        cat_q = cat_q.filter(Product.updated_at <= end_date)
                for cat_name, retail_sum in cat_q.group_by(Product.category).all():
                    cat = cat_name or "Otros"
                    categories_data[cat] = categories_data.get(cat, 0.0) + float(retail_sum or 0.0)

            return {
                "period_label": period_label,
                "is_all_time": is_all_time,
                # Métricas dinámicas del periodo
                "period_cost": round(period_cost, 2),
                "period_projected_sales": round(period_projected_sales, 2),
                "period_potential_profit": round(period_potential_profit, 2),
                "total_realized_sales": round(realized_sales, 2),
                "cash_sales": round(cash_sales, 2),
                "sales_cogs": round(sales_cogs, 2),
                "gross_sales_profit": round(gross_sales_profit, 2),
                "supplier_expenses": round(supplier_expenses, 2),
                "general_expenses": round(general_expenses, 2),
                "total_outflows": round(total_operational_outflows, 2),
                "total_realized_profit": round(real_net_profit, 2),
                "net_cash_flow": round(net_cash_flow, 2),
                "pending_credits": round(pending_credits, 2),
                # Métricas de inventario físico en bodega y alertas paginadas (LIMIT 50 OFFSET X)
                "total_inventory_cost": round(total_inventory_cost, 2),
                "total_inventory_retail": round(total_inventory_retail, 2),
                "total_potential_profit": round(total_potential_profit, 2),
                "low_stock_count": low_stock_count,
                "low_stock_items": low_stock_products,
                "low_stock_page": current_ls_page,
                "low_stock_page_size": low_stock_page_size,
                "low_stock_total_pages": low_stock_total_pages,
                "low_stock_offset": low_stock_offset,
                "categories_distribution": categories_data,
                "total_products_count": total_products_count,
                "total_inventory_units": total_inventory_units,
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
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Consolida, ordena cronológicamente y pagina (LIMIT 50 OFFSET X) en SQLite:
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

        page_size = max(1, int(page_size or 50))
        requested_page = max(1, int(page or 1))
        has_search = bool(search_query and search_query.strip())

        total_ingresos = 0.0
        total_pagos_proveedores = 0.0
        total_gastos_generales = 0.0

        with get_db_session() as session:
            if not has_search:
                # Paginación directa en motor SQLite usando UNION ALL + LIMIT 50 OFFSET X
                subqueries = []

                if type_filter in ("ALL", "VENTA"):
                    inv_sum_q = session.query(
                        func.count(Invoice.id),
                        func.coalesce(func.sum(Invoice.total), 0.0),
                    ).filter(Invoice.payment_status != "CANCELLED")
                    inv_sel = session.query(
                        literal("VENTA").label("source_type"),
                        Invoice.id.label("source_id"),
                        Invoice.created_at.label("ts"),
                    ).filter(Invoice.payment_status != "CANCELLED")
                    if start_date is not None:
                        inv_sum_q = inv_sum_q.filter(Invoice.created_at >= start_date)
                        inv_sel = inv_sel.filter(Invoice.created_at >= start_date)
                    if end_date is not None:
                        inv_sum_q = inv_sum_q.filter(Invoice.created_at <= end_date)
                        inv_sel = inv_sel.filter(Invoice.created_at <= end_date)
                    inv_cnt, inv_sum = inv_sum_q.first() or (0, 0.0)
                    total_ingresos = round(float(inv_sum or 0.0), 2)
                    subqueries.append((int(inv_cnt or 0), inv_sel))

                if type_filter in ("ALL", "PROVEEDOR"):
                    sp_sum_q = session.query(
                        func.count(SupplierPurchase.id),
                        func.coalesce(func.sum(SupplierPurchase.monto), 0.0),
                    )
                    sp_sel = session.query(
                        literal("PROVEEDOR").label("source_type"),
                        SupplierPurchase.id.label("source_id"),
                        SupplierPurchase.fecha_hora.label("ts"),
                    )
                    if start_date is not None:
                        sp_sum_q = sp_sum_q.filter(SupplierPurchase.fecha_hora >= start_date)
                        sp_sel = sp_sel.filter(SupplierPurchase.fecha_hora >= start_date)
                    if end_date is not None:
                        sp_sum_q = sp_sum_q.filter(SupplierPurchase.fecha_hora <= end_date)
                        sp_sel = sp_sel.filter(SupplierPurchase.fecha_hora <= end_date)
                    sp_cnt, sp_sum = sp_sum_q.first() or (0, 0.0)
                    total_pagos_proveedores = round(float(sp_sum or 0.0), 2)
                    subqueries.append((int(sp_cnt or 0), sp_sel))

                if type_filter in ("ALL", "GASTO"):
                    exp_sum_q = session.query(
                        func.count(GastosGenerales.id),
                        func.coalesce(func.sum(GastosGenerales.monto), 0.0),
                    )
                    exp_sel = session.query(
                        literal("GASTO").label("source_type"),
                        GastosGenerales.id.label("source_id"),
                        GastosGenerales.fecha_hora.label("ts"),
                    )
                    if start_date is not None:
                        exp_sum_q = exp_sum_q.filter(GastosGenerales.fecha_hora >= start_date)
                        exp_sel = exp_sel.filter(GastosGenerales.fecha_hora >= start_date)
                    if end_date is not None:
                        exp_sum_q = exp_sum_q.filter(GastosGenerales.fecha_hora <= end_date)
                        exp_sel = exp_sel.filter(GastosGenerales.fecha_hora <= end_date)
                    exp_cnt, exp_sum = exp_sum_q.first() or (0, 0.0)
                    total_gastos_generales = round(float(exp_sum or 0.0), 2)
                    subqueries.append((int(exp_cnt or 0), exp_sel))

                total_records = sum(cnt for cnt, _ in subqueries)
                total_pages = max(1, math.ceil(total_records / page_size))
                current_page = min(requested_page, total_pages)
                offset_val = (current_page - 1) * page_size

                paginated_rows: List[Dict[str, Any]] = []
                if subqueries and total_records > 0:
                    combined = union_all(*(sq for _, sq in subqueries)).subquery()
                    order_col = combined.c.ts.desc() if descending else combined.c.ts.asc()
                    # Consulta SQLite con LIMIT 50 OFFSET X
                    page_keys = (
                        session.query(combined.c.source_type, combined.c.source_id)
                        .order_by(order_col, combined.c.source_id.desc())
                        .limit(page_size)
                        .offset(offset_val)
                        .all()
                    )

                    inv_ids = [sid for st, sid in page_keys if st == "VENTA"]
                    sp_ids = [sid for st, sid in page_keys if st == "PROVEEDOR"]
                    exp_ids = [sid for st, sid in page_keys if st == "GASTO"]

                    inv_map = (
                        {
                            inv.id: inv
                            for inv in session.query(Invoice)
                            .filter(Invoice.id.in_(inv_ids))
                            .all()
                        }
                        if inv_ids
                        else {}
                    )
                    sp_map = (
                        {
                            sp.id: sp
                            for sp in session.query(SupplierPurchase)
                            .filter(SupplierPurchase.id.in_(sp_ids))
                            .all()
                        }
                        if sp_ids
                        else {}
                    )
                    exp_map = (
                        {
                            g.id: g
                            for g in session.query(GastosGenerales)
                            .filter(GastosGenerales.id.in_(exp_ids))
                            .all()
                        }
                        if exp_ids
                        else {}
                    )

                    for st, sid in page_keys:
                        if st == "VENTA" and sid in inv_map:
                            inv = inv_map[sid]
                            dt = inv.created_at or datetime.now()
                            customer_name = inv.customer.name if inv.customer else "Consumidor Final"
                            items_qty = sum(i.quantity for i in inv.items)
                            pay_badge = "Crédito" if inv.payment_type == "CREDIT" else "Contado"
                            desc = f"Factura #{inv.invoice_number} — {customer_name} ({items_qty} uds, {pay_badge})"
                            amount = round(float(inv.total or 0.0), 2)
                            paginated_rows.append({
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
                        elif st == "PROVEEDOR" and sid in sp_map:
                            sp = sp_map[sid]
                            dt = sp.fecha_hora or datetime.now()
                            sup_name = sp.supplier.name if sp.supplier else "Proveedor General"
                            ref_txt = f" [Ref: {sp.invoice_reference}]" if sp.invoice_reference else ""
                            desc = f"{sup_name} — {sp.descripcion}{ref_txt}"
                            amount = round(float(sp.monto or 0.0), 2)
                            paginated_rows.append({
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
                        elif st == "GASTO" and sid in exp_map:
                            g = exp_map[sid]
                            dt = g.fecha_hora or datetime.now()
                            desc = f"[{g.categoria}] {g.descripcion}"
                            amount = round(float(g.monto or 0.0), 2)
                            paginated_rows.append({
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
            else:
                unified_rows: List[Dict[str, Any]] = []
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

                term = search_query.strip().lower()
                unified_rows = [
                    r for r in unified_rows
                    if term in r["descripcion"].lower()
                    or term in r["tipo"].lower()
                    or term in r["fecha"].lower()
                ]
                total_ingresos = sum(r["monto"] for r in unified_rows if r["source_type"] == "VENTA")
                total_pagos_proveedores = sum(r["monto"] for r in unified_rows if r["source_type"] == "PROVEEDOR")
                total_gastos_generales = sum(r["monto"] for r in unified_rows if r["source_type"] == "GASTO")
                unified_rows.sort(key=lambda r: r["timestamp"], reverse=descending)

                total_records = len(unified_rows)
                total_pages = max(1, math.ceil(total_records / page_size))
                current_page = min(requested_page, total_pages)
                offset_val = (current_page - 1) * page_size
                paginated_rows = unified_rows[offset_val : offset_val + page_size]

        total_egresos = total_pagos_proveedores + total_gastos_generales
        balance_neto = total_ingresos - total_egresos

        return {
            "period_label": period_label,
            "transactions": paginated_rows,
            "count": total_records,
            "total_records": total_records,
            "page": current_page,
            "page_size": page_size,
            "total_pages": total_pages,
            "offset": offset_val,
            "total_ingresos": round(total_ingresos, 2),
            "total_pagos_proveedores": round(total_pagos_proveedores, 2),
            "total_gastos_generales": round(total_gastos_generales, 2),
            "total_egresos": round(total_egresos, 2),
            "balance_neto": round(balance_neto, 2),
        }

    def get_invoice_details(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene el detalle completo de una factura (productos llevados, cantidades,
        precios unitarios, subtotales, abonos y cliente o 'Consumidor Final')
        para inspección desde el módulo de Flujo de Caja.
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
            data["description_display"] = raw_desc if raw_desc else "Venta registrada en Punto de Venta (POS)"
            return data

    def reverse_sale_invoice(self, invoice_id: int, motivo: str) -> Tuple[bool, str]:
        """
        Reversa una venta, registra la auditoría inmutable (Loss Prevention) con snapshot completo
        y restaura el stock en una única transacción atómica segura de base de datos:
        1. Valida que el motivo de anulación tenga al menos 5 caracteres.
        2. Lee los datos completos de la factura original (cabecera, cliente, items y abonos) ANTES de ejecutar el delete().
        3. Crea el registro en `RegistroAnulaciones` con fecha_anulacion, factura_id_original, monto_total, motivo y snapshot_json.
        4. Itera sobre los InvoiceItems, suma de vuelta la cantidad al Producto en inventario (product.stock += item.quantity).
        5. Elimina los items y la factura original y ejecuta un único session.commit().
        """
        clean_motivo = (motivo or "").strip()
        if len(clean_motivo) < 5:
            return (
                False,
                "El motivo de la anulación es obligatorio y debe contener al menos 5 caracteres.",
            )

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
                return False, "La factura de venta seleccionada no fue encontrada."

            # 1. Leer los datos completos de la factura que se va a anular ANTES de eliminarla
            invoice_num = str(invoice.invoice_number or invoice.id)
            original_id_str = f"{invoice_num} (ID: {invoice.id})"
            original_total = round(float(invoice.total or 0.0), 2)

            snapshot_payload = invoice.to_dict()
            raw_desc = (invoice.credit_notes or "").strip()
            snapshot_payload["description_display"] = (
                raw_desc if raw_desc else "Venta registrada en Punto de Venta (POS)"
            )
            snapshot_str = json.dumps(snapshot_payload, ensure_ascii=False, default=str)

            # 2. Crear registro inmutable de auditoría en RegistroAnulaciones con snapshot_json
            audit_entry = RegistroAnulaciones(
                factura_id_original=original_id_str,
                monto_total=original_total,
                fecha_anulacion=datetime.now(),
                motivo=clean_motivo,
                snapshot_json=snapshot_str,
                restaurada=False,
            )
            session.add(audit_entry)

            # 3. Restaurar stock en inventario y eliminar los items de la factura
            restored_units = 0
            for item in list(invoice.items):
                qty = int(item.quantity or 0)
                product = None
                if item.product_id:
                    product = session.query(Product).filter(Product.id == item.product_id).first()
                if product is None and item.barcode:
                    product = session.query(Product).filter(Product.barcode == item.barcode).first()

                if product is not None and qty > 0 and not bool(product.stock_infinito):
                    product.stock = int(product.stock or 0) + qty
                    restored_units += qty

                session.delete(item)

            for payment in list(invoice.payments):
                session.delete(payment)

            # 4. Eliminar la factura original y confirmar toda la transacción en bloque
            session.delete(invoice)
            session.commit()

        self.notify_filter_change()
        return (
            True,
            f"Factura #{invoice_num} anulada y auditada. Se restauraron {restored_units} unidades al inventario.",
        )

    def get_cancellation_audit_logs(self) -> List[Dict[str, Any]]:
        """Retorna el historial inmutable de anulaciones de ventas ordenado del más reciente al más antiguo."""
        with get_db_session() as session:
            logs = (
                session.query(RegistroAnulaciones)
                .order_by(RegistroAnulaciones.fecha_anulacion.desc(), RegistroAnulaciones.id.desc())
                .all()
            )
            return [log.to_dict() for log in logs]

    def get_audit_log_invoice_details(self, audit_log_id: int) -> Optional[Dict[str, Any]]:
        """
        Retorna el detalle completo de una factura anulada desde el Registro de Auditoría
        para poder visualizar exactamente qué productos, precios y cliente tenía cargados.
        Incluye soporte retrocompatible para anulaciones previas que no tenían snapshot_json.
        """
        with get_db_session() as session:
            log = (
                session.query(RegistroAnulaciones)
                .filter(RegistroAnulaciones.id == audit_log_id)
                .first()
            )
            if not log:
                return None

            log_dict = log.to_dict()
            raw_ref = str(log.factura_id_original or f"AUDIT-{log.id}").strip()
            orig_invoice_num = raw_ref.split(" (ID:")[0].strip() if " (ID:" in raw_ref else raw_ref
            dt_cancel = log.fecha_anulacion or datetime.now()
            total_val = round(float(log.monto_total or 0.0), 2)

            snapshot = log_dict.get("snapshot")
            if isinstance(snapshot, dict) and snapshot:
                items_list = snapshot.get("items", []) or []
                total_cost = round(
                    sum(float(i.get("unit_cost", 0.0)) * int(i.get("quantity", 1)) for i in items_list),
                    2,
                )
                total_profit = round(float(snapshot.get("total", total_val)) - total_cost, 2)
                raw_desc = (snapshot.get("credit_notes") or "").strip()
                return {
                    "audit_log_id": log.id,
                    "has_snapshot": True,
                    "restaurada": bool(log.restaurada),
                    "motivo": log.motivo or "",
                    "fecha_anulacion": dt_cancel.strftime("%Y-%m-%d %H:%M:%S"),
                    "factura_id_original": raw_ref,
                    "invoice_number": snapshot.get("invoice_number") or orig_invoice_num,
                    "created_at": snapshot.get("created_at") or dt_cancel.strftime("%Y-%m-%d %H:%M:%S"),
                    "date": snapshot.get("date") or dt_cancel.strftime("%Y-%m-%d"),
                    "time": snapshot.get("time") or dt_cancel.strftime("%H:%M:%S"),
                    "customer_id": snapshot.get("customer_id"),
                    "customer_name": snapshot.get("customer_name") or "Consumidor Final",
                    "payment_type": snapshot.get("payment_type") or "CASH",
                    "payment_status": snapshot.get("payment_status") or "PAID",
                    "subtotal": round(float(snapshot.get("subtotal", total_val)), 2),
                    "discount": round(float(snapshot.get("discount", 0.0)), 2),
                    "tax": round(float(snapshot.get("tax", 0.0)), 2),
                    "total": round(float(snapshot.get("total", total_val)), 2),
                    "amount_paid": round(float(snapshot.get("amount_paid", total_val)), 2),
                    "balance_due": round(float(snapshot.get("balance_due", 0.0)), 2),
                    "total_cost": round(float(snapshot.get("total_cost", total_cost)), 2),
                    "total_profit": round(float(snapshot.get("total_profit", total_profit)), 2),
                    "credit_notes": raw_desc,
                    "description_display": (
                        snapshot.get("description_display")
                        or (raw_desc if raw_desc else "Venta registrada en Punto de Venta (POS)")
                    ),
                    "items_count": int(snapshot.get("items_count") or sum(int(i.get("quantity", 1)) for i in items_list)),
                    "items": items_list,
                    "payments": snapshot.get("payments", []) or [],
                }

            # Fallback retrocompatible para facturas anuladas antes de implementar snapshot_json
            est_cost = round(total_val / 1.2, 2) if total_val > 0 else 0.0
            est_profit = round(total_val - est_cost, 2)
            fallback_item = {
                "product_id": None,
                "barcode": WILDCARD_PRODUCT_BARCODE,
                "product_name": f"Venta Histórica Recuperada ({orig_invoice_num})",
                "display_name": f"Venta Histórica Recuperada ({orig_invoice_num}) [Sin desglose previo]",
                "presentacion": "Registro Histórico",
                "category": "Venta Libre / Comodín",
                "unit_cost": est_cost,
                "unit_price": total_val,
                "quantity": 1,
                "subtotal": total_val,
                "total_profit": est_profit,
            }
            return {
                "audit_log_id": log.id,
                "has_snapshot": False,
                "restaurada": bool(log.restaurada),
                "motivo": log.motivo or "",
                "fecha_anulacion": dt_cancel.strftime("%Y-%m-%d %H:%M:%S"),
                "factura_id_original": raw_ref,
                "invoice_number": orig_invoice_num,
                "created_at": dt_cancel.strftime("%Y-%m-%d %H:%M:%S"),
                "date": dt_cancel.strftime("%Y-%m-%d"),
                "time": dt_cancel.strftime("%H:%M:%S"),
                "customer_id": None,
                "customer_name": "Consumidor Final",
                "payment_type": "CASH",
                "payment_status": "PAID",
                "subtotal": total_val,
                "discount": 0.0,
                "tax": 0.0,
                "total": total_val,
                "amount_paid": total_val,
                "balance_due": 0.0,
                "total_cost": est_cost,
                "total_profit": est_profit,
                "credit_notes": f"Factura histórica anulada por: {log.motivo or 'Sin motivo'}",
                "description_display": (
                    f"Factura anulada antes del desglose automático (Motivo original: {log.motivo or 'N/A'})"
                ),
                "items_count": 1,
                "items": [fallback_item],
                "payments": [],
            }

    def restore_cancelled_invoice(self, audit_log_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Restaura una factura previamente anulada desde `RegistroAnulaciones` de vuelta a la tabla
        `invoices` (Flujo de Caja / Cartera), reconstruyendo sus ítems, abonos y descontando
        nuevamente el stock físico de los productos correspondientes.
        Soporta tanto facturas con `snapshot_json` completo como anulaciones históricas previas.
        """
        with get_db_session() as session:
            log = (
                session.query(RegistroAnulaciones)
                .filter(RegistroAnulaciones.id == audit_log_id)
                .first()
            )
            if not log:
                return False, "El registro de anulación seleccionado no existe.", None

            raw_ref = str(log.factura_id_original or f"INV-REST-{log.id}").strip()
            orig_invoice_num = raw_ref.split(" (ID:")[0].strip() if " (ID:" in raw_ref else raw_ref

            if bool(log.restaurada):
                existing = (
                    session.query(Invoice)
                    .filter(Invoice.invoice_number == orig_invoice_num)
                    .first()
                )
                if existing:
                    return (
                        False,
                        f"La factura {orig_invoice_num} ya fue restaurada anteriormente y se encuentra activa en el Flujo de Caja.",
                        existing.to_dict(),
                    )

            log_dict = log.to_dict()
            snapshot = log_dict.get("snapshot")

            # Determinar número de factura único (reutilizando el original si está libre)
            target_invoice_num = (
                (snapshot.get("invoice_number") if isinstance(snapshot, dict) else None)
                or orig_invoice_num
            )
            collision = (
                session.query(Invoice.id)
                .filter(Invoice.invoice_number == target_invoice_num)
                .first()
            )
            if collision is not None:
                suffix = 1
                while True:
                    candidate = f"{target_invoice_num}-R{suffix}"
                    exists = (
                        session.query(Invoice.id)
                        .filter(Invoice.invoice_number == candidate)
                        .first()
                    )
                    if exists is None:
                        target_invoice_num = candidate
                        break
                    suffix += 1

            discounted_units = 0

            if isinstance(snapshot, dict) and snapshot:
                # Parsear fecha original de creación
                created_at_dt = log.fecha_anulacion or datetime.now()
                raw_created = snapshot.get("created_at") or snapshot.get("fecha_hora")
                if raw_created:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                        try:
                            created_at_dt = datetime.strptime(str(raw_created)[:19], fmt)
                            break
                        except ValueError:
                            continue

                # Verificar si el cliente original aún existe
                cust_id = snapshot.get("customer_id")
                if cust_id is not None:
                    cust_exists = session.query(Customer.id).filter(Customer.id == cust_id).first()
                    if not cust_exists:
                        cust_id = None

                restored_invoice = Invoice(
                    invoice_number=target_invoice_num,
                    created_at=created_at_dt,
                    customer_id=cust_id,
                    payment_type=snapshot.get("payment_type") or "CASH",
                    payment_status=snapshot.get("payment_status") or "PAID",
                    subtotal=round(float(snapshot.get("subtotal", log.monto_total or 0.0)), 2),
                    discount=round(float(snapshot.get("discount", 0.0)), 2),
                    tax=round(float(snapshot.get("tax", 0.0)), 2),
                    total=round(float(snapshot.get("total", log.monto_total or 0.0)), 2),
                    amount_paid=round(float(snapshot.get("amount_paid", log.monto_total or 0.0)), 2),
                    credit_notes=snapshot.get("credit_notes") or "",
                    created_via=snapshot.get("created_via") or "POS_DESKTOP",
                )
                session.add(restored_invoice)
                session.flush()

                items_data = snapshot.get("items", []) or []
                wildcard_prod = None

                for item_dict in items_data:
                    qty = max(1, int(item_dict.get("quantity", 1)))
                    prod_id = item_dict.get("product_id")
                    barcode_str = str(item_dict.get("barcode") or WILDCARD_PRODUCT_BARCODE).strip()

                    product = None
                    if prod_id:
                        product = session.query(Product).filter(Product.id == prod_id).first()
                    if product is None and barcode_str:
                        product = session.query(Product).filter(Product.barcode == barcode_str).first()
                    if product is None:
                        if wildcard_prod is None:
                            wildcard_prod = ensure_wildcard_product(session)
                        product = wildcard_prod

                    if product is not None and not bool(product.stock_infinito):
                        product.stock = max(0, int(product.stock or 0) - qty)
                        discounted_units += qty

                    unit_price = round(float(item_dict.get("unit_price", 0.0)), 2)
                    unit_cost = round(float(item_dict.get("unit_cost", 0.0)), 2)
                    subtotal_val = round(float(item_dict.get("subtotal", unit_price * qty)), 2)

                    restored_item = InvoiceItem(
                        invoice_id=restored_invoice.id,
                        product_id=product.id if product else None,
                        barcode=barcode_str,
                        product_name=str(item_dict.get("product_name") or (product.name if product else "Producto")),
                        presentacion=str(item_dict.get("presentacion") or ""),
                        unit_cost=unit_cost,
                        unit_price=unit_price,
                        quantity=qty,
                        subtotal=subtotal_val,
                    )
                    session.add(restored_item)

                payments_data = snapshot.get("payments", []) or []
                for pay_dict in payments_data:
                    pay_dt = created_at_dt
                    raw_pay_dt = pay_dict.get("fecha_hora")
                    if raw_pay_dt:
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                            try:
                                pay_dt = datetime.strptime(str(raw_pay_dt)[:19], fmt)
                                break
                            except ValueError:
                                continue
                    restored_pay = InvoicePayment(
                        invoice_id=restored_invoice.id,
                        fecha_hora=pay_dt,
                        amount=round(float(pay_dict.get("amount", 0.0)), 2),
                        balance_after=round(float(pay_dict.get("balance_after", 0.0)), 2),
                        payment_kind=str(pay_dict.get("payment_kind") or "ABONO"),
                        notes=pay_dict.get("notes") or "",
                    )
                    session.add(restored_pay)

            else:
                # Restauración retrocompatible para facturas anuladas antes de implementar snapshot_json
                total_val = round(float(log.monto_total or 0.0), 2)
                est_cost = round(total_val / 1.2, 2) if total_val > 0 else 0.0
                wildcard_prod = ensure_wildcard_product(session)

                restored_invoice = Invoice(
                    invoice_number=target_invoice_num,
                    created_at=log.fecha_anulacion or datetime.now(),
                    customer_id=None,
                    payment_type="CASH",
                    payment_status="PAID",
                    subtotal=total_val,
                    discount=0.0,
                    tax=0.0,
                    total=total_val,
                    amount_paid=total_val,
                    credit_notes=f"Factura restaurada desde Auditoría ({log.motivo or 'Recuperación'})",
                    created_via="POS_DESKTOP",
                )
                session.add(restored_invoice)
                session.flush()

                restored_item = InvoiceItem(
                    invoice_id=restored_invoice.id,
                    product_id=wildcard_prod.id,
                    barcode=WILDCARD_PRODUCT_BARCODE,
                    product_name=f"Venta Histórica Recuperada ({target_invoice_num})",
                    presentacion="Restaurada",
                    unit_cost=est_cost,
                    unit_price=total_val,
                    quantity=1,
                    subtotal=total_val,
                )
                session.add(restored_item)

            log.restaurada = True
            session.commit()
            session.refresh(restored_invoice)
            restored_dict = restored_invoice.to_dict()

        self.notify_filter_change()
        return (
            True,
            f"Factura #{target_invoice_num} restaurada exitosamente al Flujo de Caja"
            + (f" ({discounted_units} uds descontadas de inventario)." if discounted_units > 0 else "."),
            restored_dict,
        )

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
