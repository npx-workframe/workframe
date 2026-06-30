import type { CheckboxListOption } from '@/components/dialogs/CheckboxListDialog'
import type { SelectListOption } from '@/components/dialogs/SelectListDialog'

export const HERMES_MESSAGING_CHANNELS: CheckboxListOption[] = [
  {
    id: 'discord',
    label: 'Discord',
    description: 'Gateway bot + slash commands via hermes-discord toolset',
  },
  {
    id: 'telegram',
    label: 'Telegram',
    description: 'Bot API long-polling or webhook',
  },
  {
    id: 'slack',
    label: 'Slack',
    description: 'Socket Mode app with bot + app tokens',
  },
  {
    id: 'whatsapp',
    label: 'WhatsApp',
    description: 'Business API bridge (hermes-whatsapp)',
  },
  {
    id: 'signal',
    label: 'Signal',
    description: 'Optional signal-cli linked device',
  },
  {
    id: 'localhost',
    label: 'Localhost chat',
    description: 'Built-in web chat surface on the gateway port',
  },
]

export const HERMES_LLM_MODELS: SelectListOption[] = [
  {
    id: 'anthropic/claude-sonnet-4',
    label: 'Claude Sonnet 4',
    description: 'Default balanced model via OpenRouter',
  },
  {
    id: 'openai/gpt-4.1',
    label: 'GPT-4.1',
    description: 'OpenAI-compatible provider',
  },
  {
    id: 'google/gemini-2.5-pro',
    label: 'Gemini 2.5 Pro',
    description: 'GOOGLE_API_KEY / GEMINI_API_KEY',
  },
  {
    id: 'deepseek/deepseek-chat',
    label: 'DeepSeek Chat',
    description: 'DEEPSEEK_API_KEY',
  },
  {
    id: 'nous/hermes-4',
    label: 'Hermes 4',
    description: 'Nous Portal OAuth (hermes auth)',
  },
]

export const HERMES_LLM_PROVIDERS: SelectListOption[] = [
  { id: 'openrouter', label: 'OpenRouter', description: 'OPENROUTER_API_KEY' },
  { id: 'anthropic', label: 'Anthropic', description: 'ANTHROPIC_API_KEY' },
  { id: 'openai', label: 'OpenAI', description: 'Direct API key' },
  { id: 'nous', label: 'Nous Portal', description: 'OAuth via hermes auth' },
  { id: 'google', label: 'Google Gemini', description: 'GEMINI_API_KEY' },
  { id: 'deepseek', label: 'DeepSeek', description: 'DEEPSEEK_API_KEY' },
]

export type DialogDemoId =
  | 'confirm-restart'
  | 'confirm-disconnect'
  | 'prompt-discord-token'
  | 'prompt-openrouter-key'
  | 'select-model'
  | 'select-provider'
  | 'checkbox-channels'
