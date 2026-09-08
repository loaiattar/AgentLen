export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export interface DraftMappingField {
  sourceField: string
  targetField: string
}
