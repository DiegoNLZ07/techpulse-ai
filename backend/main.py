from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Asegurar que la raíz del proyecto esté en sys.path para Windows
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.core.database import Base, engine
from backend.app.ml.train import MODEL_ARTIFACT_PATH, train_and_save_pipeline
from backend.app.ml.roi_engine import SkillROIEngine
from backend.app.services.cv_auditor import CVAuditorService
from backend.app.api.routes import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


# ============================================================================
# Gestión de Ciclo de Vida Moderno con Lifespan (Fase 4 - Estándar Senior)
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Carga y mantiene en memoria (app.state) los modelos de ML y servicios
    una sola vez al arrancar el servidor, evitando I/O de disco en cada petición.
    """
    logger.info("=== Iniciando TechPulse AI Backend ===")
    
    # 1. Asegurar esquema SQL inicializado y sembrar si está vacío
    Base.metadata.create_all(bind=engine)
    from backend.app.db.seed import seed_database
    seed_database()

    # 2. Pre-cargar artefactos ML en memoria
    if not MODEL_ARTIFACT_PATH.exists():
        logger.info("Artefacto ML no encontrado en disco. Ejecutando entrenamiento inicial...")
        train_and_save_pipeline(target_min_samples=320)

    logger.info("Cargando modelo ML y Motor de ROI en memoria RAM...")
    roi_engine = SkillROIEngine(MODEL_ARTIFACT_PATH)
    cv_auditor = CVAuditorService(roi_engine=roi_engine)

    app.state.roi_engine = roi_engine
    app.state.cv_auditor = cv_auditor
    logger.info("Motores predictivos precargados y listos para inferencia en <5ms.")

    yield

    logger.info("=== Apagando TechPulse AI Backend ===")


# ============================================================================
# Instanciación de la Aplicación FastAPI
# ============================================================================
app = FastAPI(
    title="TechPulse AI - API REST",
    description="Plataforma SaaS B2C/B2B para predicción salarial en TI, auditoría de CVs y simulación de ROI de skills.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# ============================================================================
# Configuración de Seguridad y CORS (Listo para Vue 3 en Fase 5)
# ============================================================================
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Registro de Rutas de la API
# ============================================================================
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root_status():
    return {
        "platform": "TechPulse AI",
        "status": "online",
        "docs": "/docs",
        "api_v1": "/api/v1",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "database": "sqlite_connected",
        "models_loaded": hasattr(app.state, "roi_engine") and app.state.roi_engine is not None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
