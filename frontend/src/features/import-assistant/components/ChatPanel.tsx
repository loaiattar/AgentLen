import { useState } from 'react'

import { Button } from '@/components/atoms/Button'
import { Input } from '@/components/atoms/Input'
import { cn } from '@/lib/utils/cn'
import type { ConversationMessage } from '@/features/import-assistant/types'

export interface ChatPanelProps {
  messages: ConversationMessage[]
  onSend: (content: string) => void
  isSending?: boolean
}

export function ChatPanel({ messages, onSend, isSending }: ChatPanelProps) {
  const [draft, setDraft] = useState('')

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!draft.trim()) return
    onSend(draft.trim())
    setDraft('')
  }

  return (
    <div className="flex h-full flex-col gap-3 rounded-lg border border-border bg-card p-3">
      <div className="flex-1 space-y-2 overflow-y-auto">
        {messages.map((message) => (
          <p
            key={message.id}
            className={cn(
              'w-fit max-w-[85%] rounded-md px-3 py-1.5 text-sm',
              message.role === 'user' ? 'ml-auto bg-primary text-primary-foreground' : 'bg-muted',
            )}
          >
            {message.content}
          </p>
        ))}
      </div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Décrire le mapping souhaité…"
          disabled={isSending}
        />
        <Button type="submit" disabled={isSending}>
          Envoyer
        </Button>
      </form>
    </div>
  )
}
