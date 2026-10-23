# TechPulse AI - Memoria de Arquitectura y Estado del Proyecto

## 1. Visión del Sistema
**TechPulse AI** es una plataforma SaaS B2C/B2B diseñada para el análisis salarial en el sector TI, auditoría automatizada de CVs en PDF y simulación matemática de ROI por adquisición de skills técnicas.

---

## 2. Estado Actual del Proyecto
- **Fase Actual:** FASE 5 - Frontend SaaS en Vue 3 (Dark Mode).
- **Estado de Fase 0:** COMPLETADA ✅
- **Estado de Fase 1:** COMPLETADA ✅
- **Estado de Fase 2:** COMPLETADA ✅
- **Estado de Fase 3:** COMPLETADA ✅
- **Estado de Fase 4:** COMPLETADA ✅
- **Estado de Fase 5:** COMPLETADA ✅
- **Próxima Fase:** FASE 6 - Testing Automatizado, README de Alto Impacto y Despliegue en GitHub.

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

### ADR 2.1: Tratamiento Matemático de la Variable Objetivo Salarial (Target)
- **Fecha:** 22-10-2026
- **Decisión:** **Opción A - Escala Anual Unificada en USD + Transformación Logarítmica (`np.log1p` / `np.expm1`) mediante `TransformedTargetRegressor`**.
- **Justificación Técnica:**
  - Corrige la asimetría positiva severa (*right-skewed*) de la distribución salarial observada en el EDA (\$2.1k a \$195k USD).
  - Estabiliza la varianza (homocedasticidad) y evita que ofertas atípicas muy altas monopolicen la función de pérdida.
  - Garantiza matemáticamente que las predicciones en inferencia sean estrictamente positivas ($\exp(x) > 0$).
- **Reglas de Implementación Mandatorias:**
  1. **Anualización y Rango de Cordura:** Si `source == 'getonboard'` o sueldo < \$12,000 USD, multiplicar por 12. Descartar registros atípicos < \$6,000 o > \$300,000 USD/año.
  2. **Punto Medio:** Calcular variable base como `(min_salary + max_salary) / 2` (o extremo disponible).
  3. **Wrapper Scikit-learn:** Usar `TransformedTargetRegressor(regressor=..., func=np.log1p, inverse_func=np.expm1)` en `sklearn.compose` para abstraer la conversión y evaluar directamente en USD reales.
  4. **Control de Brecha Regional:** Mantener `source` (`market_region`) como feature categórica explícita para capturar el diferencial estructural entre LatAm y Global Remote.

### ADR 2.2: Vectorización de Features y Preprocesamiento Tabular
- **Fecha:** 22-10-2026
- **Decisión:** **Opción A - Matriz Binaria Multietiqueta (Top N Skills con Poda por Frecuencia) + Encoders en `ColumnTransformer`**.
- **Justificación Técnica:**
  - Máxima explicabilidad analítica para el Simulador de ROI de Skills (permite variar un bit $0 \rightarrow 1$ y calcular el retorno salarial marginal $\Delta \hat{y}$ en milisegundos).
  - Blindaje contra *Data Leakage* al encapsular transformadores dentro del pipeline de Scikit-Learn.
  - Inferencia ultra rápida ($< 5\text{ ms}$) y consumo mínimo de memoria ($< 30\text{ MB}$ de RAM), compatible con la capa gratuita de Render (512 MB).
- **Reglas de Implementación Mandatorias:**
  1. **Poda por Frecuencia Mínima (`min_freq`):** Filtrar skills con baja ocurrencia en ofertas con sueldo para evitar que tecnologías raras generen sesgos y *overfitting*.
  2. **Feature de Complejidad del Stack (`skill_count`):** Columna numérica explícita con el total de tecnologías requeridas (`len(skills)`).
  3. **Enriquecimiento Ligero desde `title`:** Imputar `seniority` si es `'unknown'` inspeccionando palabras clave en el título (`lead`, `senior`, `staff`, `principal`, `architect`, `junior`).
  4. **Pipeline Scikit-learn Nativo:** Empaquetar `SkillsBinarizer` (heredando de `BaseEstimator, TransformerMixin`), `OrdinalEncoder` para seniority y `OneHotEncoder(handle_unknown='ignore')` para variables categóricas (`category`, `modality`, `market_region`).

