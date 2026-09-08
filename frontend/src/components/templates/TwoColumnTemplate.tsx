import type * as React from 'react'

export interface TwoColumnTemplateProps {
  main: React.ReactNode
  side: React.ReactNode
}

export function TwoColumnTemplate({ main, side }: TwoColumnTemplateProps) {
  return (
    <div className="grid h-full grid-cols-1 gap-4 p-4 lg:grid-cols-[1fr_320px]">
      <div className="min-w-0">{main}</div>
      <aside className="min-w-0">{side}</aside>
    </div>
  )
}
