<template>
  <div class="cv-view">
    <!-- Header -->
    <div class="view-header">
      <div class="header-badge">
        <Sparkles :size="14" />
        <span>Feature Estrella Freemium / Monetizable</span>
      </div>
      <h1 class="view-title">Auditor de CV en PDF & Simulador de ROI de Skills</h1>
      <p class="view-subtitle">
        Sube tu CV en PDF para extraer tu stack en memoria, valorar tu compensación de mercado actual y descubrir las 3 brechas exactas para ingresar al Top 20% salarial.
      </p>
    </div>

    <!-- Zona de Carga de CV (Drag & Drop) -->
    <div class="card upload-card" :class="{ 'is-dragging': isDragging }">
      <div
        class="dropzone"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
        @click="triggerFileInput"
      >
        <input
          ref="fileInputRef"
          type="file"
          accept=".pdf,application/pdf"
          class="file-input-hidden"
          @change="handleFileSelect"
        />

        <div v-if="!store.cvLoading" class="dropzone-inner">
          <div class="upload-icon-wrap">
            <UploadCloud :size="32" class="text-blue" />
          </div>
          <h3 class="upload-title">Arrastra y suelta tu CV aquí (PDF) o haz clic para explorar</h3>
          <p class="upload-hint">Documentos PDF de hasta 5 MB procesados estrictamente en memoria.</p>

          <!-- Selectores de Mercado Objetivo -->
          <div class="upload-selectors" @click.stop>
            <div class="selector-item">
              <label>Mercado Objetivo:</label>
              <select v-model="targetMarketRegion" class="form-select-sm">
                <option value="getonboard">Latinoamérica (Get On Board)</option>
                <option value="remoteok">Global Remoto (RemoteOK)</option>
              </select>
            </div>
            <div class="selector-item">
              <label>Especialidad:</label>
              <select v-model="targetCategory" class="form-select-sm">
                <option value="programming">Desarrollo Web / Software</option>
                <option value="data-science-analytics">Data Science & Analytics</option>
                <option value="machine-learning-ai">IA & Machine Learning</option>
                <option value="sysadmin-devops-qa">Cloud, DevOps & QA</option>
              </select>
            </div>
          </div>
        </div>

        <div v-else class="upload-loading">
          <div class="spinner"></div>
          <h4>Auditando Curriculum con el LLM y Ensamble de ML...</h4>
          <p class="text-muted text-sm">Extrayendo texto, normalizando skills y calculando retornos contrafactuales.</p>
        </div>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="uploadError" class="card error-banner">
      <AlertTriangle :size="20" class="text-rose" />
      <span>{{ uploadError }}</span>
    </div>

    <!-- Dashboard Diagnóstico Pro (Resultados de la Auditoría) -->
    <div v-if="store.cvAuditReport" class="audit-results">
      <!-- Fila 1: Valorización y Progreso Top 20% -->
      <div class="results-summary-grid">
        <!-- Tarjeta de Valorización Salarial -->
        <div class="card valuation-card">
          <div class="card-header">
            <span class="badge badge-green">Valoración de Mercado Actual</span>
            <span class="text-muted text-xs">{{ store.cvAuditReport.market_valuation.market_region }}</span>
          </div>
          <div class="val-body">
            <span class="val-label">Tu Valor de Mercado Estimado</span>
            <div class="val-amount text-emerald">
              {{ store.displaySalary(store.cvAuditReport.market_valuation.estimated_annual_usd) }}
            </div>
            <span class="val-sub">
              Banda Salarial: {{ store.displaySalary(store.cvAuditReport.market_valuation.confidence_range_annual_usd[0]) }} - {{ store.displaySalary(store.cvAuditReport.market_valuation.confidence_range_annual_usd[1]) }}
            </span>
          </div>

          <div class="candidate-meta">
            <div class="meta-badge">
              <span class="text-muted">Seniority Detectado:</span>
              <strong class="text-blue">{{ store.cvAuditReport.candidate_profile.detected_seniority }}</strong>
            </div>
            <div class="meta-badge">
              <span class="text-muted">Skills Extraídas:</span>
              <strong class="text-primary">{{ store.cvAuditReport.candidate_profile.detected_skills_count }} tecnologías</strong>
            </div>
          </div>
        </div>

        <!-- Tarjeta de Brecha Top 20% Salarial (Monetizable) -->
        <div class="card benchmark-card">
          <div class="card-header">
            <div class="card-title">
              <Target :size="18" class="text-amber" />
              <span>Brecha hacia el Top 20% Salarial</span>
            </div>
            <span class="badge badge-amber">Umbral de Élite</span>
          </div>

          <div class="benchmark-body">
            <div class="benchmark-header">
              <span>Umbral Percentil 80 del Mercado:</span>
              <strong class="text-amber">{{ store.displaySalary(store.cvAuditReport.market_matching.top_20_percent_salary_threshold_usd) }}</strong>
            </div>

            <!-- Barra de Progreso hacia el Top 20% -->
            <div class="progress-bar-container">
              <div
                class="progress-bar-fill"
                :style="{
                  width: `${Math.min(
                    100,
                    Math.round(
                      (store.cvAuditReport.market_valuation.estimated_annual_usd /
                        store.cvAuditReport.market_matching.top_20_percent_salary_threshold_usd) *
                        100
                    )
                  )}%`,
                }"
              ></div>
            </div>
            <div class="progress-footer">
              <span class="text-muted text-xs">
                Actualmente estás al
                <strong>
                  {{
                    Math.round(
                      (store.cvAuditReport.market_valuation.estimated_annual_usd /
                        store.cvAuditReport.market_matching.top_20_percent_salary_threshold_usd) *
                        100
                    )
                  }}%
                </strong>
                del umbral del Top 20% mejor pagado.
              </span>
              <span class="text-muted text-xs">
                Calificas al <strong>{{ store.cvAuditReport.market_matching.qualification_rate_pct }}%</strong> de ofertas activas.
              </span>
            </div>

            <!-- Las 3 Brechas Críticas -->
            <div class="critical-gaps-section">
              <span class="gaps-title">Las 3 Tecnologías Clave que te faltan para este umbral:</span>
              <div class="gaps-list">
                <div
                  v-for="(gap, idx) in store.cvAuditReport.market_matching.critical_gaps_for_top_tier"
                  :key="gap.skill"
                  class="gap-pill"
                >
                  <span class="gap-rank">#{{ idx + 1 }}</span>
                  <span class="gap-name">{{ gap.skill }}</span>
                  <span class="gap-count">{{ gap.missing_in_jobs }} vacantes</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Fila 2: Tabla de Recomendaciones de ROI de Skills -->
      <div class="card roi-table-card">
        <div class="card-header">
          <div class="card-title">
            <TrendingUp :size="18" class="text-emerald" />
            <span>Simulador de ROI de Carrera: ¿Qué tecnología estudiar hoy?</span>
          </div>
          <span class="badge badge-green">Impacto Salarial 60% + Demanda 40%</span>
        </div>

        <div class="table-responsive">
          <table class="roi-table">
            <thead>
              <tr>
                <th>Prioridad</th>
                <th>Tecnología</th>
                <th>+ Sueldo Esperado</th>
                <th>Vacantes Desbloqueadas</th>
                <th>Score ROI</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rec in store.cvAuditReport.roi_recommendations" :key="rec.skill">
                <td>
                  <span
                    class="badge"
                    :class="{
                      'badge-green': rec.learning_priority.includes('Alta'),
                      'badge-blue': rec.learning_priority.includes('Media'),
                      'badge-amber': rec.learning_priority.includes('Baja'),
                    }"
                  >
                    {{ rec.learning_priority }}
                  </span>
                </td>
                <td>
                  <strong class="skill-name">{{ rec.display_name }}</strong>
                </td>
                <td class="text-emerald font-bold">
                  +{{ store.displaySalary(rec.delta_salary_annual_usd) }}
                  <span class="text-muted text-xs">({{ store.periodSuffix }})</span>
                </td>
                <td>
                  <span class="jobs-chip">
                    {{ rec.unlocked_jobs_count }} ofertas ({{ rec.demand_pct }}%)
                  </span>
                </td>
                <td>
                  <div class="roi-score-wrap">
                    <div class="score-pill" :style="{ width: `${rec.roi_score}%` }"></div>
                    <span class="score-text">{{ rec.roi_score }}/100</span>
                  </div>
                </td>
                <td>
                  <button class="btn btn-secondary btn-xs" @click="addSkillToCurrent(rec.skill)">
                    Simular Adición
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAppStore } from '../stores/appStore.js'
import {
  Sparkles,
  UploadCloud,
  Target,
  TrendingUp,
  AlertTriangle,
} from 'lucide-vue-next'

