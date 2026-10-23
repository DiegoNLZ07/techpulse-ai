from pathlib import Path
import sys

# Asegurar que la raíz del proyecto esté en sys.path para Windows
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from backend.main import app

def run_verification():
    print("\n" + "=" * 65)
    print("  TECHPULSE AI - VERIFICACIÓN DE ENDPOINTS FASTAPI (FASE 4)")
    print("=" * 65)

    with TestClient(app) as client:
        # 1. Health & Root
        r_root = client.get("/")
        print(f"1. [GET /] Status: {r_root.status_code} | Platform: {r_root.json().get('platform')}")
        assert r_root.status_code == 200, "Error en GET /"

        # 2. Market Pulse
        r_pulse = client.get("/api/v1/market-pulse")
        print(f"2. [GET /api/v1/market-pulse] Status: {r_pulse.status_code} | Total Ofertas: {r_pulse.json().get('total_jobs')}")
        assert r_pulse.status_code == 200, "Error en GET /market-pulse"

        # 3. Predict Offer
        predict_payload = {
            "title": "Senior Fullstack Engineer",
            "description": "Looking for a Senior Python and React developer with Docker and AWS experience.",
            "seniority": "senior",
            "category": "programming",
            "market_region": "getonboard",
            "modality": "remote"
        }
        r_pred = client.post("/api/v1/predict-offer", json=predict_payload)
        pred_val = r_pred.json().get("predicted_annual_usd", 0)
        print(f"3. [POST /api/v1/predict-offer] Status: {r_pred.status_code} | Sueldo Predicho: ${pred_val:,.2f} USD")
        assert r_pred.status_code == 200, "Error en POST /predict-offer"

        # 4. Career ROI
        roi_payload = {
            "current_skills": ["python", "javascript", "vue", "sql", "git"],
            "seniority": "junior",
            "category": "programming",
            "market_region": "getonboard",
            "top_n": 3
        }
        r_roi = client.post("/api/v1/career-roi", json=roi_payload)
        top_skill = r_roi.json().get("recommendations", [{}])[0].get("display_name", "N/A")
        print(f"4. [POST /api/v1/career-roi] Status: {r_roi.status_code} | Top 1 Skill Recomendada: {top_skill}")
        assert r_roi.status_code == 200, "Error en POST /career-roi"

        # 5. Audit CV (PDF upload)
        pdf_content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 180 >> stream
BT
/F1 12 Tf
72 712 Td
(Junior Developer with Python, JavaScript, Vue, SQL, PostgreSQL and Git experience.) Tj
ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000476 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
555
%%EOF"""
        files = {"file": ("my_cv.pdf", pdf_content, "application/pdf")}
        data = {"category": "programming", "market_region": "getonboard"}
        r_cv = client.post("/api/v1/audit-cv", files=files, data=data)
        cv_val = r_cv.json().get("market_valuation", {}).get("estimated_annual_usd", 0)
        print(f"5. [POST /api/v1/audit-cv] Status: {r_cv.status_code} | Valorizacion CV: ${cv_val:,.2f} USD")
        assert r_cv.status_code == 200, "Error en POST /audit-cv"

    print("=" * 65)
    print("TODOS LOS ENDPOINTS DE FASTAPI HAN SIDO VERIFICADOS CON EXITO")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    run_verification()
