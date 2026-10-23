import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './assets/styles.css'

// Registro Estricto de Componentes de Chart.js v4 (Regla 3 - Fase 5)
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  ArcElement,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
} from 'chart.js'

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  ArcElement,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler
)

// Configuración global de colores oscuros para Chart.js
ChartJS.defaults.color = '#94a3b8'
ChartJS.defaults.borderColor = 'rgba(255, 255, 255, 0.08)'
ChartJS.defaults.font.family = "'Plus Jakarta Sans', system-ui, sans-serif"

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
