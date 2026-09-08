import type * as React from 'react'

export interface DashboardTemplateProps {
  filters: React.ReactNode
  content: React.ReactNode
}

export function DashboardTemplate({ filters, content }: DashboardTemplateProps) {
  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-2">{filters}</div>
      <div className="grid flex-1 gap-4">{content}</div>
    </div>
  )
}
