import asyncio
import logging
from typing import Dict, List, Set, Tuple
import httpx
from sqlalchemy import select

from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models.job import Job, Skill, JobSkill, normalize_skill_name
from backend.app.etl.connectors import GetOnBoardConnector, RemoteOKConnector
from backend.app.etl.extractor import HybridSkillExtractor
from backend.app.etl.schemas import RawJobData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("etl.pipeline")


async def run_pipeline(
    limit_gob_per_category: int = 10,
    limit_remoteok: int = 25,
    micro_batch_size: int = 6,
) -> Dict[str, int]:
    """
    Orquestador principal del Pipeline ETL Multi-Fuente (Fase 1).
    1. Asegura existencia del esquema SQL.
    2. Ingiere ofertas en paralelo desde Get On Board y RemoteOK.
    3. Aplica deduplicación e idempotencia estricta en memoria contra la BD.
    4. Enriquece ofertas nuevas mediante Micro-Batching con HybridSkillExtractor.
    5. Normaliza y asocia habilidades en la tabla puente job_skills.
    6. Persiste en transacción atómica y retorna métricas de ejecución.
    """
    # 1. Asegurar tablas creadas
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    metrics = {
        "fetched_total": 0,
        "new_inserted": 0,
        "existing_skipped": 0,
        "salaries_with_data": 0,
        "skills_mapped": 0,
    }

    try:
        # 2. Cargar llaves existentes en BD para deduplicación veloz
        stmt = select(Job.source, Job.external_id)
        existing_records: Set[Tuple[str, str]] = set(db.execute(stmt).all())
        logger.info(f"Registros previos en BD: {len(existing_records)}")

        raw_jobs: List[RawJobData] = []

        # 3. Ingesta asíncrona multi-fuente
        async with httpx.AsyncClient() as http_client:
            # Fuente A: Get On Board (iterando categorías TI)
            gob_connector = GetOnBoardConnector()
            for cat in gob_connector.TARGET_CATEGORIES:
                logger.info(f"Ingiriendo Get On Board categoría: {cat}...")
                jobs = await gob_connector.fetch_category_page(
                    http_client,
                    category=cat,
                    page=1,
                    per_page=limit_gob_per_category
                )
                raw_jobs.extend(jobs)

            # Fuente B: RemoteOK (mercado global remoto)
            logger.info("Ingiriendo RemoteOK...")
            rok_connector = RemoteOKConnector()
            rok_jobs = await rok_connector.fetch_jobs(http_client, limit=limit_remoteok)
            raw_jobs.extend(rok_jobs)

        metrics["fetched_total"] = len(raw_jobs)
        logger.info(f"Total de ofertas recolectadas: {metrics['fetched_total']}")

        # 4. Filtrar ofertas ya existentes (Idempotencia)
        new_jobs = [
            j for j in raw_jobs
            if (j.source, j.external_id) not in existing_records
        ]
        metrics["existing_skipped"] = metrics["fetched_total"] - len(new_jobs)
        logger.info(f"Ofertas nuevas a procesar: {len(new_jobs)} (Omitidas por duplicadas: {metrics['existing_skipped']})")

        if not new_jobs:
            logger.info("No hay nuevas ofertas para procesar. Pipeline al día.")
            return metrics

        # 5. Extracción y Enriquecimiento Híbrido (Micro-Batching)
        extractor = HybridSkillExtractor()
        skill_cache: Dict[str, Skill] = {}
        
        # Precargar catálogo de skills existentes en memoria
        for s in db.scalars(select(Skill)).all():
            skill_cache[s.slug] = s

        # Procesar en lotes de tamaño micro_batch_size
        for i in range(0, len(new_jobs), micro_batch_size):
            batch = new_jobs[i : i + micro_batch_size]
            enrichment_results = extractor.extract_batch(batch)

            for raw_job, enriched in zip(batch, enrichment_results):
                # Instanciar Job
                job = Job(
                    source=raw_job.source,
                    external_id=raw_job.external_id,
                    title=raw_job.title,
                    company=raw_job.company,
                    description=raw_job.clean_description,
                    location=raw_job.location,
                    modality=enriched.modality or raw_job.modality,
                    seniority=enriched.seniority,
                    category=raw_job.category,
                    min_salary=raw_job.min_salary,
                    max_salary=raw_job.max_salary,
                    salary_currency=raw_job.salary_currency,
                    is_salary_predicted=False,
                    url=raw_job.url,
                    published_at=raw_job.published_at,
                )
                db.add(job)
                db.flush()  # Obtener job.id generado

                if raw_job.min_salary is not None or raw_job.max_salary is not None:
                    metrics["salaries_with_data"] += 1

                # Mapear y normalizar Habilidades (Association Object)
                for ext_skill in enriched.skills:
                    disp_name, slug = normalize_skill_name(ext_skill.name)
                    if not slug:
                        continue

                    if slug not in skill_cache:
                        new_skill = Skill(
                            name=disp_name,
                            slug=slug,
                            category=ext_skill.category
                        )
                        db.add(new_skill)
                        db.flush()
                        skill_cache[slug] = new_skill
                    
                    skill_obj = skill_cache[slug]

                    # Crear vínculo N:M con is_required
                    job_skill = JobSkill(
                        job_id=job.id,
                        skill_id=skill_obj.id,
                        is_required=ext_skill.is_required
                    )
                    db.add(job_skill)
                    metrics["skills_mapped"] += 1

                metrics["new_inserted"] += 1

            # Commit parcial por lote para mantener transacciones cortas
            db.commit()
            logger.info(f"Lote procesado: {min(i + micro_batch_size, len(new_jobs))}/{len(new_jobs)} ofertas guardadas.")

        logger.info("Pipeline ETL finalizado exitosamente.")
        return metrics

    except Exception as e:
        db.rollback()
        logger.error(f"Fallo crítico en el pipeline ETL: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    results = asyncio.run(run_pipeline())
    print("\n" + "=" * 50)
    print("RESUMEN DE EJECUCIÓN ETL (TechPulse AI)")
    print("=" * 50)
    for k, v in results.items():
        print(f" - {k}: {v}")
    print("=" * 50)
