from collections import Counter
import logging
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
import httpx
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.models.job import Job, JobSkill, Skill
from backend.app.etl.connectors import clean_html
from backend.app.etl.extractor import HybridSkillExtractor
from backend.app.etl.schemas import RawJobData
from backend.app.ml.train import predict_salary_with_confidence

logger = logging.getLogger("api.routes")
api_router = APIRouter()
extractor = HybridSkillExtractor()


# ============================================================================
# Esquemas Pydantic para Request y Response (Fase 4)
# ============================================================================
class PredictOfferRequest(BaseModel):
    url: Optional[str] = Field(default=None, description="URL pública de Get On Board o RemoteOK")
    title: Optional[str] = Field(default=None, description="Título del puesto si no se provee URL")
    description: Optional[str] = Field(default=None, description="Descripción del puesto si no se provee URL")
    seniority: Optional[str] = Field(default=None, description="junior, semi-senior, senior, lead")
    category: str = Field(default="programming", description="programming, data-science-analytics, sysadmin-devops-qa, machine-learning-ai")
    modality: str = Field(default="remote", description="remote, hybrid, onsite")
    market_region: str = Field(default="getonboard", description="getonboard o remoteok")


class PredictOfferResponse(BaseModel):
    title: str
    company: str
    detected_skills: List[str]
    seniority: str
    category: str
    modality: str
    market_region: str
    predicted_annual_usd: float
    predicted_monthly_usd: float
    confidence_range_annual_usd: List[float]
    source_evaluated: str


class CareerROIRequest(BaseModel):
    current_skills: List[str] = Field(description="Lista de tecnologías actuales del usuario")
    seniority: str = Field(default="junior", description="Nivel actual: junior, semi-senior, senior, lead")
    category: str = Field(default="programming", description="Categoría temática TI")
    market_region: str = Field(default="getonboard", description="getonboard (LatAm) o remoteok (Global)")
    modality: str = Field(default="remote", description="Modalidad de interés")
    top_n: int = Field(default=6, description="Cantidad de habilidades recomendadas")


# ============================================================================
# Endpoint 1: GET /api/v1/market-pulse (KPIs del Mercado TI en Vivo)
# ============================================================================
@api_router.get("/market-pulse")
def get_market_pulse():
    """
    Retorna métricas ejecutivas en vivo del mercado laboral TI:
    total de ofertas en SQL, % con sueldo visible vs oculto, salario promedio/mediana
    y Top 10 tecnologías más demandadas y mejor pagadas.
    """
    db = SessionLocal()
    try:
        jobs = db.scalars(select(Job)).all()
        total_jobs = len(jobs)
        if total_jobs == 0:
            return {"total_jobs": 0, "message": "No hay ofertas en la base de datos."}

        jobs_with_salary = 0
        annual_salaries = []
        source_counts = Counter()
        seniority_counts = Counter()

        for j in jobs:
            source_counts[j.source] += 1
            seniority_counts[j.seniority] += 1

            min_s = j.min_salary if j.min_salary and j.min_salary > 0 else None
            max_s = j.max_salary if j.max_salary and j.max_salary > 0 else None
            if min_s is not None or max_s is not None:
                jobs_with_salary += 1
                mid = (min_s + max_s) / 2.0 if (min_s and max_s) else (min_s or max_s) # type: ignore
                ann = mid * 12.0 if (j.source == "getonboard" or mid < 12000.0) else mid
                if 6000.0 <= ann <= 300000.0:
                    annual_salaries.append(ann)

        salary_coverage_pct = round((jobs_with_salary / total_jobs) * 100.0, 1)
        median_salary = round(float(np.median(annual_salaries)), 2) if annual_salaries else 0.0
        mean_salary = round(float(np.mean(annual_salaries)), 2) if annual_salaries else 0.0

        # Top 10 skills por demanda
        stmt_skills = (
            select(Skill.name, func.count(JobSkill.job_id).label("job_count"))
            .join(JobSkill, Skill.id == JobSkill.skill_id)
            .group_by(Skill.name)
            .order_by(func.count(JobSkill.job_id).desc())
            .limit(10)
        )
        top_demanded = [
            {"skill": row[0], "jobs_count": row[1], "demand_pct": round((row[1] / total_jobs) * 100.0, 1)}
            for row in db.execute(stmt_skills).all()
        ]

        return {
            "total_jobs": total_jobs,
            "jobs_with_salary": jobs_with_salary,
            "jobs_without_salary": total_jobs - jobs_with_salary,
            "salary_coverage_pct": salary_coverage_pct,
            "median_salary_annual_usd": median_salary,
            "mean_salary_annual_usd": mean_salary,
            "median_salary_monthly_usd": round(median_salary / 12.0, 2),
            "top_skills_by_demand": top_demanded,
            "seniority_distribution": dict(seniority_counts),
            "market_region_distribution": dict(source_counts),
        }
    finally:
        db.close()


