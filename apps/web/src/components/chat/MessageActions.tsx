import { Reply, SmilePlus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { AgentAvatar } from '@/components/ui/AgentAvatar'
import type { ChatReaction } from '@/lib/chatTypes'

const REACTION_OPTIONS = ['👍', '❤️', '🎉', '🔥', '😂', '😮', '😢', '🙏', '👀', '✅', '🚀', '💡']

type MessageActionsProps = {
  onReply?: () => void
  onReact?: (emoji: string) => void
}

export function MessageActions({ onReply, onReact }: MessageActionsProps) {
  if (!onReply && !onReact) return null

  return (
    <TooltipProvider delayDuration={350}>
      <div className="wf-message-actions" role="toolbar" aria-label="Message actions">
        {onReply ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="toolbar"
                size="toolbarIcon"
                className="wf-message-actions__button"
                aria-label="Reply to message"
                onClick={onReply}
              >
                <Reply aria-hidden="true" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Reply</TooltipContent>
          </Tooltip>
        ) : null}

        {onReact ? (
          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="toolbar"
                    size="toolbarIcon"
                    className="wf-message-actions__button"
                    aria-label="React to message"
                  >
                    <SmilePlus aria-hidden="true" />
                  </Button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent side="top">React</TooltipContent>
            </Tooltip>
            <DropdownMenuContent align="end" className="wf-message-reaction-menu">
              <div className="wf-message-reaction-menu__grid" aria-label="Choose a reaction">
                {REACTION_OPTIONS.map((emoji) => (
                  <DropdownMenuItem
                    key={emoji}
                    className="wf-message-reaction-menu__item"
                    aria-label={`React with ${emoji}`}
                    onSelect={() => onReact(emoji)}
                  >
                    <span aria-hidden="true">{emoji}</span>
                  </DropdownMenuItem>
                ))}
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
    </TooltipProvider>
  )
}

export function MessageReactions({
  reactions,
  onToggle,
}: {
  reactions: ChatReaction[]
  onToggle?: (emoji: string) => void
}) {
  if (!reactions.length) return null
  return (
    <TooltipProvider delayDuration={250}>
      <div className="wf-message-reactions" aria-label="Message reactions">
        {reactions.map((reaction) => {
          const names = reaction.reactors.map((reactor) => reactor.displayName).join(', ')
          return (
            <Tooltip key={reaction.emoji}>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="toolbar"
                  size="toolbarText"
                  className="wf-message-reaction"
                  aria-label={`${reaction.emoji}, ${reaction.count} ${reaction.count === 1 ? 'reaction' : 'reactions'}${names ? ` from ${names}` : ''}`}
                  aria-pressed={reaction.reacted}
                  onClick={() => onToggle?.(reaction.emoji)}
                >
                  <span aria-hidden="true">{reaction.emoji}</span>
                  <span>{reaction.count}</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top" className="wf-message-reaction-tooltip">
                {reaction.reactors.length ? (
                  <div className="wf-message-reaction-tooltip__people">
                    {reaction.reactors.map((reactor) => (
                      <span key={reactor.userId} className="wf-message-reaction-tooltip__person">
                        <AgentAvatar
                          src={reactor.avatarUrl}
                          name={reactor.displayName}
                          size="xs"
                          className="wf-message-reaction-tooltip__avatar"
                        />
                        <span>{reactor.displayName}</span>
                      </span>
                    ))}
                  </div>
                ) : (
                  <span>{reaction.count} {reaction.count === 1 ? 'reaction' : 'reactions'}</span>
                )}
              </TooltipContent>
            </Tooltip>
          )
        })}
      </div>
    </TooltipProvider>
  )
}
