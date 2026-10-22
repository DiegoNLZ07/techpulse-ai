# TechPulse AI - Memoria de Arquitectura y Estado del Proyecto

## 1. Visión del Sistema
**TechPulse AI** es una plataforma SaaS B2C/B2B diseñada para el análisis salarial en el sector TI, auditoría automatizada de CVs en PDF y simulación matemática de ROI por adquisición de skills técnicas.

---

## 2. Estado Actual del Proyecto
- **Fase Actual:** FASE 0 - Preparación de Windows desde Cero & Configuración Base.
- **Estado de Fase 0:** COMPLETADA ✅
- **Próxima Fase:** FASE 1 - Pipeline ETL Multi-Fuente (Get On Board + RemoteOK) + Extracción con LLM.

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
