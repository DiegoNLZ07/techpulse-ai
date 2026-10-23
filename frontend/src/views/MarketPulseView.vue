<template>
  <div class="market-view">
    <!-- Header de la Vista -->
    <div class="view-header">
      <div class="header-badge">
        <Activity :size="14" />
        <span>Datos en Vivo de Mercado TI</span>
      </div>
      <h1 class="view-title">Radar de Inteligencia Salarial</h1>
      <p class="view-subtitle">
        Monitoreo en tiempo real de ofertas laborales TI ingeridas desde Get On Board (LatAm) y RemoteOK (Global Remote).
      </p>
    </div>

    <!-- Loading State -->
    <div v-if="store.loadingMarket" class="loading-state card">
      <div class="spinner"></div>
      <p>Consultando base de datos SQL y analítica de mercado...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="store.errorMessage" class="error-state card">
      <AlertTriangle :size="32" class="text-rose" />
      <p>{{ store.errorMessage }}</p>
      <button class="btn btn-secondary" @click="store.fetchMarketPulse">Reintentar</button>
    </div>

    <!-- Contenido Principal -->
    <div v-else-if="store.marketData" class="market-content">
      <!-- Fila 1: KPIs Principales -->
      <div class="kpi-grid">
        <div class="kpi-card card">
          <div class="kpi-icon-wrap bg-blue">
            <Briefcase :size="20" class="text-blue" />
          </div>
          <div class="kpi-info">
            <span class="kpi-label">Total Ofertas en Base de Datos</span>
            <span class="kpi-value">{{ store.marketData.total_jobs }}</span>
            <span class="kpi-subtext">GetOnBoard + RemoteOK</span>
          </div>
        </div>

        <div class="kpi-card card">
          <div class="kpi-icon-wrap bg-emerald">
            <DollarSign :size="20" class="text-emerald" />
          </div>
          <div class="kpi-info">
            <span class="kpi-label">Sueldo Mediana (P50)</span>
            <span class="kpi-value text-emerald">
              {{ store.displaySalary(store.marketData.median_salary_annual_usd) }}
            </span>
            <span class="kpi-subtext">{{ store.periodLabel }}</span>
          </div>
        </div>

        <div class="kpi-card card">
          <div class="kpi-icon-wrap bg-purple">
            <TrendingUp :size="20" class="text-purple" />
          </div>
          <div class="kpi-info">
            <span class="kpi-label">Sueldo Promedio</span>
            <span class="kpi-value text-purple">
              {{ store.displaySalary(store.marketData.mean_salary_annual_usd) }}
            </span>
            <span class="kpi-subtext">{{ store.periodLabel }}</span>
          </div>
        </div>

        <div class="kpi-card card">
          <div class="kpi-icon-wrap bg-amber">
            <EyeOff :size="20" class="text-amber" />
          </div>
          <div class="kpi-info">
            <span class="kpi-label">Sueldo Oculto en Ofertas</span>
            <span class="kpi-value text-amber">
              {{ (100 - store.marketData.salary_coverage_pct).toFixed(1) }}%
            </span>
            <span class="kpi-subtext">{{ store.marketData.jobs_without_salary }} ofertas sin sueldo publicado</span>
          </div>
        </div>
      </div>

      <!-- Fila 2: Gráficos de Demanda y Distribución -->
      <div class="charts-grid">
        <!-- Gráfico 1: Top 10 Habilidades más Demandadas -->
        <div class="card chart-card">
          <div class="card-header">
            <div class="card-title">
              <BarChart2 :size="18" class="text-blue" />
              <span>Top 10 Habilidades Más Demandadas</span>
            </div>
            <span class="badge badge-blue">Frecuencia en SQL</span>
          </div>
          <div class="chart-container">
            <Bar :data="skillsChartData" :options="barOptions" />
          </div>
        </div>

        <!-- Gráfico 2: Distribución de Seniority -->
        <div class="card chart-card">
          <div class="card-header">
            <div class="card-title">
              <PieChart :size="18" class="text-emerald" />
              <span>Distribución por Seniority</span>
            </div>
            <span class="badge badge-green">Nivel de Cargo</span>
          </div>
          <div class="chart-container doughnut-wrap">
            <Doughnut :data="seniorityChartData" :options="doughnutOptions" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAppStore } from '../stores/appStore.js'
import { Bar, Doughnut } from 'vue-chartjs'
import {
  Activity,
  Briefcase,
  DollarSign,
  TrendingUp,
  EyeOff,
  BarChart2,
  PieChart,
  AlertTriangle,
} from 'lucide-vue-next'

const store = useAppStore()

// Gráfico de Barras Reactivo (Regla 1 - Fase 5)
const skillsChartData = computed(() => {
  const topSkills = store.marketData?.top_skills_by_demand || []
  return {
    labels: topSkills.map((s) => s.skill),
    datasets: [
      {
        label: 'Vacantes que la solicitan',
        data: topSkills.map((s) => s.jobs_count),
        backgroundColor: 'rgba(59, 130, 246, 0.75)',
        hoverBackgroundColor: 'rgba(59, 130, 246, 1)',
        borderColor: '#3b82f6',
        borderWidth: 1,
        borderRadius: 6,
      },
    ],
  }
})

const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => ` ${ctx.raw} ofertas laborales activas`,
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { color: '#94a3b8', font: { weight: '600' } },
    },
    y: {
      grid: { color: 'rgba(255, 255, 255, 0.05)' },
      ticks: { color: '#94a3b8' },
    },
  },
}

// Gráfico de Dona: Seniority
const seniorityChartData = computed(() => {
  const seniority = store.marketData?.seniority_distribution || {}
  const labels = Object.keys(seniority).map((k) => k.toUpperCase())
  const values = Object.values(seniority)

  return {
    labels: labels.length ? labels : ['Sin datos'],
    datasets: [
      {
        data: values.length ? values : [1],
        backgroundColor: [
          '#3b82f6', // Senior
          '#10b981', // Lead
          '#64748b', // Unknown
          '#f59e0b', // Semi-senior
          '#a855f7', // Junior
        ],
        borderWidth: 0,
        hoverOffset: 6,
      },
    ],
  }
})

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom',
      labels: {
        color: '#94a3b8',
        padding: 15,
        usePointStyle: true,
        font: { family: "'Plus Jakarta Sans', sans-serif", weight: '600' },
      },
    },
  },
  cutout: '70%',
}
</script>

<style scoped>
.market-view {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 9999px;
  color: #60a5fa;
  font-size: 0.75rem;
  font-weight: 700;
  margin-bottom: 0.75rem;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.25rem;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 1.25rem;
}

.kpi-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.bg-blue { background: rgba(59, 130, 246, 0.15); }
.bg-emerald { background: rgba(16, 185, 129, 0.15); }
.bg-purple { background: rgba(168, 85, 247, 0.15); }
.bg-amber { background: rgba(245, 158, 11, 0.15); }

.text-blue { color: #60a5fa; }
.text-emerald { color: #34d399; }
.text-purple { color: #c084fc; }
.text-amber { color: #fbbf24; }
.text-rose { color: #fb7185; }

.kpi-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.kpi-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.kpi-value {
  font-size: 1.5rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.kpi-subtext {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.charts-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 992px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  display: flex;
  flex-direction: column;
}

.chart-container {
  position: relative;
  width: 100%;
  height: 320px;
}

.doughnut-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem 0;
}

.loading-state, .error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem;
  gap: 1rem;
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(59, 130, 246, 0.2);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