const store = useAppStore()

const fileInputRef = ref(null)
const isDragging = ref(false)
const uploadError = ref(null)

const targetMarketRegion = ref('getonboard')
const targetCategory = ref('programming')

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleFileSelect = (event) => {
  const file = event.target.files?.[0]
  if (file) processUpload(file)
}

const handleDrop = (event) => {
  isDragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) processUpload(file)
}

const processUpload = async (file) => {
  uploadError.value = null

  if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
    uploadError.value = 'Por favor selecciona un archivo PDF válido (.pdf).'
    return
  }

  if (file.size > 5 * 1024 * 1024) {
    uploadError.value = 'El archivo supera el límite máximo de 5 MB.'
    return
  }

  try {
    await store.auditCandidateCV(file, targetCategory.value, targetMarketRegion.value)
  } catch (err) {
    uploadError.value = err.message || 'Error al procesar el archivo.'
  }
}

const addSkillToCurrent = (skill) => {
  if (!store.candidateProfile.skills.includes(skill)) {
    store.candidateProfile.skills.push(skill)
    store.fetchCareerROI()
  }
}
</script>

<style scoped>
.cv-view {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 9999px;
  color: #34d399;
  font-size: 0.75rem;
  font-weight: 700;
  margin-bottom: 0.75rem;
}

