from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ExtractedSkill(BaseModel):
    """
    Representa una habilidad técnica individual extraída por el LLM o Regex.
    """
    name: str = Field(description="Nombre normalizado de la tecnología (ej. Python, Docker, Vue.js)")
    category: str = Field(
        default="other",
        description="Categoría: language, framework, database, cloud, data_ml, devops, tool, other"
    )
    is_required: bool = Field(
        default=True,
        description="True si es requisito obligatorio o excluyente, False si es deseable"
    )


class JobEnrichmentResult(BaseModel):
    """
    Esquema estructurado de salida (Structured Outputs) para enriquecimiento con LLM.
    Representa los datos extraídos de una oferta laboral individual.
    """
    job_external_id: str = Field(description="Identificador externo de la oferta para mapeo unívoco")
    seniority: str = Field(
        default="unknown",
        description="Nivel inferido: junior, semi-senior, senior, lead, unknown"
    )
    modality: str = Field(
        default="remote",
        description="Modalidad detectada: remote, hybrid, onsite"
    )
    skills: List[ExtractedSkill] = Field(
        default_factory=list,
        description="Lista de habilidades técnicas requeridas o deseables detectadas en el texto"
    )


class BatchEnrichmentResponse(BaseModel):
    """
    Contenedor para Micro-Batching de ofertas enviado y devuelto por Gemini API (ADR 1.2).
    Permite procesar múltiples ofertas en un único round-trip HTTP reduciendo el consumo de RPM.
    """
    items: List[JobEnrichmentResult] = Field(
        default_factory=list,
        description="Lista de ofertas estructuradas resultantes del análisis del lote"
    )


class RawJobData(BaseModel):
    """
    Esquema estándar intermedio para normalizar ofertas crudas provenientes de
    Get On Board y RemoteOK antes de su inserción y enriquecimiento.
    """
    source: str = Field(description="Fuente de ingesta: getonboard o remoteok")
    external_id: str = Field(description="ID original provisto por la API externa")
    title: str = Field(description="Título del puesto")
    company: str = Field(description="Nombre de la empresa empleadora")
    raw_description: str = Field(description="Texto HTML o enriquecido original de la descripción")
    clean_description: str = Field(description="Texto sanitizado sin etiquetas HTML ni scripts")
    location: Optional[str] = Field(default=None, description="Ubicación geográfica o país")
    modality: str = Field(default="remote", description="Modalidad reportada por la API")
    category: str = Field(default="programming", description="Categoría temática del empleo")
    min_salary: Optional[float] = Field(default=None, description="Sueldo mínimo publicado en USD")
    max_salary: Optional[float] = Field(default=None, description="Sueldo máximo publicado en USD")
    salary_currency: str = Field(default="USD", description="Moneda original reportada")
    url: str = Field(description="Enlace público oficial a la oferta laboral")
    published_at: Optional[datetime] = Field(default=None, description="Fecha de publicación")
