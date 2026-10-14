from typing import List, Optional, Dict, Any
from sqlalchemy import or_

from database import get_db_session
from models import Product

class InventoryController:
    """Controlador CRUD y de lógica de inventario."""

    def get_all_products(self, search_query: str = "") -> List[Dict[str, Any]]:
        with get_db_session() as session:
            query = session.query(Product).filter(Product.is_active == True)
            if search_query.strip():
                term = f"%{search_query.strip()}%"
                query = query.filter(
                    or_(
                        Product.name.ilike(term),
                        Product.barcode.ilike(term),
                        Product.category.ilike(term)
                    )
                )
            products = query.order_by(Product.name.asc()).all()
            return [p.to_dict() for p in products]

    def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        with get_db_session() as session:
            product = session.query(Product).filter_by(id=product_id).first()
            return product.to_dict() if product else None

    def get_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        with get_db_session() as session:
            product = session.query(Product).filter_by(barcode=barcode.strip()).first()
            return product.to_dict() if product else None

    def create_product(
        self,
        barcode: str,
        name: str,
        cost_price: float,
        sale_price: float,
        stock: int,
        min_stock: int = 5,
        presentacion: str = "",
        description: str = "",
        category: str = "General"
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        barcode = barcode.strip()
        name = name.strip()

        if not barcode or not name:
            return False, "Código de barras y nombre son obligatorios.", None

        if cost_price < 0 or sale_price < 0 or stock < 0:
            return False, "Los precios y el stock no pueden ser negativos.", None

        with get_db_session() as session:
            existing = session.query(Product).filter_by(barcode=barcode).first()
            if existing:
                return False, f"Ya existe un producto con el código de barras '{barcode}'.", None

            new_prod = Product(
                barcode=barcode,
                name=name,
                presentacion=presentacion.strip() if presentacion else "",
                description=description.strip() if description else None,
                cost_price=float(cost_price),
                sale_price=float(sale_price),
                stock=int(stock),
                min_stock=int(min_stock),
                category=category.strip() if category else "General"
            )
            session.add(new_prod)
            session.commit()
            session.refresh(new_prod)
            return True, f"Producto '{new_prod.display_name}' creado exitosamente.", new_prod.to_dict()

    def update_product(
        self,
        product_id: int,
        barcode: str,
        name: str,
        cost_price: float,
        sale_price: float,
        stock: int,
        min_stock: int = 5,
        presentacion: str = "",
        description: str = "",
        category: str = "General"
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        with get_db_session() as session:
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                return False, f"Producto con ID {product_id} no encontrado.", None

            # Verificar colisión de código con otro producto
            duplicate = session.query(Product).filter(
                Product.barcode == barcode.strip(),
                Product.id != product_id
            ).first()
            if duplicate:
                return False, f"El código '{barcode}' ya está en uso por otro producto.", None

            product.barcode = barcode.strip()
            product.name = name.strip()
            product.presentacion = presentacion.strip() if presentacion else ""
            product.cost_price = float(cost_price)
            product.sale_price = float(sale_price)
            product.stock = int(stock)
            product.min_stock = int(min_stock)
            product.description = description.strip() if description else None
            product.category = category.strip() if category else "General"

            session.commit()
            session.refresh(product)
            return True, f"Producto '{product.display_name}' actualizado.", product.to_dict()

    def lookup_open_food_facts(self, barcode: str) -> Dict[str, Any]:
        """Consulta la API de Open Food Facts para autocompletar presentación y datos."""
        from services.open_food_facts import OpenFoodFactsService
        return OpenFoodFactsService.fetch_product_by_barcode(barcode)

    def delete_product(self, product_id: int) -> tuple[bool, str]:
        with get_db_session() as session:
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                return False, "Producto no encontrado."

            # Soft delete o eliminación física
            product.is_active = False
            session.commit()
            return True, f"Producto '{product.name}' desactivado del inventario."

    def get_low_stock_products(self) -> List[Dict[str, Any]]:
        """Retorna productos cuyo stock está en o por debajo del mínimo de alerta."""
        with get_db_session() as session:
            low_stock = session.query(Product).filter(
                Product.is_active == True,
                Product.stock <= Product.min_stock
            ).order_by(Product.stock.asc()).all()
            return [p.to_dict() for p in low_stock]
