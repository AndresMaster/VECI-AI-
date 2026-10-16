import contextlib
from datetime import datetime, timedelta
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from config import DATABASE_URL
from models import (
    Base,
    Product,
    Customer,
    Supplier,
    SupplierPurchase,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    GastosGenerales,
)

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
    """
    Ejecuta migraciones automáticas en caliente para SQLite:
    - Añade columnas nuevas si no existen.
    - Normaliza campos de fecha a DateTime (YYYY-MM-DD HH:MM:SS) en facturas,
      compras a proveedores y gastos generales.
    """
    with engine.connect() as conn:
        try:
            # 1. products.presentacion y products.brand
            res_prod = conn.execute(text("PRAGMA table_info(products)"))
            prod_cols = [row[1] for row in res_prod.fetchall()]
            if "presentacion" not in prod_cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN presentacion VARCHAR(100) DEFAULT ''"))
                conn.commit()
            if "brand" not in prod_cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN brand VARCHAR(100) DEFAULT ''"))
                conn.commit()

            # 2. invoice_items.presentacion
            res_inv_items = conn.execute(text("PRAGMA table_info(invoice_items)"))
            inv_item_cols = [row[1] for row in res_inv_items.fetchall()]
            if "presentacion" not in inv_item_cols:
                conn.execute(text("ALTER TABLE invoice_items ADD COLUMN presentacion VARCHAR(100) DEFAULT ''"))
                conn.commit()

            # 2.1 invoices.amount_paid para control de abonos parciales en créditos
            res_inv = conn.execute(text("PRAGMA table_info(invoices)"))
            inv_cols = [row[1] for row in res_inv.fetchall()]
            if "amount_paid" not in inv_cols:
                conn.execute(text("ALTER TABLE invoices ADD COLUMN amount_paid FLOAT DEFAULT 0.0"))
                conn.commit()

            # 3. Asegurar formato DateTime completo (con hora exacta) en invoices y suppliers
            conn.execute(text(
                "UPDATE invoices SET created_at = created_at || ' 00:00:00' "
                "WHERE created_at IS NOT NULL AND length(trim(created_at)) = 10"
            ))
            conn.execute(text(
                "UPDATE suppliers SET created_at = created_at || ' 00:00:00' "
                "WHERE created_at IS NOT NULL AND length(trim(created_at)) = 10"
            ))
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
    """Precarga datos iniciales para pruebas inmediatas si las tablas están vacías."""
    with get_db_session() as session:
        # 1. Productos, Clientes y Proveedores iniciales
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
        else:
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
                    stock=3,
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
                    stock=2,
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
            session.flush()

        # 2. Semilla de Compras a Proveedores (Egresos de inventario) si la tabla está vacía
        if session.query(SupplierPurchase).count() == 0:
            now = datetime.now()
            first_supplier = session.query(Supplier).order_by(Supplier.id.asc()).first()
            second_supplier = session.query(Supplier).order_by(Supplier.id.desc()).first()
            sup1_id = first_supplier.id if first_supplier else None
            sup2_id = second_supplier.id if second_supplier else None

            sample_purchases = [
                SupplierPurchase(
                    supplier_id=sup1_id,
                    fecha_hora=now.replace(hour=9, minute=15, second=20, microsecond=0),
                    invoice_reference="FAC-PROV-1042",
                    descripcion="Surtido de leche entera y derivados lácteos (Lote fresco)",
                    monto=48000.0,
                    payment_method="CASH"
                ),
                SupplierPurchase(
                    supplier_id=sup2_id,
                    fecha_hora=(now - timedelta(days=3)).replace(hour=14, minute=40, second=10, microsecond=0),
                    invoice_reference="FAC-PROV-0988",
                    descripcion="Abastecimiento de arroz blanco 1kg y aceite vegetal",
                    monto=95000.0,
                    payment_method="TRANSFER"
                ),
                SupplierPurchase(
                    supplier_id=sup1_id,
                    fecha_hora=(now - timedelta(days=18)).replace(hour=11, minute=5, second=45, microsecond=0),
                    invoice_reference="FAC-PROV-0850",
                    descripcion="Pedido mensual de panadería y lácteos",
                    monto=72000.0,
                    payment_method="CASH"
                ),
            ]
            session.add_all(sample_purchases)

        # 3. Semilla de Gastos Generales (Expenses) si la tabla está vacía
        if session.query(GastosGenerales).count() == 0:
            now = datetime.now()
            sample_expenses = [
                GastosGenerales(
                    fecha_hora=now.replace(hour=10, minute=30, second=0, microsecond=0),
                    categoria="Servicios Públicos",
                    descripcion="Pago recibo de energía eléctrica e internet del local",
                    monto=35000.0
                ),
                GastosGenerales(
                    fecha_hora=(now - timedelta(days=2)).replace(hour=16, minute=20, second=15, microsecond=0),
                    categoria="Varios",
                    descripcion="Insumos de aseo, bolsas plásticas y rollos térmicos POS",
                    monto=18500.0
                ),
                GastosGenerales(
                    fecha_hora=(now - timedelta(days=14)).replace(hour=17, minute=0, second=0, microsecond=0),
                    categoria="Nómina",
                    descripcion="Pago turno auxiliar de bodega y atención en caja",
                    monto=85000.0
                ),
                GastosGenerales(
                    fecha_hora=(now - timedelta(days=28)).replace(hour=8, minute=45, second=30, microsecond=0),
                    categoria="Servicios Públicos",
                    descripcion="Factura de acueducto y alcantarillado comercial",
                    monto=28000.0
                ),
            ]
            session.add_all(sample_expenses)
