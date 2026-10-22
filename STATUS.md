# TechPulse AI - Memoria de Arquitectura y Estado del Proyecto

## 1. Visión del Sistema
**TechPulse AI** es una plataforma SaaS B2C/B2B diseñada para el análisis salarial en el sector TI, auditoría automatizada de CVs en PDF y simulación matemática de ROI por adquisición de skills técnicas.

---

## 2. Estado Actual del Proyecto
- **Fase Actual:** FASE 1 - Pipeline ETL Multi-Fuente (Get On Board + RemoteOK) + Extracción con LLM.
- **Estado de Fase 0:** COMPLETADA ✅
- **Estado de Fase 1:** COMPLETADA ✅
- **Próxima Fase:** FASE 2 - Análisis Exploratorio (EDA) y Feature Engineering sin Data Leakage.

---

## 3. Registro de Decisiones de Arquitectura (ADR)

### ADR 0.1: Estrategia de Persistencia y Motor SQL (Desarrollo vs. Producción)
- **Fecha:** 21-10-2026
- **Decisión:** **Opción A - SQLite en local y PostgreSQL en producción mediante SQLAlchemy 2.0**.
- **Justificación Técnica:**
  - Evita consumo innecesario de memoria RAM y servicios en segundo plano en Windows.
  - Facilita ejecución de pruebas automatizadas con `pytest` en memoria sin dependencias externas.
  - Permite desacoplar el almacenamiento mediante el patrón ORM (12-Factor App methodology), migrando a PostgreSQL en la nube (Render/Supabase) cambiando únicamente `DATABASE_URL`.
- **Reglas de Implementación Mandatorias (SQLAlchemy 2.0):**
  1. **Integridad Referencial en SQLite:** Activar explícitamente llaves foráneas mediante el event listener `connect` de SQLAlchemy (`PRAGMA foreign_keys=ON`), garantizando comportamiento idéntico a PostgreSQL.
  2. **Concurrencia en FastAPI:** Pasar `connect_args={"check_same_thread": False}` únicamente cuando la URL de conexión sea SQLite, previniendo errores de concurrencia multihilo en endpoints asíncronos.
  3. **Tipos de Datos Neutrales:** Usar tipos estándar del ORM (`String`, `Integer`, `Float`, `Boolean`, `DateTime`, `JSON`) evitando dialectos propietarios no portables.

### ADR 1.1: Esquema de Base de Datos para Habilidades y Ofertas (Muchos-a-Muchos Normalizado)
- **Fecha:** 21-10-2026
- **Decisión:** **Opción A - Modelo Normalizado Muchos-a-Muchos (`jobs`, `skills`, `job_skills`) con Association Object**.
- **Justificación Técnica:**
  - Garantiza máxima eficiencia en agregaciones analíticas SQL (`GROUP BY`, `AVG`, `COUNT`), fundamentales para el cálculo de ROI salarial y métricas de mercado.
  - Mantiene neutralidad 100% entre SQLite y PostgreSQL (SQL ANSI estándar sin depender de funciones JSON específicas de motor).
  - Asegura integridad referencial en 3ra Forma Normal (3FN).
- **Reglas de Implementación Mandatorias:**
  1. **Normalización Canónica en `skills`:** Columna `name` para display, `slug` único e indexado en minúsculas, diccionario de sinónimos canónicos (ej. `reactjs` -> `react`), y columna `category` (`language`, `framework`, `database`, `cloud`, `data_ml`, `devops`, `tool`).
  2. **Patrón Association Object en `job_skills`:** Llave primaria compuesta `(job_id, skill_id)` con `ForeignKey(..., ondelete="CASCADE")` y atributo booleano `is_required` (default True).
  3. **Idempotencia en `jobs`:** Columnas `external_id` y `source` ("getonboard" o "remoteok") con restricción `UniqueConstraint('source', 'external_id')` para re-ejecución segura del pipeline sin duplicados.

### ADR 1.2: Extractor LLM Híbrido y Resiliencia de Ingesta (Gemini 2.5 Flash + Micro-Batching)
- **Fecha:** 21-10-2026
- **Decisión:** **Opción A - Google Gemini API (`gemini-2.5-flash`) mediante SDK oficial `google-genai` + Micro-Batching + Pipeline Híbrido de Resiliencia**.
- **Justificación Técnica:**
  - Capa gratuita generosa (1.500 RPD) con soporte de *Structured Outputs* nativo (`response_schema` enlazado a Pydantic).
  - Micro-batching de 5 a 10 ofertas pre-limpiadas con `BeautifulSoup` reduce el consumo de peticiones por minuto (RPM) en ~90%, evitando saturar el límite de 15 RPM.
  - Mitiga interrupciones mediante reintentos exponenciales (`tenacity`) y degradación fluida a extractor Regex ante códigos `429 (Rate Limit)` o ausencia de API Key.
- **Reglas de Implementación Mandatorias:**
  1. **SDK Oficial Actual:** Emplear `google-genai` con cliente `client.models.generate_content(model="gemini-2.5-flash", contents=..., config=dict(response_mime_type="application/json", response_schema=...))`.
  2. **Sanitización y Micro-Batching:** Limpieza de HTML crudo a texto plano con `BeautifulSoup` antes de enviar el lote (`list[JobExtractionSchema]`).
  3. **Capa Regex Defensiva:** Catálogo de expresiones regulares y sinónimos canónicos para pre-filtrado rápido y fallback tolerante a fallos.

---

## 4. Estructura Objetivo del Monorepo
```text
techpulse-ai/
├── backend/
│   ├── app/
│   │   ├── api/            # Endpoints FastAPI (Mercado, Predicción, Auditoría CV, ROI)
│   │   ├── core/           # Configuración Pydantic BaseSettings y conexión SQL
│   │   ├── etl/            # Conectores Get On Board + RemoteOK y Extractor LLM
│   │   ├── ml/             # Feature Engineering, Entrenamiento XGBoost/RF e Inferencia
│   │   ├── services/       # Parser de CV PDF (PyMuPDF) y Motor de Matching
│   │   └── models/         # Modelos SQLAlchemy y Esquemas Pydantic
│   ├── data/               # Datasets procesados y modelos serializados (.joblib)
│   ├── tests/              # Suite de pruebas unitarias con pytest
│   ├── .env.example
│   ├── requirements.txt
│   └── main.py
├── frontend/               # Aplicación SPA en Vue 3 + Vite (Dark Mode)
├── .gitignore              # Blindaje de secretos y entornos
├── STATUS.md               # Memoria persistente del sistema
└── README.md
```

---

## 5. Registro de Commits y Trazabilidad
| Commit Hash | Mensaje | Descripción |
| :--- | :--- | :--- |
| `6a36244` | `chore(init): initial commit with secure gitignore and architecture status` | Inicialización del repositorio base con reglas de seguridad y ADR 0.1 |
| `3d7537b` | `feat(etl): implement multi-source ingestion and LLM skill extractor` | Modelos SQLAlchemy, esquemas Pydantic, conectores Get On Board/RemoteOK, extractor híbrido y pipeline de orquestación |
