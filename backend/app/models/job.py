from datetime import datetime, timezone
from typing import List, Optional
import re
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


# Diccionario canónico para mapeo y normalización de sinónimos técnicos
CANONICAL_SKILL_SYNONYMS = {
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "nodejs": "node.js",
    "node": "node.js",
    "golang": "go",
    "postgresql": "postgres",
    "psql": "postgres",
    "amazon web services": "aws",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "k8s": "kubernetes",
    "fast api": "fastapi",
    "django rest framework": "drf",
}


def normalize_skill_name(raw_name: str) -> tuple[str, str]:
    """
    Normaliza el nombre de una tecnología eliminando caracteres extraños y
    resolviendo sinónimos comunes hacia un slug canónico único.
    
    Retorna: (display_name, canonical_slug)
    Ejemplo: "React.js" -> ("React", "react")
    """
    cleaned = raw_name.strip()
    slug = re.sub(r"[^\w\s\.\-\#\+]", "", cleaned.lower())
    slug = re.sub(r"\s+", "-", slug)
    
    # Resolver sinónimos conocidos
    slug = CANONICAL_SKILL_SYNONYMS.get(slug, slug)
    
    # Capitalizar display name adecuadamente
    display_name = cleaned
    return display_name, slug


class JobSkill(Base):
    """
    Patrón Association Object (ADR 1.1).
    Permite modelar atributos adicionales en la relación N:M,
    específicamente si la habilidad es requisito obligatorio o deseable.
    """
    __tablename__ = "job_skills"

    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True
    )
    skill_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="True si es requisito obligatorio, False si es deseable"
    )

    # Relaciones de navegación
    job: Mapped["Job"] = relationship("Job", back_populates="job_skills")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="job_skills")


class Job(Base):
    """
    Tabla de Ofertas Laborales Ingeridas (ADR 1.1).
    Almacena ofertas provenientes de Get On Board y RemoteOK garantizando
    idempotencia mediante la restricción única (source, external_id).
    """
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    modality: Mapped[str] = mapped_column(String(50), default="remote", nullable=False)
    seniority: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # Datos Salariales (USD)
    min_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    
    # Campos para Machine Learning (Fases 2 y 3)
    is_salary_predicted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    predicted_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Restricción de Idempotencia estricta
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
    )

    # Relación con la tabla puente
    job_skills: Mapped[List["JobSkill"]] = relationship(
        "JobSkill",
        back_populates="job",
        cascade="all, delete-orphan"
    )


class Skill(Base):
    """
    Catálogo Normalizado de Habilidades Técnicas (ADR 1.1).
    Identificador único canónico indexado para búsquedas y agregaciones analíticas.
    """
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(
        String(50),
        default="other",
        nullable=False,
        comment="language, framework, database, cloud, data_ml, devops, tool, other"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relación con la tabla puente
    job_skills: Mapped[List["JobSkill"]] = relationship(
        "JobSkill",
        back_populates="skill",
        cascade="all, delete-orphan"
    )
