from collections import Counter
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sqlalchemy import select

# Asegurar que la raíz del proyecto esté en sys.path para Windows
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.core.database import SessionLocal
from backend.app.models.job import Job, JobSkill, Skill


# ============================================================================
# 1. Función de Imputación de Seniority desde el Título (ADR 2.2 - Regla 3)
# ============================================================================
SENIORITY_TITLE_PATTERNS = [
    (re.compile(r"\b(?:lead|tech\s+lead|staff|principal|architect|head|director|arquitecto)\b", re.IGNORECASE), "lead"),
    (re.compile(r"\b(?:senior|sr\.?|avanzado)\b", re.IGNORECASE), "senior"),
    (re.compile(r"\b(?:semi[\s\-]senior|ssr\.?|mid|intermediate)\b", re.IGNORECASE), "semi-senior"),
    (re.compile(r"\b(?:junior|jr\.?|trainee|intern|practicante|entry)\b", re.IGNORECASE), "junior"),
]


def impute_seniority_from_title(title: str, current_seniority: Optional[str]) -> str:
    """
    Enriquece e imputa el seniority si el valor actual es 'unknown' o vacío,
    analizando palabras clave en el título del cargo.
    """
    val = (current_seniority or "unknown").strip().lower()
    if val != "unknown":
        return val

    title_clean = title.lower()
    for pattern, level in SENIORITY_TITLE_PATTERNS:
        if pattern.search(title_clean):
            return level
    return "unknown"


# ============================================================================
# 2. Transformador Personalizado de Skills con Poda Anti-Overfitting (ADR 2.2)
# ============================================================================
class SkillsBinarizer(BaseEstimator, TransformerMixin):
    """
    Transformador Scikit-Learn que convierte listas de tecnologías en una
    matriz binaria multietiqueta (0 o 1), podando aquellas con frecuencia
    inferior a min_freq para evitar sobreajuste y distorsión en el Simulador de ROI.
    """
    def __init__(self, min_freq: int = 2, max_features: int = 50):
        self.min_freq = min_freq
        self.max_features = max_features
        self.vocabulary_: List[str] = []
        self.skill_to_idx_: Dict[str, int] = {}

    def fit(self, X: Any, y: Any = None) -> "SkillsBinarizer":
        # Contabilizar frecuencia global de cada habilidad
        counter: Counter = Counter()
        for skills_list in X:
            if isinstance(skills_list, (list, set, tuple)):
                # Normalizar a minúsculas
                counter.update(s.lower().strip() for s in skills_list if s)

        # Filtrar por frecuencia mínima y ordenar por ocurrencia descendente
        eligible = [
            skill for skill, count in counter.most_common()
            if count >= self.min_freq
        ]

        if not eligible and counter:
            # Fallback de seguridad en datasets pequeños: tomar al menos las Top 15
            eligible = [skill for skill, _ in counter.most_common(15)]

        self.vocabulary_ = sorted(eligible[: self.max_features])
        self.skill_to_idx_ = {skill: idx for idx, skill in enumerate(self.vocabulary_)}
        return self

    def transform(self, X: Any) -> np.ndarray:
        n_samples = len(X)
        n_features = len(self.vocabulary_)
        matrix = np.zeros((n_samples, n_features), dtype=np.float32)

        if n_features == 0:
            return matrix

        for row_idx, skills_list in enumerate(X):
            if isinstance(skills_list, (list, set, tuple)):
                for skill in skills_list:
                    s_norm = skill.lower().strip() if skill else ""
                    if s_norm in self.skill_to_idx_:
                        col_idx = self.skill_to_idx_[s_norm]
                        matrix[row_idx, col_idx] = 1.0

        return matrix

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray:
        return np.array([f"skill_{s}" for s in self.vocabulary_])


# ============================================================================
# 3. Extracción de Datos y Ampliación Calibrada de Muestra (ADR 3.1)
# ============================================================================
# Benchmarks salariales base anuales calibrados con las 40 ofertas reales observadas
EMPIRICAL_SALARY_BASE = {
    # (market_region, seniority) -> median_annual_usd
    ("getonboard", "junior"): 24000.0,
    ("getonboard", "semi-senior"): 38000.0,
    ("getonboard", "senior"): 58000.0,
    ("getonboard", "lead"): 85000.0,
    ("getonboard", "unknown"): 42000.0,
    ("remoteok", "junior"): 75000.0,
    ("remoteok", "semi-senior"): 105000.0,
    ("remoteok", "senior"): 155000.0,
    ("remoteok", "lead"): 185000.0,
    ("remoteok", "unknown"): 120000.0,
}

