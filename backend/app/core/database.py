import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Ruta base del proyecto para persistencia consistente en Windows
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_SQLITE_PATH = BASE_DIR / "techpulse.db"

# Obtener URL desde variable de entorno o usar SQLite local por defecto
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

# Configuración condicional según el motor (ADR 0.1)
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    # Permite a FastAPI manejar conexiones SQLite en hilos concurrentes
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

# Activar integridad referencial estricta (Foreign Keys) en SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Generador de sesiones de base de datos
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base declarativa estándar de SQLAlchemy 2.0
class Base(DeclarativeBase):
    pass

# Helper para inyección de dependencias en FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
