<template>
  <div class="predict-view">
    <!-- Header -->
    <div class="view-header">
      <div class="header-badge">
        <Sparkles :size="14" />
        <span>Inferencia con Ensamble ML (VotingRegressor)</span>
      </div>
      <h1 class="view-title">Predictor de Sueldos Ocultos</h1>
      <p class="view-subtitle">
        El 80% de las ofertas TI no publican sueldo. Pega la URL de una vacante o completa su descripción para estimar su valor real de mercado.
      </p>

      <!-- Botones de Demo Rápida (1-Clic) (Regla 2 - Fase 5) -->
      <div class="presets-container">
        <span class="presets-label">Prueba rápida para reclutadores:</span>
        <button class="preset-btn" @click="loadPreset('data_science')">
          <span>⚡ Ejemplo: Data Scientist (LatAm)</span>
        </button>
        <button class="preset-btn" @click="loadPreset('backend_remote')">
          <span>🌎 Ejemplo: Senior Backend Python (Global Remote)</span>
        </button>
      </div>
    </div>

    <!-- Grid de Formulario y Resultados -->
    <div class="predict-grid">
      <!-- Columna 1: Formulario -->
      <div class="card form-card">
        <div class="card-header">
          <div class="card-title">
            <Search :size="18" class="text-blue" />
            <span>Datos de la Oferta Laboral</span>
          </div>
        </div>

        <form @submit.prevent="handleSubmit">
          <!-- Opción A: Pegar URL -->
          <div class="form-group">
            <label class="form-label">
              <span>Opción A: Pegar URL de Get On Board</span>
              <span class="label-hint">(Extracción en vivo)</span>
            </label>
            <div class="input-with-icon">
              <LinkIcon :size="16" class="input-icon text-muted" />
              <input
                v-model="form.url"
                type="url"
                class="form-input has-icon"
                placeholder="https://www.getonbrd.com/jobs/programming/..."
              />
            </div>
          </div>

          <div class="divider">
            <span>o ingresa los datos manualmente</span>
          </div>

          <!-- Opción B: Formulario Manual -->
          <div class="form-group">
            <label class="form-label">Título del Cargo</label>
            <input
              v-model="form.title"
              type="text"
              class="form-input"
              placeholder="Ej. Senior Fullstack Engineer"
            />
          </div>

          <div class="form-group">
            <label class="form-label">Descripción de Requisitos y Stack</label>
            <textarea
              v-model="form.description"
              class="form-textarea"
              rows="4"
              placeholder="Pega las tecnologías y requisitos solicitados en la oferta..."
            ></textarea>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Categoría</label>
              <select v-model="form.category" class="form-select">
                <option value="programming">Desarrollo Web / Móvil</option>
                <option value="data-science-analytics">Data Science & Analytics</option>
                <option value="machine-learning-ai">IA & Machine Learning</option>
                <option value="sysadmin-devops-qa">DevOps, Cloud & QA</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Mercado / Región</label>
              <select v-model="form.market_region" class="form-select">
                <option value="getonboard">Latinoamérica (Get On Board)</option>
                <option value="remoteok">Global Remoto (RemoteOK)</option>
              </select>
            </div>
          </div>

          <button
            type="submit"
            class="btn btn-primary btn-block"
            :disabled="store.predictionLoading"
          >
            <span v-if="store.predictionLoading" class="spinner-sm"></span>
            <Sparkles v-else :size="18" />
            <span>{{ store.predictionLoading ? 'Calculando Inferencia ML...' : 'Predecir Banda Salarial Oculta' }}</span>
          </button>
        </form>
      </div>

      <!-- Columna 2: Resultado de la Predicción -->
      <div class="result-column">
        <div v-if="store.predictionResult" class="card result-card">
          <div class="card-header">
            <span class="badge badge-green">Predicción Concluida</span>
            <span class="text-muted text-xs">Margen MAE: &plusmn;${{ Math.round(store.isMonthly ? 1070 : 12840) }} {{ store.periodSuffix }}</span>
          </div>

          <!-- Monto Principal -->
          <div class="salary-display">
            <span class="salary-label">Sueldo Estimado de la Vacante</span>
            <div class="salary-amount text-emerald">
              {{ store.displaySalary(store.predictionResult.predicted_annual_usd) }}
            </div>
            <span class="salary-subtext">
              Equivalente a ${{ Math.round(store.predictionResult.predicted_annual_usd / 12).toLocaleString() }} USD/mes &bull; {{ store.predictionResult.market_region }}
            </span>
          </div>

          <!-- Banda de Confianza -->
          <div class="confidence-box">
            <span class="confidence-title">Banda Salarial con Intervalo de Confianza (MAE):</span>
            <div class="confidence-range">
              <div class="range-val">
                <span class="range-lbl">Mínimo Estimado</span>
                <span class="range-num">{{ store.displaySalary(store.predictionResult.confidence_range_annual_usd[0]) }}</span>
              </div>
              <div class="range-bar">
                <div class="range-fill"></div>
              </div>
              <div class="range-val text-right">
                <span class="range-lbl">Máximo Estimado</span>
                <span class="range-num">{{ store.displaySalary(store.predictionResult.confidence_range_annual_usd[1]) }}</span>
              </div>
            </div>
          </div>

          <!-- Metadatos de la Oferta -->
          <div class="metadata-grid">
            <div class="meta-item">
              <span class="meta-lbl">Puesto:</span>
              <span class="meta-val">{{ store.predictionResult.title }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-lbl">Seniority Inferred:</span>
              <span class="badge badge-blue">{{ store.predictionResult.seniority }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-lbl">Modalidad:</span>
              <span class="meta-val capitalize">{{ store.predictionResult.modality }}</span>
            </div>
          </div>

          <!-- Habilidades Técnicas Detectadas -->
          <div class="detected-skills">
            <span class="meta-lbl">Tecnologías Detectadas por el LLM/Regex:</span>
            <div class="skills-wrap">
              <span
                v-for="skill in store.predictionResult.detected_skills"
                :key="skill"
                class="badge badge-purple"
              >
                {{ skill }}
              </span>
              <span v-if="!store.predictionResult.detected_skills.length" class="text-muted text-xs">
                No se detectaron skills explícitas en el texto.
              </span>
            </div>
          </div>
        </div>

        <!-- Placeholder antes de predecir -->
        <div v-else class="card empty-result-card">
          <Sparkles :size="48" class="text-muted" />
          <h3>Esperando datos para inferencia</h3>
          <p>Usa uno de los botones de Demo Rápida o ingresa la URL de una oferta para calcular su sueldo oculto.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { useAppStore } from '../stores/appStore.js'
import {
  Sparkles,
  Search,
  Link as LinkIcon,
} from 'lucide-vue-next'

const store = useAppStore()

const form = reactive({
  url: '',
  title: '',
  description: '',
  category: 'programming',
  market_region: 'getonboard',
})

// Presets de 1-Clic para Reclutadores (Regla 2 - Fase 5)
const loadPreset = (type) => {
  if (type === 'data_science') {
    form.url = ''
    form.title = 'Data Scientist / Machine Learning Engineer'
    form.description =
      'Buscamos Data Scientist con experiencia en Python, SQL, Pandas, Scikit-learn, XGBoost y modelos predictivos en producción con Docker y GCP.'
    form.category = 'data-science-analytics'
    form.market_region = 'getonboard'
  } else if (type === 'backend_remote') {
    form.url = ''
    form.title = 'Senior Python & Cloud Backend Engineer'
    form.description =
      'Remote global position for a Senior Backend Engineer. Required: Python, FastAPI, PostgreSQL, Docker, Kubernetes, AWS, Redis, CI/CD.'
    form.category = 'programming'
    form.market_region = 'remoteok'
  }
  handleSubmit()
}

const handleSubmit = async () => {
  if (!form.url && !form.title && !form.description) {
    alert('Ingresa una URL o completa el título y descripción.')
    return
  }

  await store.predictOfferSalary({
    url: form.url || undefined,
    title: form.title || undefined,
    description: form.description || undefined,
    category: form.category,
    market_region: form.market_region,
    modality: 'remote',
  })
}
</script>

<style scoped>
.predict-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem;
  background: rgba(168, 85, 247, 0.15);
  border: 1px solid rgba(168, 85, 247, 0.3);
  border-radius: 9999px;
  color: #c084fc;
  font-size: 0.75rem;
  font-weight: 700;
  margin-bottom: 0.75rem;
}

.presets-container {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
  flex-wrap: wrap;
}

.presets-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-muted);
}

