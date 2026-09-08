export interface ModelCall {
  id: string
  model: string
  startedAt: string
  latencyMs: number
  tokensIn: number
  tokensOut: number
}

export interface ToolCall {
  id: string
  toolName: string
  startedAt: string
  status: 'success' | 'error'
}

export interface SessionDetail {
  id: string
  source: string
  agent: string
  startedAt: string
  modelCalls: ModelCall[]
  toolCalls: ToolCall[]
}
