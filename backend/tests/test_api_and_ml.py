import io
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient

# Asegurar path para imports en Windows
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.main import app
from backend.app.ml.train import MODEL_ARTIFACT_PATH
from backend.app.ml.roi_engine import SkillROIEngine


# Fixture de TestClient con lifespan activo
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


# ============================================================================
# 1. Tests de Salud y Market Pulse (Estructura y Limpieza de Seniority)
# ============================================================================
def test_root_health_check(client):
    """Verifica que el endpoint raíz responda con estado online y metadata de la plataforma."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "TechPulse AI" in data["platform"]


def test_market_pulse_structure_and_no_unknown_seniority(client):
    """
    Verifica que /market-pulse devuelva métricas agregadas válidas y que
    la regla de limpieza garantice que 'unknown' NO aparezca en seniority_distribution.
    """
    response = client.get("/api/v1/market-pulse")
    assert response.status_code == 200
    data = response.json()

    assert data["total_jobs"] > 0
    assert data["jobs_with_salary"] > 0
    assert 0 <= data["salary_coverage_pct"] <= 100
    assert data["median_salary_annual_usd"] > 0
    assert len(data["top_skills_by_demand"]) > 0

    seniority_dist = data.get("seniority_distribution", {})
    assert "unknown" not in seniority_dist, "La etiqueta 'unknown' no debe exponerse en el dashboard"
    assert any(k in seniority_dist for k in ["senior", "lead", "semi-senior", "junior"])


# ============================================================================
# 2. Tests de Inferencia ML en /predict-offer (Coherencia y Gradiente Seniority)
# ============================================================================
def test_predict_offer_salary_and_seniority_gradient(client):
    """
    Verifica que la inferencia ML sea económicamente coherente:
    Un perfil Senior debe predecir un salario significativamente superior a un perfil Junior
    con las mismas tecnologías y en el mismo mercado.
    """
    base_skills = "Python, Docker, SQL, AWS, FastAPI"
    
    junior_payload = {
        "title": "Junior Backend Developer",
        "description": f"Junior role requiring: {base_skills}",
        "seniority": "junior",
        "category": "programming",
        "market_region": "getonboard",
        "modality": "remote"
    }
    
    senior_payload = {
        "title": "Senior Backend Developer",
        "description": f"Senior role requiring: {base_skills}",
        "seniority": "senior",
        "category": "programming",
        "market_region": "getonboard",
        "modality": "remote"
    }

    resp_junior = client.post("/api/v1/predict-offer", json=junior_payload)
    resp_senior = client.post("/api/v1/predict-offer", json=senior_payload)

    assert resp_junior.status_code == 200
    assert resp_senior.status_code == 200

    data_jr = resp_junior.json()
    data_sr = resp_senior.json()

    # Salarios positivos y realistas
    assert data_jr["predicted_annual_usd"] > 10000.0
    assert data_sr["predicted_annual_usd"] > 10000.0

    # Rango de confianza acotado (min < predicho < max)
    assert data_jr["confidence_range_annual_usd"][0] < data_jr["predicted_annual_usd"] < data_jr["confidence_range_annual_usd"][1]
    assert data_sr["confidence_range_annual_usd"][0] < data_sr["predicted_annual_usd"] < data_sr["confidence_range_annual_usd"][1]

    # Coherencia económica: Senior > Junior
    assert data_sr["predicted_annual_usd"] > data_jr["predicted_annual_usd"], (
        f"Senior ({data_sr['predicted_annual_usd']}) debe ser mayor a Junior ({data_jr['predicted_annual_usd']})"
    )


# ============================================================================
# 3. Tests de Motor de ROI en /career-roi (Derivadas Continuas y No-Vacías)
# ============================================================================
def test_career_roi_continuous_lift_and_ranking(client):
    """
    Verifica que el motor de ROI retorne recomendaciones personalizadas,
    sin skills duplicadas de las actuales y con ROI score > 0.
    """
    current_skills = ["python", "javascript", "vue", "sql", "git"]
    roi_payload = {
        "current_skills": current_skills,
        "seniority": "junior",
        "category": "programming",
        "market_region": "getonboard",
        "top_n": 5
    }

    response = client.post("/api/v1/career-roi", json=roi_payload)
    assert response.status_code == 200
    data = response.json()

    assert data["seniority"] == "junior"
    assert data["market_region"] == "getonboard"
    
    recommendations = data["recommendations"]
    assert 1 <= len(recommendations) <= 5

    for rec in recommendations:
        assert rec["skill"] not in current_skills
        assert rec["roi_score"] > 0.0
        assert rec["delta_salary_annual_usd"] >= 0.0
        assert "learning_priority" in rec


# ============================================================================
# 4. Tests de Auditor de CV en /audit-cv (Seguridad de Carga y PDF Válido)
# ============================================================================
def test_cv_auditor_rejects_non_pdf_file(client):
    """Verifica que el endpoint rechace con HTTP 400 archivos que no sean PDF (Seguridad de Upload)."""
    fake_txt = io.BytesIO(b"Este es un archivo de texto simple y no un PDF.")
    files = {"file": ("curriculum.txt", fake_txt, "text/plain")}
    data = {"category": "programming", "market_region": "getonboard"}

    response = client.post("/api/v1/audit-cv", files=files, data=data)
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_cv_auditor_rejects_spoofed_pdf_magic_bytes(client):
    """Verifica que rechace archivos con extensión .pdf pero sin cabecera binaria %PDF-."""
    spoofed = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00FakePEHeader")
    files = {"file": ("curriculum.pdf", spoofed, "application/pdf")}
    data = {"category": "programming", "market_region": "getonboard"}

    response = client.post("/api/v1/audit-cv", files=files, data=data)
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_cv_auditor_processes_valid_pdf(client):
    """Verifica que un PDF estructurado válido sea auditado y genere valorización y gaps."""
    valid_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        b"4 0 obj << /Length 120 >> stream\n"
        b"BT /F1 12 Tf 50 700 Td (Senior Python Backend Developer with AWS Docker SQL Kubernetes PostgreSQL) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000244 00000 n \n"
        b"0000000416 00000 n \n"
        b"trailer << /Size 6 /Root 1 0 R >>\n"
        b"startxref\n493\n%%EOF\n"
    )
    files = {"file": ("diego_cv.pdf", io.BytesIO(valid_pdf), "application/pdf")}
    data = {"category": "programming", "market_region": "getonboard"}

    response = client.post("/api/v1/audit-cv", files=files, data=data)
    assert response.status_code == 200
    result = response.json()

    assert result["candidate_profile"]["detected_seniority"] in ["SENIOR", "LEAD", "SEMI-SENIOR", "JUNIOR"]
    assert len(result["candidate_profile"]["detected_skills"]) > 0
    assert result["market_valuation"]["estimated_annual_usd"] > 0
    assert result["market_matching"]["top_20_percent_salary_threshold_usd"] > 0
    assert len(result["market_matching"]["critical_gaps_for_top_tier"]) > 0


# ============================================================================
# 5. Tests Unitarios de Machine Learning (SkillROIEngine y Penalización de Liquidez)
# ============================================================================
def test_roi_engine_liquidity_penalty():
    """
    Verifica que el motor de ROI aplique la penalización de liquidez (Regla 1 - Fase 4)
    para habilidades con 0 o 1 ofertas de empleo activas en SQLite.
    """
    engine = SkillROIEngine(MODEL_ARTIFACT_PATH)
    res = engine.simulate_roi(
        current_skills=["python", "javascript"],
        seniority="junior",
        category="programming",
        market_region="getonboard",
        top_n=10
    )
    recommendations = res["recommendations"]

    assert len(recommendations) > 0
    # Toda habilidad debe tener un delta salarial continuo mayor a cero
    for rec in recommendations:
        assert rec["delta_salary_annual_usd"] > 0.0, f"Skill {rec['skill']} tiene delta cero"
        
        # Si no tiene ofertas en el mercado, su score debe haber sido penalizado fuertemente
        if rec["unlocked_jobs_count"] == 0:
            assert rec["roi_score"] <= 50.0, f"Skill {rec['skill']} sin liquidez no debe tener ROI alto"
