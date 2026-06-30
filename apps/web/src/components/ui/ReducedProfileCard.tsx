import { Bot, ChevronRight, User } from 'lucide-react'
import { cn } from '@/lib/utils'

export type ReducedProfileCardProps = {
  type?: string
  name: string
  tagline?: string
  avatarUrl?: string | null
  onClick?: () => void
  className?: string
  asAgent?: boolean
}

export function ReducedProfileCard({
  type,
  name,
  tagline,
  avatarUrl,
  onClick,
  className,
  asAgent = false,
}: ReducedProfileCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-4 bg-card text-card-foreground border border-border rounded-xl p-3 text-left transition-all hover:border-primary hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        className
      )}
    >
      <div className="w-12 h-12 rounded-full overflow-hidden bg-muted shrink-0 flex items-center justify-center border border-border/50">
        {avatarUrl ? (
          <img src={avatarUrl} alt={name} className="w-full h-full object-cover" />
        ) : asAgent ? (
          <Bot className="w-6 h-6 text-muted-foreground" />
        ) : (
          <User className="w-6 h-6 text-muted-foreground" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <h4 className="font-semibold text-sm truncate flex items-center gap-2">
          {name}
          {type && (
            <span className="text-[10px] bg-muted text-muted-foreground px-2 py-0.5 rounded-full font-medium">
              {type}
            </span>
          )}
        </h4>
        {tagline && <p className="text-xs text-muted-foreground truncate mt-0.5">{tagline}</p>}
      </div>
      <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0 opacity-50" />
    </button>
  )
}
