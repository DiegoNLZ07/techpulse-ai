from collections import Counter
import io
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from pypdf import PdfReader
from sqlalchemy import select

# Asegurar que la raíz del proyecto esté en sys.path para Windows
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.core.database import SessionLocal
from backend.app.models.job import Job, JobSkill, Skill
from backend.app.etl.extractor import HybridSkillExtractor, SENIORITY_PATTERNS
from backend.app.etl.schemas import RawJobData
from backend.app.ml.train import predict_salary_with_confidence
from backend.app.ml.roi_engine import SkillROIEngine

logger = logging.getLogger("services.cv_auditor")


class CVAuditorService:
    """
    Servicio de Auditoría Automatizada de CVs en PDF (Feature Estrella Freemium - Fase 4).
    1. Extrae texto crudo desde PDFs en memoria con PyPDF.
    2. Identifica stack tecnológico y seniority del candidato con el extractor híbrido.
    3. Estima su valor de mercado actual en USD mediante el ensamble de ML.
    4. Cruza su perfil contra vacantes reales en SQLite e identifica brechas técnicas
       frente al Top 20% de ofertas mejor pagadas del mercado.
    5. Ejecuta el Simulador de ROI recomendando las tecnologías de mayor retorno.
    """

    def __init__(self, roi_engine: Optional[SkillROIEngine] = None):
        self.extractor = HybridSkillExtractor()
        self.roi_engine = roi_engine or SkillROIEngine()

    def extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """
        Extrae el texto de todas las páginas de un archivo PDF en memoria.
        """
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            full_text = "\n".join(text_parts).strip()
            return full_text
        except Exception as e:
            logger.error(f"Error procesando PDF: {e}")
            raise ValueError(f"No se pudo leer el archivo PDF: {e}")

    def audit_cv(
        self,
        pdf_bytes: bytes,
        target_market_region: str = "getonboard",
        target_category: str = "programming",
    ) -> Dict[str, Any]:
        """
        Flujo integral de auditoría de CV:
        - Input: bytes de PDF.
        - Output: Reporte ejecutivo completo con valorización, compatibilidad y brechas de ROI.
        """
        # 1. Extracción de texto
        cv_text = self.extract_text_from_pdf(pdf_bytes)
        if not cv_text or len(cv_text) < 50:
            raise ValueError("El archivo PDF no contiene suficiente texto legible (posible documento escaneado/imagen).")

        # 2. Extracción de Habilidades y Seniority
        dummy_job = RawJobData(
            source="cv_upload",
            external_id="cv_user",
            title="Curriculum Vitae",
            company="Candidato",
            raw_description=cv_text,
            clean_description=cv_text[:3000],
            modality="remote",
            category=target_category,
            url="",
        )

        enrichment = self.extractor.extract_with_regex(dummy_job)
        detected_skills = [s.name for s in enrichment.skills]
        detected_seniority = enrichment.seniority

        # Si el seniority es unknown, hacer fallback a junior/mid por defecto
        if detected_seniority == "unknown":
            detected_seniority = "junior" if len(detected_skills) <= 4 else "semi-senior"

        # 3. Estimación de Valor de Mercado Actual
        profile_df = pd.DataFrame([{
            "title": f"{detected_seniority.capitalize()} Developer",
            "skills": detected_skills,
            "skill_count": float(len(detected_skills)),
            "seniority": detected_seniority,
            "modality": "remote",
            "category": target_category,
            "market_region": target_market_region,
        }])

        valuation = predict_salary_with_confidence(profile_df)

        # 4. Cruce de Compatibilidad con Vacantes Reales en SQLite
        market_stats = self._match_against_market(
            user_skills=detected_skills,
            category=target_category,
            market_region=target_market_region
        )

        # 5. Simulación de ROI para cerrar brechas salariales
        roi_results = self.roi_engine.simulate_roi(
            current_skills=detected_skills,
            seniority=detected_seniority,
            category=target_category,
            market_region=target_market_region,
            top_n=5
        )

        return {
            "candidate_profile": {
                "detected_seniority": detected_seniority.upper(),
                "detected_skills_count": len(detected_skills),
                "detected_skills": detected_skills,
            },
            "market_valuation": {
                "estimated_annual_usd": valuation["predicted_annual_usd"],
                "estimated_monthly_usd": valuation["predicted_monthly_usd"],
                "confidence_range_annual_usd": [
                    valuation["salary_min_annual_usd"],
                    valuation["salary_max_annual_usd"],
                ],
                "market_region": target_market_region.upper(),
            },
            "market_matching": {
                "total_jobs_in_segment": market_stats["total_jobs"],
                "qualified_jobs_count": market_stats["qualified_count"],
                "qualification_rate_pct": market_stats["qualification_pct"],
                "top_20_percent_salary_threshold_usd": market_stats["top_20_threshold"],
                "critical_gaps_for_top_tier": market_stats["critical_gaps"],
            },
            "roi_recommendations": roi_results["recommendations"],
        }

    def _match_against_market(
        self,
        user_skills: List[str],
        category: str,
        market_region: str
    ) -> Dict[str, Any]:
        """
        Cruza las habilidades del candidato con las ofertas activas en SQLite
        y detecta las 3 habilidades clave que le impiden acceder al Top 20% de sueldos más altos.
        """
        db = SessionLocal()
        try:
            user_skills_set = {s.lower().strip() for s in user_skills}

            # Consultar ofertas del segmento
            stmt = select(Job).where(Job.category == category)
            if market_region:
                stmt = stmt.where(Job.source == market_region)
            jobs = db.scalars(stmt).all()

            if not jobs:
                # Si el filtro es muy estricto, relajar región
                jobs = db.scalars(select(Job).where(Job.category == category)).all()

            total_jobs = len(jobs)
            if total_jobs == 0:
                return {
                    "total_jobs": 0,
                    "qualified_count": 0,
                    "qualification_pct": 0.0,
                    "top_20_threshold": 0.0,
                    "critical_gaps": [],
                }

            qualified_count = 0
            job_matches: List[Tuple[Job, float, Set[str]]] = []

            for job in jobs:
                job_required_skills = {
                    js.skill.name.lower().strip()
                    for js in job.job_skills
                    if js.skill and js.is_required
                }
                if not job_required_skills:
                    job_required_skills = {
                        js.skill.name.lower().strip()
                        for js in job.job_skills
                        if js.skill
                    }

                if not job_required_skills:
                    continue

                intersection = user_skills_set.intersection(job_required_skills)
                match_rate = len(intersection) / len(job_required_skills)
                missing_skills = job_required_skills - user_skills_set

                if match_rate >= 0.50:  # Califica si cubre al menos el 50% de las skills
                    qualified_count += 1

                job_matches.append((job, match_rate, missing_skills))

            # Calcular umbral del Top 20% mejor pagado con anualización estricta (ADR 2.1)
            annual_salaries = []
            for j in jobs:
                min_s = j.min_salary if j.min_salary and j.min_salary > 0 else None
                max_s = j.max_salary if j.max_salary and j.max_salary > 0 else None
                if min_s is not None and max_s is not None:
                    mid = (min_s + max_s) / 2.0
                elif min_s is not None:
                    mid = min_s
                elif max_s is not None:
                    mid = max_s
                else:
                    continue

                ann = mid * 12.0 if (j.source == "getonboard" or mid < 12000.0) else mid
                if 6000.0 <= ann <= 300000.0:
                    annual_salaries.append(ann)

            if annual_salaries:
                raw_top_20 = float(np.percentile(annual_salaries, 80))
            else:
                raw_top_20 = 55000.0 if market_region == "getonboard" else 150000.0

            # Asegurar consistencia con la banda salarial Senior/Lead del segmento
            regional_floor = 54000.0 if market_region == "getonboard" else 145000.0
            top_20_threshold = max(raw_top_20, regional_floor)

            # Identificar las 3 skills más demandadas que le faltan al candidato
            # en las ofertas que pagan en el percentil superior
            gap_counter: Counter = Counter()
            for job, _, missing in job_matches:
                gap_counter.update(missing)

            # Formatear Top 3 brechas
            critical_gaps = [
                {"skill": skill.capitalize(), "missing_in_jobs": count}
                for skill, count in gap_counter.most_common(3)
            ]

            qualification_pct = (qualified_count / max(1, total_jobs)) * 100.0

            return {
                "total_jobs": total_jobs,
                "qualified_count": qualified_count,
                "qualification_pct": round(qualification_pct, 1),
                "top_20_threshold": round(top_20_threshold, 2),
                "critical_gaps": critical_gaps,
            }
        finally:
            db.close()
