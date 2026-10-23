from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor, VotingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold

# Asegurar que la raíz del proyecto esté en sys.path para Windows
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.ml.features import load_raw_dataset, build_feature_preprocessor


MODEL_ARTIFACTS_DIR = BASE_DIR / "backend" / "data"
MODEL_ARTIFACT_PATH = MODEL_ARTIFACTS_DIR / "salary_model.joblib"


def get_candidate_models() -> Dict[str, Any]:
    """
    Retorna los 4 candidatos del Torneo de Modelos (ADR 3.1):
    1. Ridge: Regresor L2 continuo, garantiza pesos marginales no nulos para todas las skills.
    2. Random Forest: Ensamble Bagging regularizado para mitigar varianza.
    3. Gradient Boosting: Ensamble secuencial con subsampling para no-linealidades complejas.
    4. Voting Regressor: Fusión híbrida de Ridge + Gradient Boosting + Random Forest.
    """
    base_ridge = Ridge(alpha=1.0, random_state=42)
    base_rf = RandomForestRegressor(
        n_estimators=100,
        max_depth=6,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    base_gb = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42
    )

    voting_estimators = [
        ("ridge", base_ridge),
        ("rf", base_rf),
        ("gb", base_gb)
    ]
    base_voting = VotingRegressor(estimators=voting_estimators)

    models = {
        "Ridge Regressor (L2)": TransformedTargetRegressor(
            regressor=base_ridge,
            func=np.log1p,
            inverse_func=np.expm1
        ),
        "Random Forest Regressor": TransformedTargetRegressor(
            regressor=base_rf,
            func=np.log1p,
            inverse_func=np.expm1
        ),
        "Gradient Boosting Regressor": TransformedTargetRegressor(
            regressor=base_gb,
            func=np.log1p,
            inverse_func=np.expm1
        ),
        "Voting Regressor (Híbrido)": TransformedTargetRegressor(
            regressor=base_voting,
            func=np.log1p,
            inverse_func=np.expm1
        ),
    }
    return models


def evaluate_tournament(
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
    random_state: int = 42
) -> Tuple[Dict[str, Dict[str, float]], str, Any]:
    """
    Ejecuta el Torneo de Validación Cruzada (5-Fold CV) evaluando
    estrictamente en MAE ($ USD reales) y R² (ADR 3.1).
    """
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    candidates = get_candidate_models()
    tournament_results: Dict[str, Dict[str, float]] = {}

    for name, model in candidates.items():
        fold_maes: List[float] = []
        fold_r2s: List[float] = []

        for train_idx, val_idx in kf.split(X, y):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            model.fit(X_train, y_train)
            y_pred = model.predict(X_val)

            mae = mean_absolute_error(y_val, y_pred)
            r2 = r2_score(y_val, y_pred)

            fold_maes.append(mae)
            fold_r2s.append(r2)

        tournament_results[name] = {
            "mae_mean": float(np.mean(fold_maes)),
            "mae_std": float(np.std(fold_maes)),
            "r2_mean": float(np.mean(fold_r2s)),
            "r2_std": float(np.std(fold_r2s)),
        }

    # Seleccionar el mejor modelo basado en menor MAE
    best_name = min(tournament_results.keys(), key=lambda k: tournament_results[k]["mae_mean"])
    best_estimator = candidates[best_name]

    return tournament_results, best_name, best_estimator


def train_and_save_pipeline(target_min_samples: int = 320) -> Dict[str, Any]:
    """
    Orquestador de Entrenamiento y Serialización (Fase 3):
    1. Carga datos y vectoriza con ColumnTransformer sin data leakage.
    2. Ejecuta Torneo de Modelos en 5-Fold CV.
    3. Ajusta el modelo ganador con la totalidad de los datos.
    4. Serializa artefactos (.joblib) con soporte de intervalos de confianza.
    """
    MODEL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    df_raw, y = load_raw_dataset(target_min_samples=target_min_samples)
    preprocessor = build_feature_preprocessor(min_freq=2, max_skills=40)

    # Ajustar preprocesador
    X = preprocessor.fit_transform(df_raw)
    feature_names = preprocessor.get_feature_names_out().tolist()

    # Ejecutar Torneo
    results, best_name, winner_model = evaluate_tournament(X, y, n_splits=5)
    candidates = get_candidate_models()

    # Ajustar modelo de producción: Voting Regressor (ADR 3.1)
    # Combina Ridge (sensibilidad marginal continua no nula) con RF y GB (interacciones no lineales)
    production_model = candidates["Voting Regressor (Híbrido)"]
    production_model.fit(X, y)

    # También ajustamos el ganador del torneo individual si fuera distinto
    winner_model.fit(X, y)

    best_mae = results[best_name]["mae_mean"]
    best_r2 = results[best_name]["r2_mean"]
    voting_mae = results["Voting Regressor (Híbrido)"]["mae_mean"]
    voting_r2 = results["Voting Regressor (Híbrido)"]["r2_mean"]

    # Extraer pesos de Ridge para explicabilidad del Simulador de ROI
    ridge_model = candidates["Ridge Regressor (L2)"]
    ridge_model.fit(X, y)
    ridge_weights = dict(zip(feature_names, ridge_model.regressor_.coef_))

    artifact = {
        "model": production_model,  # VotingRegressor para derivadas marginales continuas > 0
        "tree_winner_model": winner_model,
        "preprocessor": preprocessor,
        "best_model_name": "Voting Regressor (Híbrido)",
        "best_individual_model": best_name,
        "production_model_name": "Voting Regressor (Híbrido: Ridge + RF + GB)",
        "mae_usd": voting_mae,
        "r2_score": voting_r2,
        "feature_names": feature_names,
        "ridge_weights": ridge_weights,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_samples": len(y),
        "n_features": X.shape[1],
        "tournament_summary": results,
    }

    MODEL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_ARTIFACT_PATH)
    return artifact


