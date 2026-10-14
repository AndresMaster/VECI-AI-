import contextlib
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from config import DATABASE_URL
from models import Base, Product, Customer, Supplier

# Engine configurado para SQLite en entorno multi-hilo (UI Flet + hilo del escáner de cámara)
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

# Fábrica de sesiones ORM
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

@contextlib.contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager seguro para obtener y cerrar sesiones de base de datos.
    Efectúa rollback automático ante excepciones y cierra la sesión siempre.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def _migrate_database_schema() -> None:
    """Añade columnas nuevas si no existen para garantizar retrocompatibilidad."""
    with engine.connect() as conn:
        try:
            # 1. products.presentacion
            res_prod = conn.execute(text("PRAGMA table_info(products)"))
            prod_cols = [row[1] for row in res_prod.fetchall()]
            if "presentacion" not in prod_cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN presentacion VARCHAR(100) DEFAULT ''"))
                conn.commit()

            # 2. invoice_items.presentacion
            res_inv = conn.execute(text("PRAGMA table_info(invoice_items)"))
            inv_cols = [row[1] for row in res_inv.fetchall()]
            if "presentacion" not in inv_cols:
                conn.execute(text("ALTER TABLE invoice_items ADD COLUMN presentacion VARCHAR(100) DEFAULT ''"))
                conn.commit()
        except Exception as e:
            print(f"[Database Migration Warning]: {e}")

def init_db(seed_sample_data: bool = True) -> None:
    """
    Crea todas las tablas definidas en los modelos ORM si no existen.
    Aplica migraciones automáticas y opcionalmente precarga datos de prueba.
    """
    Base.metadata.create_all(bind=engine)
    _migrate_database_schema()
    
    if seed_sample_data:
        _seed_demo_data_if_empty()

def _seed_demo_data_if_empty() -> None:
    """Precarga datos iniciales para pruebas inmediatas si no hay productos registrados."""
    with get_db_session() as session:
        # Actualizar presentaciones vacías en productos de demostración existentes
        existing_products = session.query(Product).all()
        if existing_products:
            demo_map = {
                "7701001001": ("Leche Entera", "1L"),
                "7701001002": ("Pan Tajado Familiar", "500g"),
                "7701001003": ("Café Molido", "500g"),
                "7701001004": ("Arroz Blanco", "1kg"),
                "7701001005": ("Aceite Vegetal", "900ml"),
                "7701001006": ("Detergente en Polvo", "1kg"),
            }
            for p in existing_products:
                if p.barcode in demo_map and (not p.presentacion or not p.presentacion.strip()):
                    clean_name, pres = demo_map[p.barcode]
                    p.name = clean_name
                    p.presentacion = pres
            return # Ya existen datos

        # Productos de demostración con diferentes niveles de stock
        sample_products = [
            Product(
                barcode="7701001001",
                name="Leche Entera",
                presentacion="1L",
                description="Leche pasteurizada en bolsa",
                cost_price=3200.0,
                sale_price=4500.0,
                stock=25,
                min_stock=5,
                category="Lácteos"
            ),
            Product(
                barcode="7701001002",
                name="Pan Tajado Familiar",
                presentacion="500g",
                description="Pan blanco tajado suave",
                cost_price=4000.0,
                sale_price=5800.0,
                stock=14,
                min_stock=4,
                category="Panadería"
            ),
            Product(
                barcode="7701001003",
                name="Café Molido",
                presentacion="500g",
                description="Café tostado y molido premium",
                cost_price=12000.0,
                sale_price=17500.0,
                stock=3, # Alerta de stock bajo (< min_stock 5)
                min_stock=5,
                category="Bebidas"
            ),
            Product(
                barcode="7701001004",
                name="Arroz Blanco",
                presentacion="1kg",
                description="Arroz de primera calidad grano largo",
                cost_price=2800.0,
                sale_price=3900.0,
                stock=40,
                min_stock=10,
                category="Abarrotes"
            ),
            Product(
                barcode="7701001005",
                name="Aceite Vegetal",
                presentacion="900ml",
                description="Aceite de cocina 100% puro",
                cost_price=7500.0,
                sale_price=10500.0,
                stock=2, # Alerta de stock bajo
                min_stock=6,
                category="Abarrotes"
            ),
            Product(
                barcode="7701001006",
                name="Detergente en Polvo",
                presentacion="1kg",
                description="Limpieza profunda biodegradable",
                cost_price=6800.0,
                sale_price=9800.0,
                stock=18,
                min_stock=5,
                category="Aseo"
            )
        ]
        session.add_all(sample_products)

        # Clientes de demostración para cartera y crédito
        sample_customers = [
            Customer(
                name="María Camila Pérez",
                document_id="1020304050",
                phone="3101234567",
                email="maria.perez@example.com",
                credit_limit=150000.0,
                notes="Cliente frecuente del barrio. Autorizado crédito a 15 días."
            ),
            Customer(
                name="Restaurante La Esquina Gourmet",
                document_id="900123456-1",
                phone="3209876543",
                email="pedidos@laesquina.com",
                credit_limit=500000.0,
                notes="Compras institucionales semanales."
            )
        ]
        session.add_all(sample_customers)

        # Proveedores de demostración
        sample_suppliers = [
            Supplier(
                name="Distribuidora Lácteos del Valle",
                contact_name="Carlos Restrepo",
                phone="3114445566",
                email="ventas@lacteosvalle.com",
                notes="Entrega los días martes y viernes."
            ),
            Supplier(
                name="Molinos y Granos de Colombia",
                contact_name="Lucía Morales",
                phone="3157778899",
                email="contacto@molinosgranos.com",
                notes="Facturación a 30 días."
            )
        ]
        session.add_all(sample_suppliers)
