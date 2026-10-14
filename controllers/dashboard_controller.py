from typing import Dict, Any, List
from sqlalchemy import func

from database import get_db_session
from models import Product, Invoice, InvoiceItem

class DashboardController:
    """Controlador analítico para métricas clave, alertas y reportes."""

    def get_kpis(self) -> Dict[str, Any]:
        with get_db_session() as session:
            # Métricas de inventario
            products = session.query(Product).filter(Product.is_active == True).all()
            total_inventory_cost = sum(p.total_cost_value for p in products)
            total_inventory_retail = sum(p.total_retail_value for p in products)
            total_potential_profit = total_inventory_retail - total_inventory_cost
            low_stock_products = [p.to_dict() for p in products if p.is_low_stock]

            # Métricas de ventas realizadas
            invoices = session.query(Invoice).all()
            total_realized_sales = sum(inv.total for inv in invoices)
            total_realized_profit = sum(inv.total_profit for inv in invoices)
            
            # Cartera pendiente por cobrar (Créditos)
            pending_credits = sum(
                inv.total for inv in invoices 
                if inv.payment_type == "CREDIT" and inv.payment_status == "PENDING"
            )

            # Distribución por categorías para gráficos
            categories_data: Dict[str, float] = {}
            for p in products:
                cat = p.category or "Otros"
                categories_data[cat] = categories_data.get(cat, 0.0) + p.total_retail_value

            return {
                "total_inventory_cost": round(total_inventory_cost, 2),
                "total_inventory_retail": round(total_inventory_retail, 2),
                "total_potential_profit": round(total_potential_profit, 2),
                "total_realized_sales": round(total_realized_sales, 2),
                "total_realized_profit": round(total_realized_profit, 2),
                "pending_credits": round(pending_credits, 2),
                "low_stock_count": len(low_stock_products),
                "low_stock_items": low_stock_products,
                "categories_distribution": categories_data,
                "total_products_count": len(products),
                "total_invoices_count": len(invoices)
            }