.preset-btn {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 0.4rem 0.85rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.preset-btn:hover {
  background: var(--accent-primary-glow);
  border-color: var(--accent-primary);
  color: #60a5fa;
  transform: translateY(-1px);
}

.predict-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 900px) {
  .predict-grid {
    grid-template-columns: 1fr;
  }
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.input-with-icon {
  position: relative;
}

.input-icon {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
}

.has-icon {
  padding-left: 2.75rem;
}

.label-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: normal;
  margin-left: 0.35rem;
}

.divider {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 1rem 0;
  color: var(--text-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
}

.divider::before, .divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid var(--border-color);
}

.divider span {
  padding: 0 0.75rem;
}

.btn-block {
  width: 100%;
}

.salary-display {
  text-align: center;
  padding: 1.5rem 0;
  border-bottom: 1px solid var(--border-color);
}

.salary-label {
  display: block;
  font-size: 0.8125rem;
  color: var(--text-muted);
  text-transform: uppercase;
  font-weight: 700;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.salary-amount {
  font-size: 2.5rem;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.salary-subtext {
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.confidence-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1rem;
  margin: 1.25rem 0;
}

.confidence-title {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.confidence-range {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.range-val {
  display: flex;
  flex-direction: column;
}

.range-lbl {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.range-num {
  font-size: 0.95rem;
  font-weight: 700;
}

.range-bar {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 9999px;
  overflow: hidden;
  position: relative;
}

.range-fill {
  width: 60%;
  height: 100%;
  background: var(--accent-emerald);
  border-radius: 9999px;
  margin: 0 auto;
}

.text-right {
  text-align: right;
}

.metadata-grid {
  display: flex;
  justify-content: space-between;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.875rem;
}

.meta-lbl {
  color: var(--text-muted);
  font-size: 0.8125rem;
  display: block;
  margin-bottom: 0.5rem;
}

.meta-val {
  font-weight: 600;
}

.detected-skills {
  margin-top: 1rem;
}

.skills-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.empty-result-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 4rem 2rem;
  gap: 1rem;
}

.spinner-sm {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