### ADR 3.1: Torneo de Modelos (5-Fold CV), Ensamble Híbrido y Estimación por Intervalos
- **Fecha:** 22-10-2026
- **Decisión:** **Opción A - Torneo de 4 Modelos (`Ridge`, `RandomForest`, `GradientBoosting`, `VotingRegressor`) con 5-Fold Cross-Validation bajo `TransformedTargetRegressor` + Ampliación Calibrada de Muestra ($N \ge 300$)**.
- **Justificación Técnica:**
  - Resuelve la alerta matemática de sub-determinación ($p > n$, 45 features vs 38 filas) mediante data augmentation calibrado estadísticamente con las distribuciones reales de Get On Board y RemoteOK, asegurando $N \gg P$ ($N \ge 300, N/P \ge 6$).
  - `Ridge(alpha=1.0)` garantiza gradientes continuos y pesos marginales no nulos para todas las tecnologías, evitando que tecnologías clave tengan coeficiente 0 en el Simulador de ROI.
  - `VotingRegressor(Ridge + GradientBoosting/RF)` combina la sensibilidad marginal continua lineal con interacciones no lineales de árboles de decisión.
  - El motor de inferencia entrega predicción puntual $\hat{y}$ e intervalo de confianza $[\hat{y} - \text{MAE}, \hat{y} + \text{MAE}]$ para ofrecer bandas salariales realistas a usuarios B2C/B2B.

### ADR 5.1: Arquitectura Frontend (Vue 3 Composition API + Pinia + Chart.js Canvas)
- **Fecha:** 23-10-2026
- **Decisión:** **Opción A - Vue 3 con `<script setup>`, Pinia para gestión de estado global reactiva y Chart.js (`vue-chartjs`) sobre HTML5 Canvas**.
- **Justificación Técnica:**
  - Estándar de oro del ecosistema Vue 3 moderno con reactividad desacoplada de la vista.
  - Pinia permite compartir el perfil del CV y la valorización entre pestañas sin acoplamiento de componentes.
  - Switch reactivo global `USD/Mes` (estándar LatAm) vs. `USD/Año` (estándar Global) unificado en Pinia.
  - Chart.js v4 ofrece renderizado en Canvas ultra liviano (~60 KB), evitando el sobrepeso de librerías SVG como ApexCharts (~500 KB).
- **Reglas de Implementación Mandatorias:**
  1. **Capa API Desacoplada (`api.js`):** Cliente Axios con variable de entorno `VITE_API_URL` y manejo estandarizado de errores.
  2. **Switch Global de Periodicidad:** Interruptor reactivo en Navbar que recalcula y actualiza todas las vistas en milisegundos.
  3. **Registro Exhaustivo en Chart.js:** Configuración con `ChartJS.register(...)` y `maintainAspectRatio: false` con alturas fijas en CSS para evitar bugs de visualización.
  4. **Modo Oscuro Nativo:** Sistema de variables CSS personalizadas (`--bg-primary: #0b0f19`, `--bg-card: #1e293b`, etc.) con estética SaaS comercial B2C/B2B.

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
| `11a47c5` | `feat(etl): implement multi-source ingestion and LLM skill extractor` | Modelos SQLAlchemy, esquemas Pydantic, conectores Get On Board/RemoteOK, extractor híbrido y pipeline de orquestación |
| `17598dd` | `feat(ml): implement EDA diagnostics and leak-free feature engineering pipeline` | Script de diagnóstico exploratorio, imputación de seniority, matriz multietiqueta con poda y ColumnTransformer Scikit-learn |
| `d7194bc` | `feat(ml): train salary regressor and skill ROI engine` | Torneo 5-Fold CV (Ridge, RF, GB, VotingRegressor), inferencia por intervalos y simulador bidimensional de ROI de skills |
| `01d6dcf` | `feat(api): implement FastAPI REST endpoints with lifespan and CV PDF auditor` | Endpoints REST (market-pulse, predict-offer, career-roi, audit-cv), gestión lifespan de modelos ML, parser de PDF con PyPDF y CORS |
| `abc7b77` | `test(api): add endpoint verification script for FastAPI suite` | Suite de verificación para los 4 endpoints REST con TestClient |
| `79fbed6` | `feat(frontend): implement Vue 3 SPA with Pinia Dark Mode and Chartjs` | Dashboard reactivo de 3 pestañas (Radar de Mercado, Predictor y Auditor de CV), switch de periodicidad USD/mes vs USD/año y presets de 1-clic |
