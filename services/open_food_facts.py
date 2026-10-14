from typing import Dict, Any, Optional
import httpx

class OpenFoodFactsService:
    """
    Servicio de integración con la API REST de Open Food Facts (v2).
    Permite consultar códigos de barras a nivel mundial y extraer
    automáticamente el nombre, marca, categoría y la presentación física (quantity).
    """

    BASE_URL = "https://world.openfoodfacts.org/api/v2/product"
    USER_AGENT = "PointPulsePOS/2.0 (local.pos.system; contact@pointpulse.local)"

    @classmethod
    def fetch_product_by_barcode(cls, barcode: str, timeout: float = 6.0) -> Dict[str, Any]:
        """
        Consulta la API de Open Food Facts para un código de barras.
        Retorna un diccionario estructurado con:
        - found: bool
        - name: str (nombre comercial del producto)
        - quantity: str (presentación física: "65g", "500ml", "1kg", etc.)
        - brand: str (marca fabricante)
        - category: str (categoría alimenticia o general)
        - display_name: str (nombre concatenado con presentación)
        """
        code = barcode.strip()
        if not code:
            return {"found": False, "error": "Código de barras vacío"}

        url = f"{cls.BASE_URL}/{code}.json"
        headers = {
            "User-Agent": cls.USER_AGENT,
            "Accept": "application/json"
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    # En Open Food Facts, status == 1 indica producto encontrado
                    if status == 1 and "product" in data:
                        raw = data["product"]
                        
                        # 1. Extracción de Nombre (prioriza español si existe)
                        name = (
                            raw.get("product_name_es") or 
                            raw.get("product_name") or 
                            raw.get("generic_name_es") or 
                            raw.get("generic_name") or 
                            ""
                        ).strip()

                        # 2. Extracción de Presentación / Cantidad (CRÍTICO)
                        quantity = (
                            raw.get("quantity") or 
                            raw.get("product_quantity_unit") or 
                            ""
                        ).strip()
                        # Limpiar sufijos comunes como 'e' (peso neto estimado europeo ej. '400 g e')
                        if quantity.endswith(" e"):
                            quantity = quantity[:-2].strip()

                        # 3. Extracción de Marca
                        brand = (raw.get("brands") or "").strip()
                        if brand:
                            # Si vienen múltiples marcas separadas por coma, tomar la primera
                            brand = brand.split(",")[0].strip()

                        # 4. Categoría
                        category = (raw.get("categories") or "Abarrotes").split(",")[0].strip()
                        if category.startswith("en:"):
                            category = category[3:].replace("-", " ").capitalize()

                        # 5. Nombre sugerido para catálogo
                        final_name = name
                        if brand and brand.lower() not in final_name.lower():
                            final_name = f"{final_name} {brand}".strip() if final_name else brand

                        display_name = f"{final_name} - {quantity}" if (quantity and final_name) else final_name

                        return {
                            "found": True,
                            "barcode": code,
                            "name": final_name or "Producto sin nombre",
                            "quantity": quantity, # ej. "65g", "500ml", "1kg"
                            "brand": brand,
                            "category": category or "General",
                            "display_name": display_name
                        }

                elif response.status_code == 404:
                    return {"found": False, "barcode": code, "error": "Producto no encontrado en Open Food Facts."}

                return {"found": False, "barcode": code, "error": f"Respuesta no satisfactoria (HTTP {response.status_code})"}

        except httpx.TimeoutException:
            return {"found": False, "barcode": code, "error": "Tiempo de espera agotado al conectar con Open Food Facts."}
        except Exception as e:
            return {"found": False, "barcode": code, "error": f"Error de conexión: {str(e)}"}
