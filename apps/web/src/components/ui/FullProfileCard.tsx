import { Bot, User } from 'lucide-react'
import { cn } from '@/lib/utils'

export type FullProfileCardProps = {
  type?: string
  name: string
  slug?: string
  tagline?: string
  bio?: string
  avatarUrl?: string | null
  asAgent?: boolean
  className?: string
  status?: string
}

export function FullProfileCard({
  type,
  name,
  slug,
  tagline,
  bio,
  avatarUrl,
  asAgent = false,
  className,
  status,
}: FullProfileCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center bg-card border border-border rounded-2xl shadow-sm p-6 relative overflow-hidden group w-full',
        className
      )}
    >
      {/* Background flourish */}
      <div className="absolute top-0 left-0 w-full h-24 bg-gradient-to-br from-primary/10 to-primary/5 dark:from-primary/20 dark:to-primary/5 pointer-events-none" />

      <div className="w-24 h-24 rounded-full border-4 border-card bg-muted shadow-md relative z-10 flex items-center justify-center overflow-hidden mb-4">
        {avatarUrl ? (
          <img src={avatarUrl} alt={name} className="w-full h-full object-cover" />
        ) : asAgent ? (
          <Bot className="w-10 h-10 text-muted-foreground" />
        ) : (
          <User className="w-10 h-10 text-muted-foreground" />
        )}
      </div>

      <div className="text-center z-10 w-full space-y-1">
        <h3 className="text-xl font-bold text-card-foreground flex justify-center items-center gap-2">
          {name || 'Unnamed'}
          {type && (
            <span className="text-[10px] tracking-wider uppercase bg-muted text-muted-foreground px-2 py-0.5 rounded-full font-bold">
              {type}
            </span>
          )}
        </h3>
        {slug && <p className="text-sm font-mono text-muted-foreground">@{slug}</p>}
        {tagline && <p className="text-sm font-medium text-primary mt-2">{tagline}</p>}
        {status && <p className="text-xs text-muted-foreground mt-1">{status}</p>}
      </div>

      {bio && (
        <div className="mt-6 w-full text-left">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            {asAgent ? 'Instructions / Soul' : 'Bio'}
          </h4>
          <p className="text-sm text-card-foreground leading-relaxed bg-muted/30 p-3 rounded-lg border border-border/50">
            {bio}
          </p>
        </div>
      )}
    </div>
  )
}
