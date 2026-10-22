import hashlib
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from backend.app.etl.schemas import (
    BatchEnrichmentResponse,
    ExtractedSkill,
    JobEnrichmentResult,
    RawJobData,
)

logger = logging.getLogger("etl.extractor")

# ============================================================================
# Catálogo Exhaustivo de Expresiones Regulares para Tecnologías TI (Fallback)
# ============================================================================
TECH_CATALOG: List[Tuple[str, str, str]] = [
    # (regex_pattern, display_name, category)
    # Lenguajes
    (r"\bpython\b", "Python", "language"),
    (r"\b(?:javascript|js)\b", "JavaScript", "language"),
    (r"\b(?:typescript|ts)\b", "TypeScript", "language"),
    (r"\bjava\b", "Java", "language"),
    (r"(?:\bc\+\+|\bcpp\b)", "C++", "language"),
    (r"(?:\bc\#|\bcsharp\b)", "C#", "language"),
    (r"\b(?:golang|go)\b", "Go", "language"),
    (r"\brust\b", "Rust", "language"),
    (r"\bphp\b", "PHP", "language"),
    (r"\bruby\b", "Ruby", "language"),
    (r"\bswift\b", "Swift", "language"),
    (r"\bkotlin\b", "Kotlin", "language"),
    (r"\bscala\b", "Scala", "language"),
    (r"\bsql\b", "SQL", "language"),
    (r"\b(?:bash|shell)\b", "Bash", "language"),
    (r"\bhtml(?:5)?\b", "HTML", "language"),
    (r"\bcss(?:3)?\b", "CSS", "language"),

    # Frameworks & Librerías
    (r"\b(?:react|reactjs|react\.js)\b", "React", "framework"),
    (r"\b(?:vue|vuejs|vue\.js)\b", "Vue.js", "framework"),
    (r"\bangular\b", "Angular", "framework"),
    (r"\bnext\.?js\b", "Next.js", "framework"),
    (r"\bnuxt\.?js\b", "Nuxt.js", "framework"),
    (r"\bnode(?:\.js)?\b", "Node.js", "framework"),
    (r"\bexpress(?:\.js)?\b", "Express", "framework"),
    (r"\bnest(?:\.js)?\b", "NestJS", "framework"),
    (r"\bfastapi\b", "FastAPI", "framework"),
    (r"\bdjango\b", "Django", "framework"),
    (r"\bflask\b", "Flask", "framework"),
    (r"\bspring(?:\s+boot)?\b", "Spring Boot", "framework"),
    (r"\bruby\s+on\s+rails\b", "Rails", "framework"),
    (r"\blaravel\b", "Laravel", "framework"),
    (r"(?:\b\.net\b|\bdotnet\b)", ".NET", "framework"),
    (r"\bflutter\b", "Flutter", "framework"),
    (r"\breact\s+native\b", "React Native", "framework"),

    # Bases de Datos
    (r"\b(?:postgres|postgresql|psql)\b", "PostgreSQL", "database"),
    (r"\bmysql\b", "MySQL", "database"),
    (r"\bsqlite\b", "SQLite", "database"),
    (r"\bmongodb\b", "MongoDB", "database"),
    (r"\bredis\b", "Redis", "database"),
    (r"\bcassandra\b", "Cassandra", "database"),
    (r"\belasticsearch\b", "Elasticsearch", "database"),
    (r"\bdynamodb\b", "DynamoDB", "database"),
    (r"\boracle\b", "Oracle", "database"),

    # Cloud & DevOps
    (r"\b(?:aws|amazon\s+web\s+services)\b", "AWS", "cloud"),
    (r"\b(?:azure|microsoft\s+azure)\b", "Azure", "cloud"),
    (r"\b(?:gcp|google\s+cloud)\b", "GCP", "cloud"),
    (r"\bdocker\b", "Docker", "devops"),
    (r"\b(?:kubernetes|k8s)\b", "Kubernetes", "devops"),
    (r"\bterraform\b", "Terraform", "devops"),
    (r"\bansible\b", "Ansible", "devops"),
    (r"\bjenkins\b", "Jenkins", "devops"),
    (r"\bgitlab(?:\s+ci)?\b", "GitLab CI", "devops"),
    (r"\bgithub\s+actions\b", "GitHub Actions", "devops"),
    (r"\blinux\b", "Linux", "devops"),
    (r"\bkafka\b", "Kafka", "devops"),
    (r"\brabbitmq\b", "RabbitMQ", "devops"),

    # Data Science & Machine Learning
    (r"\bpandas\b", "Pandas", "data_ml"),
    (r"\bnumpy\b", "NumPy", "data_ml"),
    (r"\b(?:scikit-learn|sklearn)\b", "Scikit-Learn", "data_ml"),
    (r"\btensorflow\b", "TensorFlow", "data_ml"),
    (r"\bpytorch\b", "PyTorch", "data_ml"),
    (r"\bspark\b", "Apache Spark", "data_ml"),
    (r"\bairflow\b", "Apache Airflow", "data_ml"),
    (r"\bdbt\b", "dbt", "data_ml"),
    (r"\btableau\b", "Tableau", "data_ml"),
    (r"\bpower\s*bi\b", "Power BI", "data_ml"),
    (r"\bxgboost\b", "XGBoost", "data_ml"),
    (r"\blightgbm\b", "LightGBM", "data_ml"),
    (r"\bhugging\s*face\b", "Hugging Face", "data_ml"),
]

