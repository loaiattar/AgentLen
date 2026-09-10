export interface SessionListItem {
  id: number
  data_source_id: number
  import_run_id: number
  raw_record_id: number
  external_id: string
  agent_id: number | null
  repository_id: number | null
  started_at: string | null
  ended_at: string | null
  duration_ms: number | null
  outcome: string | null
}

export interface SessionsPage {
  items: SessionListItem[]
  total: number
  limit: number
  offset: number
}

export interface ModelCallDetail {
  id: number
  session_id: number
  raw_record_id: number
  model_id: number | null
  sequence_index: number
  external_id: string | null
  started_at: string | null
  duration_ms: number | null
  input_tokens: number | null
  output_tokens: number | null
  cache_read_tokens: number | null
  cache_creation_tokens: number | null
  reasoning_tokens: number | null
  stop_reason: string | null
  status: string
  error_code: string | null
}

export interface ToolCallDetail {
  id: number
  session_id: number
  model_call_id: number | null
  raw_record_id: number
  tool_id: number
  sequence_index: number
  external_id: string | null
  started_at: string | null
  duration_ms: number | null
  status: string
  error_message: string | null
  arguments: unknown
  result_size: number | null
}

export interface SessionWithCalls {
  session: SessionListItem
  model_calls: ModelCallDetail[]
  tool_calls: ToolCallDetail[]
}

export interface TimelineEvent {
  type: 'model_call' | 'tool_call'
  event: ModelCallDetail | ToolCallDetail
}

export interface RawRecordDetail {
  id: number
  import_run_id: number
  line_number: number
  payload: unknown
  content_hash: string
}
