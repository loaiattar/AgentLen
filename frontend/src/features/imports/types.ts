export type ImportStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface ImportItem {
  id: string
  fileName: string
  status: ImportStatus
  createdAt: string
  rowCount: number
}
