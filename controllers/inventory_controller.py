import math
from typing import List, Optional, Dict, Any
from sqlalchemy import or_, func, case

from database import get_db_session
from models import Product, WILDCARD_PRODUCT_BARCODE

class InventoryController:
    """Controlador CRUD y de lógica de inventario con paginación SQL (LIMIT / OFFSET)."""

    def get_inventory_summary(self) -> Dict[str, Any]:
        """
        Calcula instantáneamente en SQLite (sin cargar objetos ORM en memoria)
        las métricas globales del inventario para las tarjetas KPI superiores.
        Los productos con stock_infinito=True no suman unidades físicas ni costo de inventario.
        """
        with get_db_session() as session:
            is_physical = (Product.stock_infinito == False) & (Product.stock > 0)
            row = (
                session.query(
                    func.count(Product.id),
                    func.coalesce(
                        func.sum(case((is_physical, Product.stock), else_=0)),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((is_physical, Product.cost_price * Product.stock), else_=0.0)),
                        0.0,
                    ),
                    func.coalesce(
                        func.sum(case((is_physical, Product.sale_price * Product.stock), else_=0.0)),
                        0.0,
                    ),
                )
                .filter(
                    Product.is_active == True,
                    Product.barcode != WILDCARD_PRODUCT_BARCODE,
                )
                .first()
            )
            total_by_name = int(row[0] or 0) if row else 0
            total_units = int(row[1] or 0) if row else 0
            total_cost = round(float(row[2] or 0.0), 2) if row else 0.0
            total_retail = round(float(row[3] or 0.0), 2) if row else 0.0
            return {
                "total_by_name": total_by_name,
                "total_units": total_units,
                "total_cost_value": total_cost,
                "total_retail_value": total_retail,
            }

    def get_products_paginated(
        self,
        search_query: str = "",
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Consulta paginada a nivel de motor SQLite usando estrictamente `LIMIT 50 OFFSET X`.
        Retorna únicamente los registros de la página solicitada junto con los metadatos
        de paginación y los totales agregados del inventario.
        """
        page_size = max(1, int(page_size or 50))
        requested_page = max(1, int(page or 1))

        with get_db_session() as session:
            base_query = session.query(Product).filter(
                Product.is_active == True,
                Product.barcode != WILDCARD_PRODUCT_BARCODE,
            )
            if search_query and search_query.strip():
                term = f"%{search_query.strip()}%"
                base_query = base_query.filter(
                    or_(
                        Product.name.ilike(term),
                        Product.presentacion.ilike(term),
                        Product.barcode.ilike(term),
                        Product.category.ilike(term),
                    )
                )

            total_records = int(base_query.count() or 0)
            total_pages = max(1, math.ceil(total_records / page_size))
            current_page = min(requested_page, total_pages)
            offset_val = (current_page - 1) * page_size

            # Consulta SQLite con LIMIT 50 OFFSET X
            products = (
                base_query.order_by(Product.name.asc())
                .limit(page_size)
                .offset(offset_val)
                .all()
            )
            items = [p.to_dict() for p in products]

            # Resumen global mediante agregación SQL directa
            is_physical = (Product.stock_infinito == False) & (Product.stock > 0)
            summary_row = (
                session.query(
                    func.count(Product.id),
                    func.coalesce(
                        func.sum(case((is_physical, Product.stock), else_=0)),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((is_physical, Product.cost_price * Product.stock), else_=0.0)),
                        0.0,
                    ),
                )
                .filter(
                    Product.is_active == True,
                    Product.barcode != WILDCARD_PRODUCT_BARCODE,
                )
                .first()
            )
            total_by_name = int(summary_row[0] or 0) if summary_row else 0
            total_units = int(summary_row[1] or 0) if summary_row else 0
            total_inv_cost = round(float(summary_row[2] or 0.0), 2) if summary_row else 0.0

            return {
                "items": items,
                "page": current_page,
                "page_size": page_size,
                "total_records": total_records,
                "total_pages": total_pages,
                "offset": offset_val,
                "total_by_name": total_by_name,
                "total_units": total_units,
                "total_inventory_cost": total_inv_cost,
            }

    def get_all_products(
        self,
        search_query: str = "",
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with get_db_session() as session:
            query = session.query(Product).filter(
                Product.is_active == True,
                Product.barcode != WILDCARD_PRODUCT_BARCODE,
            )
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
            query = query.order_by(Product.name.asc())
            if offset > 0:
                query = query.offset(offset)
            if limit is not None and limit > 0:
                query = query.limit(limit)
            products = query.all()
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
        category: str = "General",
        stock_infinito: bool = False,
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        barcode = barcode.strip()
        name = name.strip()
        is_inf = bool(stock_infinito)

        if not barcode or not name:
            return False, "Código de barras y nombre son obligatorios.", None

        if cost_price < 0 or sale_price < 0 or (not is_inf and stock < 0):
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
                stock=0 if is_inf else int(stock),
                min_stock=0 if is_inf else int(min_stock),
                stock_infinito=is_inf,
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
        category: str = "General",
        stock_infinito: bool = False,
    ) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        is_inf = bool(stock_infinito)
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
            product.stock_infinito = is_inf
            if is_inf:
                product.stock = 0
                product.min_stock = 0
            else:
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

            if bool(product.stock_infinito):
                return (
                    False,
                    f"'{product.display_name}' tiene Stock Infinito (∞) activado y no requiere ajustes manuales de existencias.",
                    None,
                )

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
        """Retorna productos físicos (stock_infinito == False) cuyo stock está en o por debajo del mínimo de alerta."""
        with get_db_session() as session:
            low_stock = session.query(Product).filter(
                Product.is_active == True,
                Product.stock_infinito == False,
                Product.stock <= Product.min_stock
            ).order_by(Product.stock.asc()).all()
            return [p.to_dict() for p in low_stock]
