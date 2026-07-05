# Connectors, Accounts, and Identity

Workframe should let users and companies connect the accounts where business already happens.

## Account connections

Priority connectors:

```text
Telegram
Discord
Slack
GitHub
Linear
Google Workspace
Gmail
Google Drive
Google Calendar
Vercel
Netlify
Stripe
Figma
Notion
MCP servers
custom API keys
```

## Connector doctrine

Each connector must answer:

```text
who connected it?
who owns it?
which workspace can use it?
which agents can request it?
which actions are allowed?
which actions require approval?
which runs used it?
what did it cost?
what data was read or written?
```

## User vs company accounts

| Account type | Example | Default policy |
|---|---|---|
| User-owned | personal GitHub, personal Slack, personal OpenAI key | only the owner can delegate |
| Company-owned | workspace GitHub app, company OpenAI key, deployment provider | admins define usage policy |
| Service-owned | Workframe-managed credits, marketplace tool account | billed to workspace or account |
| External vendor | premium agent/tool marketplace | accessed through marketplace contract |

## Domain allowlist

For VPS/self-hosted business cells, domain allowlist is a major trust feature:

```text
only users with @mybusiness.com can request access
contractors need explicit invite
agents cannot invite humans
admins approve external guests
workspace owners can disable public signup entirely
```

## MCP connector posture

MCP connectors are powerful but risky. Workframe should treat MCP servers as tools with declared capabilities:

```text
server identity
available tools
required secrets
allowed network destinations
workspace scope
risk tier
approval requirement
run audit
```

MCP should not become an unbounded backdoor into user data or external tools.
