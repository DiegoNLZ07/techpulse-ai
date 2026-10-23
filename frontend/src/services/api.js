import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Accept': 'application/json',
  },
})

// Interceptor para manejo de errores centralizado
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorMsg =
      error.response?.data?.detail ||
      error.message ||
      'Error de conexión con el servidor de TechPulse AI'
    console.error('[API Error]:', errorMsg)
    return Promise.reject(new Error(errorMsg))
  }
)

export default {
  /**
   * Obtiene métricas en vivo del mercado laboral TI
   */
  async getMarketPulse() {
    const response = await apiClient.get('/market-pulse')
    return response.data
  },

  /**
   * Predice la banda salarial oculta de una oferta por URL o formulario
   */
  async predictOffer(payload) {
    const response = await apiClient.post('/predict-offer', payload)
    return response.data
  },

  /**
   * Simula el retorno de inversión salarial por habilidad
   */
  async getCareerROI(payload) {
    const response = await apiClient.post('/career-roi', payload)
    return response.data
  },

  /**
   * Audita un CV en PDF procesado en memoria
   */
  async auditCV(formData) {
    const response = await apiClient.post('/audit-cv', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },
}
