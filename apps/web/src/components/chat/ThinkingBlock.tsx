import { ToolRunCard } from '@/components/chat/ToolRunCard'

type ThinkingBlockProps = {
  text: string
  live?: boolean
}

export function ThinkingBlock({ text, live = false }: ThinkingBlockProps) {
  return (
    <ToolRunCard
      glyph="thinking"
      segment={{
        kind: 'tool',
        name: 'Thinking',
        status: live ? 'running' : 'done',
        output: text,
        preview: text,
      }}
    />
  )
}
