import {
  Bold,
  Heading2,
  Image,
  Italic,
  Link2,
  List,
  Quote,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

type MarkdownEditToolbarProps = {
  onWrap: (before: string, after?: string, placeholder?: string) => void
  onInsertLine: (prefix: string) => void
}

export function MarkdownEditToolbar({ onWrap, onInsertLine }: MarkdownEditToolbarProps) {
  return (
    <TooltipProvider delayDuration={400}>
      <div className="wf-browser-markdown-toolbar">
        <ToolbarButton label="Bold" onClick={() => onWrap('**', '**', 'bold text')}>
          <Bold aria-hidden="true" />
        </ToolbarButton>
        <ToolbarButton label="Italic" onClick={() => onWrap('*', '*', 'italic text')}>
          <Italic aria-hidden="true" />
        </ToolbarButton>
        <ToolbarButton label="Heading" onClick={() => onInsertLine('## ')}>
          <Heading2 aria-hidden="true" />
        </ToolbarButton>
        <ToolbarButton label="Link" onClick={() => onWrap('[', '](https://)', 'link text')}>
          <Link2 aria-hidden="true" />
        </ToolbarButton>
        <ToolbarButton label="Image" onClick={() => onWrap('![', '](assets/hero.png)', 'alt text')}>
          <Image aria-hidden="true" />
        </ToolbarButton>
        <ToolbarButton label="Quote" onClick={() => onInsertLine('> ')}>
          <Quote aria-hidden="true" />
        </ToolbarButton>
        <ToolbarButton label="List" onClick={() => onInsertLine('- ')}>
          <List aria-hidden="true" />
        </ToolbarButton>
      </div>
    </TooltipProvider>
  )
}

function ToolbarButton({
  label,
  onClick,
  children,
}: {
  label: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button type="button" variant="ghost" size="icon" className="wf-browser-markdown-toolbar__btn" onClick={onClick}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