# ============================================================================
# Endpoint 2: POST /api/v1/predict-offer (Predictor de Sueldo Oculto)
# ============================================================================
@api_router.post("/predict-offer", response_model=PredictOfferResponse)
async def predict_offer(payload: PredictOfferRequest, request: Request):
    """
    Predice la banda salarial oculta de una oferta de empleo TI.
    Acepta una URL de Get On Board (la extrae en vivo) o los campos manuales.
    """
    title = payload.title or ""
    description = payload.description or ""
    company = "Empresa Confidencial"
    evaluated_source = "direct_input"

    # Si se provee URL, extraer datos en vivo
    if payload.url:
        evaluated_source = payload.url
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Si es Get On Board, buscar ID en la URL
                match = re.search(r"/jobs/(?:[a-zA-Z0-9\-]+/)?([a-zA-Z0-9\-]+)", payload.url)
                if match and "getonbrd.com" in payload.url:
                    job_slug_or_id = match.group(1).split("-")[0]
                    api_url = f"https://www.getonbrd.com/api/v0/jobs/{job_slug_or_id}?expand=[\"company\"]"
                    resp = await client.get(api_url)
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        attrs = data.get("attributes", {})
                        title = attrs.get("title", title)
                        description = clean_html(attrs.get("description", ""))
                        company = attrs.get("company", {}).get("data", {}).get("attributes", {}).get("name", company)
                
                if not description:
                    # Fallback de scraping HTML ligero
                    resp = await client.get(payload.url)
                    if resp.status_code == 200:
                        description = clean_html(resp.text[:5000])
                        title = title or "Oferta Web TI"
        except Exception as e:
            logger.warning(f"No se pudo extraer URL en vivo ({e}). Se usarán datos de respaldo.")

    if not title and not description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes proporcionar una URL válida o al menos el título y descripción de la vacante."
        )

    # Extraer skills y seniority con el extractor híbrido
    dummy_job = RawJobData(
        source=payload.market_region,
        external_id="temp_predict",
        title=title or "Software Developer",
        company=company,
        raw_description=description,
        clean_description=description,
        modality=payload.modality,
        category=payload.category,
        url=payload.url or "",
    )
    enrichment = extractor.extract_with_regex(dummy_job)
    detected_skills = [s.name for s in enrichment.skills]
    seniority = payload.seniority or enrichment.seniority
    if seniority == "unknown":
        seniority = "senior" if len(detected_skills) >= 6 else "semi-senior"

    # Predecir con el modelo ML
    profile_df = pd.DataFrame([{
        "title": title or f"{seniority.capitalize()} Developer",
        "skills": detected_skills,
        "skill_count": float(len(detected_skills)),
        "seniority": seniority,
        "modality": payload.modality,
        "category": payload.category,
        "market_region": payload.market_region,
    }])

    pred = predict_salary_with_confidence(profile_df)

    return PredictOfferResponse(
        title=title or "Posición TI",
        company=company,
        detected_skills=detected_skills,
        seniority=seniority.upper(),
        category=payload.category,
        modality=payload.modality,
        market_region=payload.market_region.upper(),
        predicted_annual_usd=pred["predicted_annual_usd"],
        predicted_monthly_usd=pred["predicted_monthly_usd"],
        confidence_range_annual_usd=[pred["salary_min_annual_usd"], pred["salary_max_annual_usd"]],
        source_evaluated=evaluated_source,
    )


# ============================================================================
# Endpoint 3: POST /api/v1/career-roi (Simulador de ROI de Skills)
# ============================================================================
@api_router.post("/career-roi")
def simulate_career_roi(payload: CareerROIRequest, request: Request):
    """
    Recibe el stack actual del usuario y simula el retorno de inversión salarial
    y demanda de mercado de aprender nuevas tecnologías.
    """
    roi_engine = getattr(request.app.state, "roi_engine", None)
    if not roi_engine:
        from backend.app.ml.roi_engine import SkillROIEngine
        roi_engine = SkillROIEngine()

    result = roi_engine.simulate_roi(
        current_skills=payload.current_skills,
        seniority=payload.seniority,
        category=payload.category,
        market_region=payload.market_region,
        modality=payload.modality,
        top_n=payload.top_n
    )
    return result


# ============================================================================
# Endpoint 4: POST /api/v1/audit-cv (Auditor Monetizable de CV en PDF)
# ============================================================================
@api_router.post("/audit-cv")
async def audit_cv_pdf(
    file: UploadFile = File(..., description="Archivo PDF del CV (Máximo 5 MB)"),
    category: str = Form("programming", description="Categoría objetivo TI"),
    market_region: str = Form("getonboard", description="Mercado objetivo: getonboard o remoteok"),
    request: Request = None, # type: ignore
):
    """
    Auditoría Automatizada de CV en PDF (Feature Estrella Freemium):
    1. Valida el tipo y tamaño del PDF en memoria.
    2. Extrae texto, stack y seniority.
    3. Estima valor de mercado en USD.
    4. Cruza con ofertas de SQLite y detecta las 3 brechas para acceder al Top 20%.
    5. Retorna Top 5 skills con mayor ROI.
    """
    # 1. Validar Tipo MIME
    if not (file.filename.lower().endswith(".pdf") or file.content_type in ("application/pdf", "application/x-pdf")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato inválido. Solo se admiten archivos en formato PDF (.pdf)."
        )

    # 2. Leer archivo en memoria con límite estricto de 5 MB (Anti-DoS)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
    pdf_bytes = await file.read(MAX_FILE_SIZE + 1024)

    if len(pdf_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo PDF subido está vacío (0 bytes)."
        )

    if len(pdf_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo excede el tamaño máximo permitido de 5 MB."
        )

    # 3. Procesar Auditoría con el servicio pre-cargado
    cv_auditor = getattr(request.app.state, "cv_auditor", None) if request else None
    if not cv_auditor:
        from backend.app.services.cv_auditor import CVAuditorService
        cv_auditor = CVAuditorService()

    try:
        report = cv_auditor.audit_cv(
            pdf_bytes=pdf_bytes,
            target_market_region=market_region,
            target_category=category
        )
        return report
    except Exception as e:
        logger.error(f"Error procesando auditoría de CV: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo procesar el CV: {str(e)}"
        )
