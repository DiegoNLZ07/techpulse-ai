<template>
  <div class="app-layout">
    <!-- Navbar Superior -->
    <header class="navbar">
      <div class="container navbar-content">
        <!-- Logo y Marca -->
        <div class="brand">
          <div class="brand-logo">
            <span class="pulse-dot"></span>
            <Activity :size="20" class="brand-icon" />
          </div>
          <div class="brand-text">
            <span class="brand-name">TechPulse <span class="gradient-text">AI</span></span>
            <span class="brand-tag">SaaS B2C/B2B</span>
          </div>
        </div>

        <!-- Navegación por Pestañas -->
        <nav class="tab-nav">
          <button
            class="tab-btn"
            :class="{ active: store.currentTab === 'market' }"
            @click="store.setTab('market')"
          >
            <BarChart3 :size="16" />
            <span>Radar de Mercado</span>
          </button>
          <button
            class="tab-btn"
            :class="{ active: store.currentTab === 'predict' }"
            @click="store.setTab('predict')"
          >
            <Sparkles :size="16" />
            <span>Predictor de Sueldos</span>
          </button>
          <button
            class="tab-btn"
            :class="{ active: store.currentTab === 'cv' }"
            @click="store.setTab('cv')"
          >
            <FileText :size="16" />
            <span>Auditor de CV & ROI</span>
            <span class="badge badge-emerald">Pro</span>
          </button>
        </nav>

        <!-- Switch Global de Periodicidad Salarial (Regla 2 - Fase 5) -->
        <div class="navbar-actions">
          <div class="currency-switch-container">
            <span class="switch-label">Escala:</span>
            <button
              class="currency-toggle-btn"
              :class="{ 'is-annual': !store.isMonthly }"
              @click="store.toggleBillingPeriod"
              :title="'Alternar entre sueldo mensual y anual'"
            >
              <span class="toggle-pill" :class="{ 'is-right': !store.isMonthly }"></span>
              <span class="toggle-option" :class="{ active: store.isMonthly }">USD/Mes</span>
              <span class="toggle-option" :class="{ active: !store.isMonthly }">USD/Año</span>
            </button>
          </div>
          
          <a
            href="https://github.com/DiegoNLZ07/techpulse-ai"
            target="_blank"
            class="btn-icon"
            title="Ver repositorio en GitHub"
          >
            <Github :size="18" />
          </a>
        </div>
      </div>
    </header>

    <!-- Contenedor Principal con las 3 Vistas Integradas (Paso 5.2) -->
    <main class="main-content container">
      <!-- Pestaña 1: Radar de Mercado TI -->
      <MarketPulseView v-if="store.currentTab === 'market'" />

      <!-- Pestaña 2: Predictor de Sueldos Ocultos -->
      <PredictOfferView v-else-if="store.currentTab === 'predict'" />

      <!-- Pestaña 3: Auditor de CV en PDF & Simulador de ROI -->
      <CVAuditorView v-else-if="store.currentTab === 'cv'" />
    </main>

    <!-- Footer -->
    <footer class="footer">
      <div class="container footer-content">
        <p>TechPulse AI &copy; 2026 - Plataforma SaaS de Inteligencia Salarial TI. Diseñado con Vue 3 + FastAPI.</p>
        <div class="footer-links">
          <span>Backend: FastAPI + Ensamble ML (Port 8000)</span>
          <span>&bull;</span>
          <span>Frontend: Vue 3 + Pinia + Chart.js (Port 5173)</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAppStore } from './stores/appStore.js'
import {
  Activity,
  BarChart3,
  Sparkles,
  FileText,
  Github,
} from 'lucide-vue-next'

import MarketPulseView from './views/MarketPulseView.vue'
import PredictOfferView from './views/PredictOfferView.vue'
import CVAuditorView from './views/CVAuditorView.vue'

const store = useAppStore()

onMounted(() => {
  store.fetchMarketPulse()
})
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.navbar {
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 50;
  padding: 0.875rem 0;
}

.navbar-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.brand-logo {
  position: relative;
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #1e3a8a, #3b82f6);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
}

.brand-icon {
  color: #ffffff;
}

.pulse-dot {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 8px;
  height: 8px;
  background: var(--accent-emerald);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--accent-emerald);
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: 1.125rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.gradient-text {
  background: linear-gradient(135deg, #60a5fa, #a855f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.brand-tag {
  font-size: 0.65rem;
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: 0.05em;
}

/* Tabs */
.tab-nav {
  display: flex;
  gap: 0.5rem;
  background: var(--bg-primary);
  padding: 0.25rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: transparent;
  color: var(--text-secondary);
  border: none;
  border-radius: var(--radius-md);
  font-family: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.tab-btn.active {
  background: var(--bg-card);
  color: var(--accent-primary);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.badge-emerald {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
  font-size: 0.65rem;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}

/* Actions & Switch */
.navbar-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.currency-switch-container {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.switch-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 600;
}

.currency-toggle-btn {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 9999px;
  padding: 0.2rem;
  cursor: pointer;
  user-select: none;
  font-family: inherit;
}

.toggle-pill {
  position: absolute;
  left: 2px;
  top: 2px;
  bottom: 2px;
  width: calc(50% - 2px);
  background: var(--accent-primary);
  border-radius: 9999px;
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 0 10px var(--accent-primary-glow);
}

.toggle-pill.is-right {
  transform: translateX(100%);
}

.toggle-option {
  position: relative;
  z-index: 1;
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-muted);
  transition: color 0.2s ease;
}

.toggle-option.active {
  color: #ffffff;
}

.btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  transition: all 0.2s ease;
}
.btn-icon:hover {
  color: var(--text-primary);
  border-color: var(--accent-primary);
}

/* Main Content */
.main-content {
  flex: 1;
  padding-top: 2rem;
  padding-bottom: 3rem;
}

/* Footer */
.footer {
  border-top: 1px solid var(--border-color);
  padding: 1.5rem 0;
  background: var(--bg-secondary);
  font-size: 0.8125rem;
  color: var(--text-muted);
}

.footer-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.footer-links {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
</style>