# Compilación de patrones Regex para alta performance
COMPILED_TECH_PATTERNS = [
    (re.compile(pat, re.IGNORECASE), name, cat) for pat, name, cat in TECH_CATALOG
]

# Patrones para inferencia de Seniority
SENIORITY_PATTERNS = [
    (re.compile(r"\b(?:lead|tech\s+lead|staff|principal|architect|arquitecto)\b", re.IGNORECASE), "lead"),
    (re.compile(r"\b(?:senior|sr\.?|avanzado)\b", re.IGNORECASE), "senior"),
    (re.compile(r"\b(?:semi[\s\-]senior|ssr\.?|mid|intermediate)\b", re.IGNORECASE), "semi-senior"),
    (re.compile(r"\b(?:junior|jr\.?|trainee|entry|intern|practicante)\b", re.IGNORECASE), "junior"),
]

# Patrones para inferencia de Modalidad
MODALITY_PATTERNS = [
    (re.compile(r"\b(?:remote|remoto|teletrabajo|100%\s+remoto|work\s+from\s+home)\b", re.IGNORECASE), "remote"),
    (re.compile(r"\b(?:hybrid|híbrido|hibrido)\b", re.IGNORECASE), "hybrid"),
    (re.compile(r"\b(?:onsite|on-site|presencial)\b", re.IGNORECASE), "onsite"),
]


