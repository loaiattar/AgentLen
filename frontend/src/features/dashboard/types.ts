export interface DashboardFilters {
  source?: string
  agent?: string
  model?: string
  period?: '24h' | '7d' | '30d'
}

export interface DashboardMetrics {
  totalSessions: number
  totalCalls: number
  errorRate: number
  averageLatencyMs: number
}
