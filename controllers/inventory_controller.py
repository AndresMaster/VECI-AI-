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
                        Product.presentacion.ilike(term),
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
        brand: str = "",
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
                brand=brand.strip() if brand else "",
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
        brand: str = "",
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
            product.brand = brand.strip() if brand else ""
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

    def adjust_product_stock(
        self,
        product_id: int,
        quantity_delta: int,
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Ajusta (In/Out) la cantidad en stock de un producto sumando o restando unidades:
        - Si quantity_delta > 0 (Entrada / In): Suma las unidades al stock actual.
        - Si quantity_delta < 0 (Salida / Out): Resta las unidades del stock actual (sin permitir stock negativo).
        """
        if quantity_delta == 0:
            return False, "La cantidad a ajustar debe ser mayor a 0.", None

        with get_db_session() as session:
            product = session.query(Product).filter_by(id=product_id, is_active=True).first()
            if not product:
                return False, "Producto no encontrado en el inventario.", None

            previous_stock = int(product.stock or 0)
            new_stock = previous_stock + int(quantity_delta)
            if new_stock < 0:
                return (
                    False,
                    f"No puedes restar {abs(quantity_delta)} unidades porque solo hay {previous_stock} en stock.",
                    None,
                )

            product.stock = new_stock
            session.commit()
            session.refresh(product)
            action_label = f"+{quantity_delta} añadidas" if quantity_delta > 0 else f"{quantity_delta} restadas"
            return (
                True,
                f"Stock de '{product.display_name}' actualizado ({action_label}). Stock actual: {new_stock} uds.",
                product.to_dict(),
            )

    def scan_or_lookup_barcode_for_new(self, barcode: str) -> Dict[str, Any]:
        """
        Flujo de creación de producto con separación estricta:
        1. Consulta primero en SQLite local para evitar duplicados.
        2. Si no está en SQLite, ejecuta petición HTTP GET con 'requests' a Open Food Facts.
        3. Si status 200 y status '1', extrae 'product_name', 'brands', 'quantity' y categoría.
        """
        code = barcode.strip()
        if not code:
            return {"status": "EMPTY", "message": "Código de barras vacío."}

        # 1. Comprobación obligatoria en SQLite local
        existing = self.get_product_by_barcode(code)
        if existing:
            return {
                "status": "EXISTS_LOCAL",
                "message": f"El producto ya existe en la base de datos local: '{existing['display_name']}'.",
                "product": existing
            }

        # 2. Petición HTTP a Open Food Facts con librería 'requests' y User-Agent
        from services.open_food_facts import OpenFoodFactsService
        res = OpenFoodFactsService.fetch_product_by_barcode(code)
        if res.get("found"):
            return {
                "status": "OFF_FOUND",
                "message": f"¡Producto encontrado en Open Food Facts! {res.get('product_name')}",
                "data": res
            }

        return {
            "status": "NOT_FOUND",
            "message": res.get("error", "Producto no registrado en Open Food Facts.")
        }

    def lookup_open_food_facts(self, barcode: str) -> Dict[str, Any]:
        """Consulta directa a la API de Open Food Facts vía 'requests'."""
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
