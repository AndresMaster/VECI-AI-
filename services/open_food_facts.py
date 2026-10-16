from typing import Dict, Any, Optional
import requests
from config import OFF_USER_AGENT

class OpenFoodFactsService:
    """
    Servicio de integración con la API REST pública de Open Food Facts (v2).
    Utiliza la librería 'requests' con User-Agent personalizado obligatorio.
    Extrae 'product_name' (nombre), 'brands' (marca) y 'quantity' (presentación).
    """

    BASE_URL = "https://world.openfoodfacts.org/api/v2/product"
    USER_AGENT = OFF_USER_AGENT

    @classmethod
    def fetch_product_by_barcode(cls, barcode: str, timeout: float = 6.0) -> Dict[str, Any]:
        """
        Ejecuta petición HTTP GET con 'requests' a Open Food Facts.
        URL: https://world.openfoodfacts.org/api/v2/product/{codigo_de_barras}.json
        
        Verifica status 200 y status de producto '1'.
        Retorna diccionario con:
        - found: bool
        - product_name: str
        - brands: str
        - quantity: str (presentación física: ej. '65g', '500ml')
        - category: str
        - display_name: str
        """
        code = barcode.strip()
        if not code:
            return {"found": False, "barcode": code, "error": "Código de barras vacío"}

        url = f"{cls.BASE_URL}/{code}.json"
        headers = {
            "User-Agent": cls.USER_AGENT,
            "Accept": "application/json"
        }

        try:
            response = requests.get(url, headers=headers, timeout=timeout)

            # Verificar status 200 de la petición HTTP
            if response.status_code == 200:
                data = response.json()
                product_status = data.get("status")

                # En Open Food Facts, status == 1 indica producto encontrado y válido
                if product_status == 1 and "product" in data:
                    raw = data["product"]

                    # 1. Extracción de product_name (prioriza variantes en español si están disponibles)
                    product_name = (
                        raw.get("product_name") or
                        raw.get("product_name_es") or
                        raw.get("generic_name_es") or
                        raw.get("generic_name") or
                        ""
                    ).strip()

                    # 2. Extracción de brands (marca)
                    brands = (raw.get("brands") or "").strip()
                    if brands:
                        # Si vienen múltiples marcas separadas por coma, tomar la principal
                        brands = brands.split(",")[0].strip()

                    # 3. Extracción de quantity (presentación física: "65g", "500ml", "1kg")
                    quantity = (
                        raw.get("quantity") or
                        raw.get("product_quantity_unit") or
                        ""
                    ).strip()
                    if quantity.endswith(" e"):
                        quantity = quantity[:-2].strip()

                    # 4. Extracción de categoría
                    category = (raw.get("categories") or "Abarrotes").split(",")[0].strip()
                    if category.startswith("en:"):
                        category = category[3:].replace("-", " ").capitalize()

                    # Nombre compuesto para catálogo
                    catalog_name = product_name or "Producto sin nombre"
                    if brands and brands.lower() not in catalog_name.lower():
                        catalog_name = f"{catalog_name} ({brands})"

                    display_name = f"{catalog_name} - {quantity}" if (quantity and catalog_name) else catalog_name

                    return {
                        "found": True,
                        "barcode": code,
                        "product_name": product_name or catalog_name,
                        "brands": brands,
                        "name": catalog_name,
                        "quantity": quantity,
                        "category": category or "General",
                        "display_name": display_name
                    }

                elif product_status == 0 or product_status == "0":
                    return {
                        "found": False,
                        "barcode": code,
                        "error": "Producto no encontrado en Open Food Facts."
                    }

            elif response.status_code == 404:
                return {
                    "found": False,
                    "barcode": code,
                    "error": "Producto no registrado en Open Food Facts."
                }

            return {
                "found": False,
                "barcode": code,
                "error": f"Respuesta del servidor no satisfactoria (HTTP {response.status_code})"
            }

        except requests.Timeout:
            return {
                "found": False,
                "barcode": code,
                "error": "Tiempo de espera agotado al conectar con Open Food Facts."
            }
        except requests.RequestException as req_err:
            return {
                "found": False,
                "barcode": code,
                "error": f"Error de conexión con Open Food Facts: {str(req_err)}"
            }
        except Exception as e:
            return {
                "found": False,
                "barcode": code,
                "error": f"Error inesperado al consultar Open Food Facts: {str(e)}"
            }
