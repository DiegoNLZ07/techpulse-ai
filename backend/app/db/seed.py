import json
import logging
from pathlib import Path
from sqlalchemy import select

from backend.app.core.database import Base, SessionLocal, engine
from backend.app.models.job import Job, Skill, JobSkill, normalize_skill_name

logger = logging.getLogger("seed")

SEED_FILE = Path(__file__).resolve().parent / "seed_data.json"


def seed_database(force: bool = False):
    """
    Siembra la base de datos SQLite con ofertas laborales reales y tecnologías canonicalizadas.
    Garantiza idempotencia y portabilidad para CI/CD y despliegue en la nube.
    """
    Base.metadata.create_all(bind=engine)
    if not SEED_FILE.exists():
        print(f"No se encontró el archivo de semillas en {SEED_FILE}")
        return

    db = SessionLocal()
    try:
        existing_count = db.query(Job).count()
        if existing_count > 0 and not force:
            print(f"La base de datos ya contiene {existing_count} ofertas. Omitiendo siembra.")
            return

        with open(SEED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"Sembrando {len(data)} ofertas laborales...")
        skills_cache = {s.canonical_slug: s for s in db.scalars(select(Skill)).all()}

        for item in data:
            job = Job(
                external_id=item["external_id"],
                source=item["source"],
                title=item["title"],
                company=item["company"],
                category=item["category"],
                seniority=item["seniority"],
                modality=item["modality"],
                location=item.get("location"),
                min_salary=item.get("min_salary"),
                max_salary=item.get("max_salary"),
                salary_currency=item.get("salary_currency", "USD"),
                url=item["url"],
                description=item["description"],
            )
            db.add(job)
            db.flush()

            for sk_name in item.get("skills", []):
                disp_name, slug = normalize_skill_name(sk_name)
                if slug not in skills_cache:
                    sk_obj = Skill(name=disp_name, canonical_slug=slug, category="technical")
                    db.add(sk_obj)
                    db.flush()
                    skills_cache[slug] = sk_obj
                else:
                    sk_obj = skills_cache[slug]

                js = JobSkill(job_id=job.id, skill_id=sk_obj.id, is_required=True)
                db.add(js)

        db.commit()
        print(f"Siembra completada con éxito. Total ofertas: {db.query(Job).count()}, Habilidades: {db.query(Skill).count()}")
    except Exception as e:
        db.rollback()
        print(f"Error sembrando base de datos: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