class HybridSkillExtractor:
    """
    Extractor Híbrido de Skills y Metadatos Laborales (ADR 1.2).
    - Motor Principal: Google Gemini 2.5 Flash mediante SDK oficial google-genai
      con Micro-Batching y Structured Outputs Pydantic.
    - Motor Fallback: Regex de alta precisión + Caché SHA-256 ante falta de API Key o cuota 429.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.client = None
        self._hash_cache: Dict[str, JobEnrichmentResult] = {}

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Google Gemini SDK inicializado con Structured Outputs.")
            except Exception as e:
                logger.warning(f"No se pudo inicializar el SDK google-genai: {e}. Se usará Regex.")

    def _hash_content(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def extract_with_regex(self, job: RawJobData) -> JobEnrichmentResult:
        """
        Extractor puramente local mediante expresiones regulares.
        Cero consumo de tokens, ultra veloz y tolerante a fallos.
        """
        combined_text = f"{job.title} {job.clean_description}".lower()

        # 1. Detectar Seniority
        seniority = "unknown"
        for pat, level in SENIORITY_PATTERNS:
            if pat.search(combined_text):
                seniority = level
                break

        # 2. Detectar Modalidad
        modality = job.modality or "remote"
        for pat, mod in MODALITY_PATTERNS:
            if pat.search(combined_text):
                modality = mod
                break

        # 3. Detectar Habilidades
        detected_skills: Dict[str, ExtractedSkill] = {}
        for pattern, display_name, category in COMPILED_TECH_PATTERNS:
            if pattern.search(combined_text):
                # Determinar si es requerida o deseable buscando cercanía a palabras clave
                # Por defecto True (obligatorio) salvo que esté explícitamente en sección 'deseable'
                detected_skills[display_name] = ExtractedSkill(
                    name=display_name,
                    category=category,
                    is_required=True
                )

        return JobEnrichmentResult(
            job_external_id=job.external_id,
            seniority=seniority,
            modality=modality,
            skills=list(detected_skills.values())
        )

    def extract_batch(self, jobs: List[RawJobData]) -> List[JobEnrichmentResult]:
        """
        Procesa un lote de ofertas (5 a 10) usando Micro-Batching con Gemini si está disponible,
        o degrada de forma transparente a Regex ante errores o ausencia de API Key.
        """
        if not jobs:
            return []

        results: List[JobEnrichmentResult] = []
        pending_jobs: List[RawJobData] = []

        # Revisar caché SHA-256 para evitar reprocesar descripciones idénticas
        for job in jobs:
            h = self._hash_content(job.clean_description)
            if h in self._hash_cache:
                cached = self._hash_cache[h].model_copy(update={"job_external_id": job.external_id})
                results.append(cached)
            else:
                pending_jobs.append(job)

        if not pending_jobs:
            return results

        # Si hay cliente Gemini disponible, intentar Micro-Batching
        if self.client:
            try:
                gemini_results = self._call_gemini_microbatch(pending_jobs)
                if gemini_results:
                    for job, res in zip(pending_jobs, gemini_results):
                        h = self._hash_content(job.clean_description)
                        self._hash_cache[h] = res
                        results.append(res)
                    return results
            except Exception as e:
                logger.warning(f"Error en llamada a Gemini ({e}). Realizando Fallback seguro a Regex.")

        # Fallback a Regex
        for job in pending_jobs:
            res = self.extract_with_regex(job)
            h = self._hash_content(job.clean_description)
            self._hash_cache[h] = res
            results.append(res)

        return results

    def _call_gemini_microbatch(self, jobs: List[RawJobData]) -> List[JobEnrichmentResult]:
        """
        Ejecuta la llamada a Gemini 2.5 Flash con Structured Outputs (Pydantic).
        """
        from google.genai import types

        batch_prompt_parts = [
            "Eres un Analista Técnico Senior de Mercado TI.",
            "Extrae con precisión para cada oferta:",
            "- seniority ('junior', 'semi-senior', 'senior', 'lead', 'unknown')",
            "- modality ('remote', 'hybrid', 'onsite')",
            "- skills técnicas (nombre canónico, category, is_required: True si es excluyente/obligatorio, False si es deseable).",
            "\nOFERTAS A ANALIZAR:\n"
        ]

        for idx, job in enumerate(jobs, 1):
            # Limitar longitud para evitar saturar tokens de contexto innecesariamente
            snippet = job.clean_description[:1200]
            batch_prompt_parts.append(
                f"--- OFERTA #{idx} ---\n"
                f"ID: {job.external_id}\n"
                f"Título: {job.title}\n"
                f"Empresa: {job.company}\n"
                f"Descripción: {snippet}\n"
            )

        full_prompt = "\n".join(batch_prompt_parts)

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BatchEnrichmentResponse,
                temperature=0.1,
            )
        )

        parsed = BatchEnrichmentResponse.model_validate_json(response.text)
        return parsed.items