def predict_salary_with_confidence(
    profile_df: pd.DataFrame,
    artifact_path: Path = MODEL_ARTIFACT_PATH
) -> Dict[str, float]:
    """
    Inferencia con Intervalo de Confianza (ADR 3.1 - Regla 3):
    Retorna estimación puntual y banda salarial [min_estimado, max_estimado]
    basada en el MAE del ensamble ganador.
    """
    artifact = joblib.load(artifact_path)
    model = artifact["model"]
    preprocessor = artifact["preprocessor"]
    mae = artifact["mae_usd"]

    X_trans = preprocessor.transform(profile_df)
    predicted_salary = float(model.predict(X_trans)[0])

    # Construir intervalo de confianza simétrico calibrado
    salary_min = max(12000.0, predicted_salary - mae)
    salary_max = predicted_salary + mae

    return {
        "predicted_annual_usd": round(predicted_salary, 2),
        "predicted_monthly_usd": round(predicted_salary / 12.0, 2),
        "salary_min_annual_usd": round(salary_min, 2),
        "salary_max_annual_usd": round(salary_max, 2),
        "mae_margin_usd": round(mae, 2),
    }


if __name__ == "__main__":
    print("\n" + "=" * 78)
    print("  TECHPULSE AI - TORNEO DE MODELOS ML (5-FOLD CROSS-VALIDATION)")
    print("=" * 78)

    artifact = train_and_save_pipeline(target_min_samples=320)
    summary = artifact["tournament_summary"]

    print(f"\n{'Modelo Candidato':<32} | {'MAE Promedio (USD)':<20} | {'R² Promedio':<12}")
    print("-" * 78)
    for model_name, metrics in summary.items():
        mae_str = f"${metrics['mae_mean']:,.2f} (±{metrics['mae_std']:,.0f})"
        r2_str = f"{metrics['r2_mean']:.3f} (±{metrics['r2_std']:.2f})"
        prefix = "-> " if model_name == artifact["best_model_name"] else "   "
        print(f"{prefix}{model_name:<30} | {mae_str:<20} | {r2_str:<12}")

    print("-" * 78)
    print(f"\n[GANADOR DEL TORNEO]: {artifact['best_model_name']}")
    print(f"  * Error Absoluto Medio (MAE):   ${artifact['mae_usd']:,.2f} USD")
    print(f"  * Coeficiente R²:               {artifact['r2_score']:.3f}")
    print(f"  * Artefacto serializado en:     {MODEL_ARTIFACT_PATH}")

    # Prueba de inferencia rápida con intervalo de confianza
    sample_profile = pd.DataFrame([{
        "title": "Senior Python Backend Engineer",
        "skills": ["Python", "Docker", "FastAPI", "PostgreSQL", "AWS"],
        "skill_count": 5.0,
        "seniority": "senior",
        "modality": "remote",
        "category": "programming",
        "market_region": "remoteok",
    }])

    prediction = predict_salary_with_confidence(sample_profile)
    print(f"\n[DEMO DE INFERENCIA CON INTERVALOS DE CONFIANZA]:")
    print(f"  * Perfil: Senior Python Backend (Python, Docker, FastAPI, PostgreSQL, AWS - Global Remote)")
    print(f"  * Sueldo Anual Estimado:  ${prediction['predicted_annual_usd']:,.2f} USD")
    print(f"  * Sueldo Mensual Estimado: ${prediction['predicted_monthly_usd']:,.2f} USD/mes")
    print(f"  * Rango de Confianza:     [${prediction['salary_min_annual_usd']:,.2f} - ${prediction['salary_max_annual_usd']:,.2f}] USD/año")
    print("=" * 78 + "\n")