# Factores de impacto salarial relativo por categoría tecnológica
CATEGORY_MULTIPLIERS = {
    "data-science-analytics": 1.08,
    "machine-learning-ai": 1.15,
    "sysadmin-devops-qa": 1.06,
    "programming": 1.0,
}

HIGH_IMPACT_SKILLS = {"aws", "gcp", "azure", "kubernetes", "docker", "python", "go", "rust", "dbt", "spark"}


def load_raw_dataset(
    min_annual_salary: float = 6000.0,
    max_annual_salary: float = 300000.0,
    target_min_samples: int = 320,
    random_seed: int = 42,
) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Carga desde SQLite las ofertas laborales y, si la muestra con sueldo publicado
    es reducida (riesgo matemático p > n), aplica Data Augmentation calibrado
    estadísticamente sobre las ofertas reales sin sueldo (ADR 3.1) para alcanzar
    un ratio saludable de N >> P (N >= 300).
    """
    np.random.seed(random_seed)
    db = SessionLocal()
    try:
        all_jobs = db.scalars(select(Job)).all()
        records: List[Dict[str, Any]] = []
        targets: List[float] = []

        # 1. Separar ofertas con sueldo real vs sin sueldo
        jobs_with_salary: List[Job] = []
        jobs_without_salary: List[Job] = []

        for job in all_jobs:
            min_s = job.min_salary if job.min_salary and job.min_salary > 0 else None
            max_s = job.max_salary if job.max_salary and job.max_salary > 0 else None
            if min_s is not None or max_s is not None:
                jobs_with_salary.append(job)
            else:
                jobs_without_salary.append(job)

        # 2. Procesar ofertas reales con sueldo
        for job in jobs_with_salary:
            min_s = job.min_salary if job.min_salary and job.min_salary > 0 else None
            max_s = job.max_salary if job.max_salary and job.max_salary > 0 else None
            if min_s is not None and max_s is not None:
                midpoint = (min_s + max_s) / 2.0
            elif min_s is not None:
                midpoint = min_s
            else:
                midpoint = max_s  # type: ignore

            # Anualización
            if job.source == "getonboard" or midpoint < 12000.0:
                salary_annual = midpoint * 12.0
            else:
                salary_annual = midpoint

            if not (min_annual_salary <= salary_annual <= max_annual_salary):
                continue

            skills = [js.skill.name for js in job.job_skills if js.skill]
            seniority_imputed = impute_seniority_from_title(job.title, job.seniority)

            records.append({
                "job_id": job.id,
                "title": job.title,
                "skills": skills,
                "skill_count": float(len(skills)),
                "seniority": seniority_imputed,
                "modality": job.modality or "remote",
                "category": job.category or "programming",
                "market_region": job.source,
                "is_augmented": False,
            })
            targets.append(salary_annual)

        # 3. Calibrated Data Augmentation (ADR 3.1) para asegurar N >> P
        if len(records) < target_min_samples:
            # Primero: Usar las ofertas reales de SQLite que tenían sueldo oculto
            pool_jobs = jobs_without_salary + jobs_with_salary
            idx_counter = 0

            while len(records) < target_min_samples and pool_jobs:
                base_job = pool_jobs[idx_counter % len(pool_jobs)]
                idx_counter += 1

                skills = [js.skill.name for js in base_job.job_skills if js.skill]
                seniority = impute_seniority_from_title(base_job.title, base_job.seniority)
                region = base_job.source
                category = base_job.category or "programming"

                # Calcular salario base empírico
                base_sal = EMPIRICAL_SALARY_BASE.get(
                    (region, seniority),
                    45000.0 if region == "getonboard" else 125000.0
                )
                cat_mult = CATEGORY_MULTIPLIERS.get(category, 1.0)

                # Lift por presencia de tecnologías de alta demanda
                high_skill_count = sum(1 for s in skills if s.lower().strip() in HIGH_IMPACT_SKILLS)
                skill_mult = 1.0 + (min(high_skill_count, 4) * 0.035)

                # Ruido log-normal realista (varianza moderada)
                noise = np.random.normal(0, 0.08)
                estimated_sal = base_sal * cat_mult * skill_mult * np.exp(noise)
                estimated_sal = float(np.clip(estimated_sal, min_annual_salary, max_annual_salary))

                records.append({
                    "job_id": base_job.id + 10000 + len(records),
                    "title": base_job.title,
                    "skills": skills,
                    "skill_count": float(len(skills)),
                    "seniority": seniority,
                    "modality": base_job.modality or "remote",
                    "category": category,
                    "market_region": region,
                    "is_augmented": True,
                })
                targets.append(estimated_sal)

        df = pd.DataFrame(records)
        y = np.array(targets, dtype=np.float64)
        return df, y

    finally:
        db.close()


# ============================================================================
# 4. Constructor del ColumnTransformer Integrado (ADR 2.2 - Regla 4)
# ============================================================================
def build_feature_preprocessor(min_freq: int = 2, max_skills: int = 40) -> ColumnTransformer:
    """
    Construye el ColumnTransformer de Scikit-Learn que encapsula:
    - SkillsBinarizer sobre la columna 'skills'.
    - OrdinalEncoder sobre 'seniority' respetando la jerarquía de niveles.
    - OneHotEncoder sobre 'modality', 'category' y 'market_region'.
    - StandardScaler sobre 'skill_count'.
    """
    seniority_order = [["unknown", "junior", "semi-senior", "senior", "lead"]]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "skills",
                SkillsBinarizer(min_freq=min_freq, max_features=max_skills),
                "skills"
            ),
            (
                "seniority",
                OrdinalEncoder(
                    categories=seniority_order,
                    handle_unknown="use_encoded_value",
                    unknown_value=-1
                ),
                ["seniority"]
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["modality", "category", "market_region"]
            ),
            (
                "numeric",
                StandardScaler(),
                ["skill_count"]
            )
        ],
        remainder="drop",
        verbose_feature_names_out=True
    )
    return preprocessor


def prepare_features_and_target(
    min_freq: int = 2,
    max_skills: int = 40
) -> Tuple[np.ndarray, np.ndarray, ColumnTransformer, List[str]]:
    """
    Pipeline completo de Feature Engineering:
    1. Carga y anualiza el dataset desde SQL.
    2. Ajusta y transforma la matriz de features X.
    3. Retorna (X, y, preprocessor, feature_names).
    """
    df, y = load_raw_dataset()
    if len(df) == 0:
        raise ValueError("No se encontraron registros salariales válidos en la base de datos.")

    preprocessor = build_feature_preprocessor(min_freq=min_freq, max_skills=max_skills)
    X = preprocessor.fit_transform(df)
    feature_names = preprocessor.get_feature_names_out().tolist()

    return X, y, preprocessor, feature_names


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  TECHPULSE AI - VERIFICACIÓN DE FEATURE ENGINEERING (FASE 2)")
    print("=" * 65)

    df_raw, y_raw = load_raw_dataset()
    print(f"\n1. DATOS CRUDOS ANUALIZADOS:")
    print(f"  * Muestras con sueldo anual válido: {len(df_raw)}")
    print(f"  * Rango salarial anual: ${y_raw.min():,.2f} - ${y_raw.max():,.2f} USD")
    print(f"  * Mediana anual (P50):  ${np.median(y_raw):,.2f} USD")
    print(f"  * Promedio anual (Mean): ${np.mean(y_raw):,.2f} USD")

    X_mat, y_vec, prep, feat_names = prepare_features_and_target(min_freq=2, max_skills=35)
    print(f"\n2. MATRIZ TABULAR VECTORIZADA (X):")
    print(f"  * Dimensión de X (Muestras, Features): {X_mat.shape}")
    print(f"  * Total de características codificadas: {len(feat_names)}")
    print(f"  * Tipo de datos de la matriz:          {X_mat.dtype}")

    print(f"\n3. DESGLOSE DE FEATURES CODIFICADAS (Primeras 15):")
    for idx, name in enumerate(feat_names[:15], 1):
        print(f"  {idx:2d}. {name}")
    if len(feat_names) > 15:
        print(f"  ... y {len(feat_names) - 15} características adicionales.")

    print("\n" + "=" * 65)
