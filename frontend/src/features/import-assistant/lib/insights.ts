import type { AiInsight } from '@/components/ui/AiPanel'
import { confidenceLabel, rationaleBody } from '@/features/import-assistant/lib/mapping'
import type { ProposalResponse } from '@/features/import-assistant/types'

export function proposalInsights(proposal: ProposalResponse): AiInsight[] {
  const insights: AiInsight[] = []

  if (!proposal.validation.valid) {
    insights.push({
      title: 'Validation failed',
      body: proposal.validation.errors.map((error) => error.message).join(' ') || 'The mapping is not valid yet.',
      tone: 'warning',
    })
  }

  proposal.rationale.forEach((item, index) => {
    insights.push({
      title: [item.target ?? `Proposed field ${index + 1}`, item.source].filter(Boolean).join(' ← '),
      body: rationaleBody(item),
      confidence: confidenceLabel(item.confidence),
    })
  })

  proposal.ambiguities.forEach((item, index) => {
    insights.push({
      title: item.field ?? `Ambiguous field ${index + 1}`,
      body: [item.question, item.options?.join(' / ')].filter(Boolean).join(' '),
      tone: 'warning',
    })
  })

  proposal.unmapped_fields.forEach((item, index) => {
    insights.push({
      title: item.path ?? `Unmapped field ${index + 1}`,
      body: item.reason ?? 'Left unmapped.',
    })
  })

  if (insights.length === 0) {
    insights.push({
      title: 'Proposal ready',
      body: 'No ambiguities. Review the mapping, then accept. The assistant does not apply it.',
    })
  }

  return insights
}
