from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import func, select

# Asegurar que la raíz del proyecto esté en sys.path para Windows
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.core.database import SessionLocal
from backend.app.models.job import Job, JobSkill, Skill
from backend.app.ml.train import MODEL_ARTIFACT_PATH


class SkillROIEngine:
    """
    Motor Matemático de Retorno de Inversión (ROI) de Habilidades Técnicas (Fase 3).
    Calcula el impacto salarial marginal contrafactual de adquirir nuevas tecnologías
    y lo cruza bidimensionalmente contra la demanda real en la base de datos SQL.
    """

    def __init__(self, artifact_path: Path = MODEL_ARTIFACT_PATH):
        if not artifact_path.exists():
            raise FileNotFoundError(
                f"No se encontró el artefacto de modelo en: {artifact_path}. "
                "Ejecuta 'python backend/app/ml/train.py' primero."
            )
        self.artifact: Dict[str, Any] = joblib.load(artifact_path)
        self.model = self.artifact["model"]
        self.preprocessor = self.artifact["preprocessor"]
        self.feature_names = self.artifact["feature_names"]
        self.ridge_weights = self.artifact.get("ridge_weights", {})

        # Extraer catálogo de skills reconocidas por el preprocesador
        skills_transformer = self.preprocessor.named_transformers_["skills"]
        self.vocabulary: List[str] = skills_transformer.vocabulary_

    def _get_market_demand(self, category: Optional[str] = None) -> Tuple[Dict[str, int], int]:
        """
        Consulta en SQLite la demanda real de cada habilidad (ofertas que la solicitan),
        opcionalmente filtrada por categoría temática.
        """
        db = SessionLocal()
        try:
            # Total de ofertas en la categoría
            total_stmt = select(func.count(Job.id))
            if category:
                total_stmt = total_stmt.where(Job.category == category)
            total_jobs = db.scalar(total_stmt) or 1

            # Conteo de ofertas por skill
            stmt = (
                select(Skill.slug, func.count(JobSkill.job_id).label("job_count"))
                .join(JobSkill, Skill.id == JobSkill.skill_id)
                .join(Job, JobSkill.job_id == Job.id)
            )
            if category:
                stmt = stmt.where(Job.category == category)
            stmt = stmt.group_by(Skill.slug)

            counts = {row[0].lower().strip(): row[1] for row in db.execute(stmt).all()}
            return counts, total_jobs
        finally:
            db.close()

    def simulate_roi(
        self,
        current_skills: List[str],
        seniority: str = "junior",
        category: str = "programming",
        market_region: str = "getonboard",
        modality: str = "remote",
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """
        Simulación Contrafactual Bidimensional de ROI (Reglas de Producto 1, 2 y 3):
        1. Predice el sueldo base con el stack actual.
        2. Simula añadir marginalmente cada skill candidata no poseída (skill_count + 1).
        3. Cruza el diferencial salarial con la demanda SQL y calcula el roi_score (0-100).
        """
        user_skills_clean = [s.lower().strip() for s in current_skills if s]
        user_skills_set = set(user_skills_clean)

        # 1. Perfil Base Actual
        base_df = pd.DataFrame([{
            "title": f"{seniority.capitalize()} Developer",
            "skills": user_skills_clean,
            "skill_count": float(len(user_skills_clean)),
            "seniority": seniority.lower(),
            "modality": modality.lower(),
            "category": category.lower(),
            "market_region": market_region.lower(),
        }])

        X_base = self.preprocessor.transform(base_df)
        base_salary_annual = float(self.model.predict(X_base)[0])
        base_salary_monthly = base_salary_annual / 12.0

        # 2. Obtener demanda del mercado real en SQL
        demand_counts, total_market_jobs = self._get_market_demand(category=category)

        # 3. Filtrar skills candidatas (aquellas en vocabulario que el usuario NO posee)
        candidates = [s for s in self.vocabulary if s not in user_skills_set]

        if not candidates:
            return {
                "base_salary_annual_usd": round(base_salary_annual, 2),
                "base_salary_monthly_usd": round(base_salary_monthly, 2),
                "recommendations": [],
            }

        simulations: List[Dict[str, Any]] = []

        # Vectorizar simulaciones en batch para alta performance
        sim_dfs: List[Dict[str, Any]] = []
        for cand in candidates:
            sim_skills = user_skills_clean + [cand]
            sim_dfs.append({
                "title": f"{seniority.capitalize()} Developer",
                "skills": sim_skills,
                "skill_count": float(len(sim_skills)),  # Regla 3: stack complexity dinámico
                "seniority": seniority.lower(),
                "modality": modality.lower(),
                "category": category.lower(),
                "market_region": market_region.lower(),
            })

        batch_sim_df = pd.DataFrame(sim_dfs)
        X_sim_batch = self.preprocessor.transform(batch_sim_df)
        predicted_batch = self.model.predict(X_sim_batch)

        for idx, cand in enumerate(candidates):
            sim_annual = float(predicted_batch[idx])
            delta_annual = max(0.0, sim_annual - base_salary_annual)

            # Si el delta salarial puro fuera muy sutil, asegurar sensibilidad con pesos Ridge
            ridge_col = f"skills__skill_{cand}"
            ridge_weight = self.ridge_weights.get(ridge_col, 0.0)
            if delta_annual < 50.0 and ridge_weight > 0:
                # Retorno mínimo estimado proporcional al peso econométrico
                delta_annual = max(delta_annual, float(ridge_weight * 3500.0))

            delta_monthly = delta_annual / 12.0
            job_count = demand_counts.get(cand, 0)
            demand_pct = (job_count / total_market_jobs) * 100.0 if total_market_jobs else 0.0

            simulations.append({
                "skill": cand,
                "display_name": cand.capitalize(),
                "simulated_annual_usd": round(sim_annual, 2),
                "delta_salary_annual_usd": round(delta_annual, 2),
                "delta_salary_monthly_usd": round(delta_monthly, 2),
                "unlocked_jobs_count": job_count,
                "demand_pct": round(demand_pct, 1),
            })

        # 4. Normalización y Cálculo de ROI Score (60% Salario + 40% Demanda)
        deltas = [s["delta_salary_annual_usd"] for s in simulations]
        demands = [s["demand_pct"] for s in simulations]

        max_delta = max(deltas) if max(deltas) > 0 else 1.0
        min_delta = min(deltas)
        max_demand = max(demands) if max(demands) > 0 else 1.0
        min_demand = min(demands)

        for s in simulations:
            # Escala 0 - 100
            norm_salary = (
                ((s["delta_salary_annual_usd"] - min_delta) / (max_delta - min_delta) * 100.0)
                if max_delta > min_delta else 50.0
            )
            norm_demand = (
                ((s["demand_pct"] - min_demand) / (max_demand - min_demand) * 100.0)
                if max_demand > min_demand else 50.0
            )

            # Fórmula Bimensional de ROI (Regla 2)
            roi_score = 0.60 * norm_salary + 0.40 * norm_demand
            s["roi_score"] = round(roi_score, 1)

            if roi_score >= 70.0:
                s["learning_priority"] = "Alta (Top ROI)"
            elif roi_score >= 40.0:
                s["learning_priority"] = "Media"
            else:
                s["learning_priority"] = "Baja / Opcional"

        # 5. Ordenar por ROI Score descendente
        simulations.sort(key=lambda x: x["roi_score"], reverse=True)

        return {
            "current_stack": user_skills_clean,
            "seniority": seniority,
            "market_region": market_region,
            "base_salary_annual_usd": round(base_salary_annual, 2),
            "base_salary_monthly_usd": round(base_salary_monthly, 2),
            "total_candidate_skills_evaluated": len(simulations),
            "recommendations": simulations[:top_n],
        }


def run_roi_demo(
    skills: Optional[List[str]] = None,
    seniority: str = "junior",
    category: str = "programming",
    market_region: str = "getonboard"
):
    """Ejecutor de demostración del motor de ROI."""
    if skills is None:
        skills = ["python", "javascript", "vue", "sql", "git"]

    engine = SkillROIEngine()
    result = engine.simulate_roi(
        current_skills=skills,
        seniority=seniority,
        category=category,
        market_region=market_region,
        top_n=8
    )

    print("\n" + "=" * 85)
    print("  TECHPULSE AI - SIMULADOR DE ROI DE SKILLS (MONETIZABLE B2C / FREEMIUM)")
    print("=" * 85)

    print(f"\n[PERFIL ANALIZADO]:")
    print(f"  * Stack Actual:     {', '.join(result['current_stack'])}")
    print(f"  * Seniority:        {result['seniority'].upper()}")
    print(f"  * Mercado/Región:   {result['market_region'].upper()}")
    print(f"  * Sueldo Base Est.: ${result['base_salary_annual_usd']:,.2f} USD/año (${result['base_salary_monthly_usd']:,.2f} USD/mes)")

    print(f"\n[TOP RECOMENDACIONES DE SKILLS PARA MAXIMIZAR SUELDO Y EMPLEABILIDAD]:")
    print(f"{'#':<3} | {'Tecnología':<18} | {'+ Sueldo Anual':<16} | {'+ Sueldo Mes':<14} | {'Ofertas':<8} | {'ROI Score':<10} | {'Prioridad'}")
    print("-" * 85)

    for idx, rec in enumerate(result["recommendations"], 1):
        delta_ann = f"+${rec['delta_salary_annual_usd']:,.2f}"
        delta_m = f"+${rec['delta_salary_monthly_usd']:,.2f}/m"
        jobs_str = f"{rec['unlocked_jobs_count']} ({rec['demand_pct']}%)"
        roi_str = f"{rec['roi_score']} / 100"
        print(f"{idx:<3} | {rec['display_name']:<18} | {delta_ann:<16} | {delta_m:<14} | {jobs_str:<8} | {roi_str:<10} | {rec['learning_priority']}")

    print("=" * 85 + "\n")


if __name__ == "__main__":
    run_roi_demo()
