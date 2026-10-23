import { defineStore } from 'pinia'
import api from '../services/api.js'

export const useAppStore = defineStore('app', {
  state: () => ({
    // Interruptor Global de Periodicidad Salarial (Regla 2 - Fase 5)
    billingPeriod: 'monthly', // 'monthly' | 'annual'

    // Control de Navegación por Pestañas
    currentTab: 'market', // 'market' | 'predict' | 'cv'

    // Datos de Mercado TI
    marketData: null,
    loadingMarket: false,

    // Perfil del Usuario / Candidato (sincronizado entre Pestaña 2 y Pestaña 3)
    candidateProfile: {
      skills: ['python', 'javascript', 'vue', 'sql', 'git'],
      seniority: 'junior',
      category: 'programming',
      marketRegion: 'getonboard',
      modality: 'remote',
    },

    // Resultados de Auditoría de CV en PDF
    cvAuditReport: null,
    cvLoading: false,

    // Resultados de Predicción de Sueldo
    predictionResult: null,
    predictionLoading: false,

    // Recomendaciones de ROI de Skills
    roiData: null,
    roiLoading: false,

    // Mensajes de Alerta y Notificación
    errorMessage: null,
  }),

  getters: {
    isMonthly: (state) => state.billingPeriod === 'monthly',
    periodLabel: (state) => (state.billingPeriod === 'monthly' ? 'USD / Mes' : 'USD / Año'),
    periodSuffix: (state) => (state.billingPeriod === 'monthly' ? '/mes' : '/año'),

    /**
     * Formatea un sueldo anual a la escala activa (mensual o anual)
     */
    displaySalary: (state) => (annualAmount) => {
      if (!annualAmount || isNaN(annualAmount)) return '$0 USD'
      const val = state.billingPeriod === 'monthly' ? annualAmount / 12 : annualAmount
      return `$${Math.round(val).toLocaleString('en-US')} USD`
    },
  },

  actions: {
    toggleBillingPeriod() {
      this.billingPeriod = this.billingPeriod === 'monthly' ? 'annual' : 'monthly'
    },

    setTab(tab) {
      this.currentTab = tab
    },

    async fetchMarketPulse() {
      this.loadingMarket = true
      this.errorMessage = null
      try {
        const data = await api.getMarketPulse()
        this.marketData = data
      } catch (err) {
        this.errorMessage = err.message
      } finally {
        this.loadingMarket = false
      }
    },

    async predictOfferSalary(payload) {
      this.predictionLoading = true
      this.errorMessage = null
      try {
        const result = await api.predictOffer(payload)
        this.predictionResult = result
        return result
      } catch (err) {
        this.errorMessage = err.message
        throw err
      } finally {
        this.predictionLoading = false
      }
    },

    async fetchCareerROI(skills, seniority, category, marketRegion) {
      this.roiLoading = true
      this.errorMessage = null
      try {
        const payload = {
          current_skills: skills || this.candidateProfile.skills,
          seniority: seniority || this.candidateProfile.seniority,
          category: category || this.candidateProfile.category,
          market_region: marketRegion || this.candidateProfile.marketRegion,
          top_n: 8,
        }
        const data = await api.getCareerROI(payload)
        this.roiData = data
        return data
      } catch (err) {
        this.errorMessage = err.message
      } finally {
        this.roiLoading = false
      }
    },

    async auditCandidateCV(file, category, marketRegion) {
      this.cvLoading = true
      this.errorMessage = null
      try {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('category', category || this.candidateProfile.category)
        formData.append('market_region', marketRegion || this.candidateProfile.marketRegion)

        const report = await api.auditCV(formData)
        this.cvAuditReport = report

        // Sincronización Automática con el Perfil Global (Regla 2 - Fase 5)
        if (report.candidate_profile?.detected_skills) {
          this.candidateProfile.skills = [...report.candidate_profile.detected_skills]
          this.candidateProfile.seniority = report.candidate_profile.detected_seniority.toLowerCase()
        }
        if (report.roi_recommendations) {
          this.roiData = {
            recommendations: report.roi_recommendations,
            base_salary_annual_usd: report.market_valuation.estimated_annual_usd,
            base_salary_monthly_usd: report.market_valuation.estimated_monthly_usd,
          }
        }
        return report
      } catch (err) {
        this.errorMessage = err.message
        throw err
      } finally {
        this.cvLoading = false
      }
    },
  },
})
