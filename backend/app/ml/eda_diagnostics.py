import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy import func, select

# Asegurar que la raíz del proyecto esté en sys.path para Windows
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.core.database import SessionLocal
from backend.app.models.job import Job, JobSkill, Skill


def calculate_percentiles(values: List[float], percentiles: List[int]) -> Dict[int, float]:
    """Calcula percentiles exactos sobre una lista ordenada de valores."""
    if not values:
        return {p: 0.0 for p in percentiles}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    results = {}
    for p in percentiles:
        k = (n - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            results[p] = sorted_vals[int(k)]
        else:
            results[p] = sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)
    return results


def run_eda_diagnostics():
    """
    Script de Diagnóstico Exploratorio de Calidad de Datos (Fase 2).
    Examina volumen, distribución salarial, brecha mensual vs anual y cobertura de skills.
    """
    db = SessionLocal()
    try:
        jobs = db.scalars(select(Job)).all()
        total_jobs = len(jobs)

        if total_jobs == 0:
            print("\n[ALERTA] La base de datos no contiene ofertas. Ejecuta el pipeline ETL primero.")
            return

        # 1. Desglose por fuente
        source_counts = Counter(job.source for job in jobs)

        # 2. Análisis de presencia salarial
        jobs_with_salary: List[Job] = []
        jobs_without_salary: List[Job] = []
        salary_midpoints: List[float] = []

        for j in jobs:
            min_s = j.min_salary if j.min_salary and j.min_salary > 0 else None
            max_s = j.max_salary if j.max_salary and j.max_salary > 0 else None

            if min_s is not None or max_s is not None:
                jobs_with_salary.append(j)
                if min_s is not None and max_s is not None:
                    mid = (min_s + max_s) / 2.0
                elif min_s is not None:
                    mid = min_s
                else:
                    mid = max_s
                salary_midpoints.append(mid)
            else:
                jobs_without_salary.append(j)

        with_salary_count = len(jobs_with_salary)
        without_salary_count = len(jobs_without_salary)
        pct_with_salary = (with_salary_count / total_jobs) * 100
        pct_without_salary = (without_salary_count / total_jobs) * 100

        # 3. Estadísticas Descriptivas Salariales
        print("\n" + "=" * 70)
        print("  TECHPULSE AI - REPORTE DE AUDITORÍA Y DIAGNÓSTICO DE DATOS (EDA)")
        print("=" * 70)

        print("\n1. VOLUMEN DE DATOS ALMACENADOS")
        print(f"  * Total de ofertas en SQLite: {total_jobs}")
        for src, cnt in source_counts.items():
            print(f"    - {src.upper()}: {cnt} ofertas ({cnt / total_jobs * 100:.1f}%)")

        print("\n2. COBERTURA DE SUELDOS (VISIBLE VS. OCULTO)")
        print(f"  * Ofertas con sueldo publicado (> 0): {with_salary_count} ({pct_with_salary:.1f}%)")
        print(f"  * Ofertas con sueldo oculto/nulo:     {without_salary_count} ({pct_without_salary:.1f}%)")

        if salary_midpoints:
            pcts = calculate_percentiles(salary_midpoints, [25, 50, 75])
            min_val = min(salary_midpoints)
            max_val = max(salary_midpoints)
            mean_val = sum(salary_midpoints) / len(salary_midpoints)

            # Detección de escala (Mensual vs Anual)
            monthly_candidates = [s for s in salary_midpoints if s < 15000]
            annual_candidates = [s for s in salary_midpoints if s >= 15000]

            print("\n3. ESTADÍSTICAS DESCRIPTIVAS SALARIALES (EN USD CRUDA)")
            print(f"  * Mínimo (Min):          ${min_val:,.2f}")
            print(f"  * Percentil 25 (P25):     ${pcts[25]:,.2f}")
            print(f"  * Mediana (P50):         ${pcts[50]:,.2f}")
            print(f"  * Promedio (Mean):       ${mean_val:,.2f}")
            print(f"  * Percentil 75 (P75):     ${pcts[75]:,.2f}")
            print(f"  * Máximo (Max):          ${max_val:,.2f}")

            print("\n  [HALLAZGO CRÍTICO DE CALIDAD DE DATOS - ESCALAS TEMPORALES]:")
            print(f"  * Registros < $15,000 USD (Probable sueldo MENSUAL - típico LatAm/GetOnBoard): {len(monthly_candidates)}")
            print(f"  * Registros >= $15,000 USD (Probable sueldo ANUAL - típico Global/RemoteOK):  {len(annual_candidates)}")

            if monthly_candidates and annual_candidates:
                print("  -> ADVERTENCIA: Existen sueldos mensuales mezclados con sueldos anuales.")
                print("     El pipeline de Feature Engineering DEBE normalizar a escala anual unificada (ej. mensual * 12).")

            # 4. Distribución por Seniority en ofertas con sueldo
            seniority_counts = Counter(j.seniority for j in jobs_with_salary)
            print("\n4. DISTRIBUCIÓN DE SENIORITY (EN OFERTAS CON SUELDO)")
            for sen, count in seniority_counts.most_common():
                print(f"  * {sen:<15}: {count:2d} ofertas ({count / with_salary_count * 100:.1f}%)")

            # 5. Top 15 Skills en ofertas con sueldo
            valid_job_ids = [j.id for j in jobs_with_salary]
            skill_stmt = (
                select(Skill.name, func.count(JobSkill.skill_id).label("freq"))
                .join(JobSkill, Skill.id == JobSkill.skill_id)
                .where(JobSkill.job_id.in_(valid_job_ids))
                .group_by(Skill.name)
                .order_by(func.count(JobSkill.skill_id).desc())
                .limit(15)
            )
            top_skills = db.execute(skill_stmt).all()

            print("\n5. TOP 15 SKILLS MÁS DEMANDADAS (EN OFERTAS CON SUELDO)")
            if top_skills:
                for idx, (skill_name, freq) in enumerate(top_skills, 1):
                    bar = "#" * math.ceil(freq / max(1, top_skills[0][1]) * 15)
                    print(f"  {idx:2d}. {skill_name:<18} | {freq:2d} ofertas | {bar}")
            else:
                print("  * No se encontraron skills asociadas a las ofertas con sueldo.")

        print("\n" + "=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_eda_diagnostics()
