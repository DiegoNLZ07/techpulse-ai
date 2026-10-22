import asyncio
from datetime import datetime, timezone
import logging
from typing import AsyncGenerator, List, Optional
from bs4 import BeautifulSoup
import httpx

from backend.app.etl.schemas import RawJobData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("etl.connectors")


def clean_html(raw_html: str) -> str:
    """
    Sanitiza y limpia contenido HTML (ADR 1.2), extrayendo texto plano
    y eliminando scripts, estilos y espacios redundantes.
    """
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    # Remover scripts y estilos si existieran
    for element in soup(["script", "style"]):
        element.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # Compactar espacios en blanco consecutivos
    return " ".join(text.split())


class GetOnBoardConnector:
    """
    Conector asíncrono para la API v0 de Get On Board (Mercado Latinoamericano).
    Docs: https://www.getonbrd.com/api/v0/
    """
    BASE_URL = "https://www.getonbrd.com/api/v0"
    TARGET_CATEGORIES = [
        "programming",
        "data-science-analytics",
        "sysadmin-devops-qa",
        "machine-learning-ai",
    ]

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client

    async def fetch_category_page(
        self,
        client: httpx.AsyncClient,
        category: str,
        page: int = 1,
        per_page: int = 100
    ) -> List[RawJobData]:
        url = f"{self.BASE_URL}/categories/{category}/jobs"
        params = {
            "per_page": per_page,
            "page": page,
            "expand": '["company"]'
        }
        headers = {"Accept": "application/json"}
        
        try:
            response = await client.get(url, params=params, headers=headers, timeout=20.0)
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.error(f"Error consultando Get On Board ({category}, pag {page}): {e}")
            return []

        jobs: List[RawJobData] = []
        for item in payload.get("data", []):
            attrs = item.get("attributes", {})
            company_data = attrs.get("company", {}).get("data", {}).get("attributes", {})
            
            raw_desc = (
                (attrs.get("description_headline") or "") + "\n\n" +
                (attrs.get("description") or "") + "\n\n" +
                (attrs.get("projects") or "")
            )
            cleaned = clean_html(raw_desc)
            
            # Normalizar modalidad
            remote_modality = attrs.get("remote_modality", "no_remote")
            if remote_modality in ("full", "hybrid_optional", "remote_local"):
                modality = "remote" if remote_modality == "full" else "hybrid"
            else:
                modality = "onsite"

            # Parsear fecha de publicación
            pub_date = None
            if pub_timestamp := attrs.get("published_at"):
                try:
                    pub_date = datetime.fromtimestamp(pub_timestamp, tz=timezone.utc)
                except Exception:
                    pass

            job = RawJobData(
                source="getonboard",
                external_id=str(item.get("id")),
                title=attrs.get("title", "Sin título"),
                company=company_data.get("name", "Confidencial"),
                raw_description=raw_desc,
                clean_description=cleaned,
                location=attrs.get("country_code"),
                modality=modality,
                category=category,
                min_salary=attrs.get("min_salary"),
                max_salary=attrs.get("max_salary"),
                salary_currency="USD",
                url=item.get("links", {}).get("public_url", ""),
                published_at=pub_date
            )
            jobs.append(job)

        return jobs


class RemoteOKConnector:
    """
    Conector asíncrono para la API de RemoteOK (Mercado Global Remoto).
    Docs: https://remoteok.com/api
    Requiere User-Agent descriptivo obligatorio.
    """
    BASE_URL = "https://remoteok.com/api"
    HEADERS = {
        "User-Agent": "TechPulseAI/1.0 (Educational SaaS Ingestion; contact: diegonicolaslobossalazar7@gmail.com)",
        "Accept": "application/json"
    }

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client

    async def fetch_jobs(self, client: httpx.AsyncClient, limit: int = 100) -> List[RawJobData]:
        try:
            response = await client.get(self.BASE_URL, headers=self.HEADERS, timeout=25.0)
            response.raise_for_status()
            raw_items = response.json()
        except Exception as e:
            logger.error(f"Error consultando RemoteOK API: {e}")
            return []

        jobs: List[RawJobData] = []
        for item in raw_items:
            # El primer elemento de RemoteOK suele ser un aviso legal/metadata
            if not isinstance(item, dict) or "id" not in item:
                continue

            # Filtrar vacantes técnicas relevantes
            tags = [t.lower() for t in item.get("tags", [])]
            tech_tags = {"dev", "engineer", "software", "python", "javascript", "react", "backend", "frontend", "data", "ml", "devops"}
            if not any(tag in tech_tags for tag in tags):
                continue

            raw_desc = item.get("description", "")
            cleaned = clean_html(raw_desc)

            # Extraer sueldos si están reportados numéricamente
            min_salary = None
            max_salary = None
            try:
                if s_min := item.get("salary_min"):
                    min_salary = float(s_min) if float(s_min) > 0 else None
                if s_max := item.get("salary_max"):
                    max_salary = float(s_max) if float(s_max) > 0 else None
            except (ValueError, TypeError):
                pass

            # Parsear fecha ISO
            pub_date = None
            if date_str := item.get("date"):
                try:
                    pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            # Inferencia de categoría
            category = "programming"
            if any(t in tags for t in ("data", "data-science", "ai", "machine-learning")):
                category = "data-science-analytics"
            elif any(t in tags for t in ("devops", "sysadmin", "cloud", "qa")):
                category = "sysadmin-devops-qa"

            url = item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id')}"

            job = RawJobData(
                source="remoteok",
                external_id=str(item.get("id")),
                title=item.get("position", "Sin título"),
                company=item.get("company", "Confidencial"),
                raw_description=raw_desc,
                clean_description=cleaned,
                location=item.get("location") or "Worldwide Remote",
                modality="remote",
                category=category,
                min_salary=min_salary,
                max_salary=max_salary,
                salary_currency="USD",
                url=url,
                published_at=pub_date
            )
            jobs.append(job)
            if len(jobs) >= limit:
                break

        return jobs