.upload-card {
  padding: 0;
  overflow: hidden;
  border: 2px dashed var(--border-color);
  background: var(--bg-card);
  transition: all 0.2s ease;
  cursor: pointer;
}

.upload-card:hover, .upload-card.is-dragging {
  border-color: var(--accent-primary);
  background: rgba(59, 130, 246, 0.05);
}

.dropzone {
  padding: 3rem 2rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.file-input-hidden {
  display: none;
}

.upload-icon-wrap {
  width: 64px;
  height: 64px;
  background: rgba(59, 130, 246, 0.15);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
}

.upload-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.35rem;
}

.upload-hint {
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin-bottom: 1.5rem;
}

.upload-selectors {
  display: flex;
  gap: 1.5rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  padding: 0.75rem 1.25rem;
  border-radius: var(--radius-md);
}

.selector-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.form-select-sm {
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8125rem;
  outline: none;
}

.upload-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: rgba(244, 63, 94, 0.1);
  border-color: rgba(244, 63, 94, 0.3);
  color: #fb7185;
  font-size: 0.875rem;
}

.results-summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

@media (max-width: 900px) {
  .results-summary-grid {
    grid-template-columns: 1fr;
  }
}

.val-body {
  text-align: center;
  padding: 1.5rem 0;
  border-bottom: 1px solid var(--border-color);
}

.val-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: var(--text-muted);
  font-weight: 700;
}

.val-amount {
  font-size: 2.25rem;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.val-sub {
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.candidate-meta {
  display: flex;
  justify-content: space-between;
  padding-top: 1rem;
  font-size: 0.8125rem;
}

.benchmark-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.benchmark-header {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
}

.progress-bar-container {
  height: 10px;
  background: var(--bg-secondary);
  border-radius: 9999px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #10b981);
  border-radius: 9999px;
  transition: width 0.6s ease;
}

.progress-footer {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.critical-gaps-section {
  margin-top: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-color);
}

.gaps-title {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.gaps-list {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.gap-pill {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(244, 63, 94, 0.12);
  border: 1px solid rgba(244, 63, 94, 0.3);
  padding: 0.25rem 0.65rem;
  border-radius: 9999px;
  font-size: 0.75rem;
}

.gap-rank {
  color: #fb7185;
  font-weight: 800;
}

.gap-name {
  color: #ffffff;
  font-weight: 700;
}

.gap-count {
  color: var(--text-muted);
}

/* Tabla ROI */
.table-responsive {
  overflow-x: auto;
}

.roi-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.875rem;
}

.roi-table th {
  padding: 0.75rem 1rem;
  color: var(--text-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  border-bottom: 1px solid var(--border-color);
}

.roi-table td {
  padding: 1rem;
  border-bottom: 1px solid var(--border-color);
}

.skill-name {
  font-size: 0.95rem;
  color: var(--text-primary);
}

.jobs-chip {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.roi-score-wrap {
  position: relative;
  width: 100px;
  height: 18px;
  background: var(--bg-secondary);
  border-radius: 9999px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.score-pill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #10b981);
}

.score-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 0.65rem;
  font-weight: 800;
  color: #ffffff;
}

.btn-xs {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}
</style>
