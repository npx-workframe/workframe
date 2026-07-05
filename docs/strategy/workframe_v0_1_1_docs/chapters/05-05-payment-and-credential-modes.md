# Payment and Credential Modes

Workframe needs two separate but related concepts:

1. **Who owns the credential?**
2. **Who pays for the run?**

The answer can be user, company, Workframe, cloud provider, marketplace vendor, or a future on-chain payment rail.

## Mode 1 - Default BYOK

BYOK should be the default.

Users connect their own provider accounts:

```text
OpenAI
Anthropic
OpenRouter
Google
DeepSeek
GitHub
Linear
Slack
Discord
Telegram
Google Workspace
MCP connectors
```

This gives Workframe strong early advantages:

| Advantage | Why it matters |
|---|---|
| Low COGS | Workframe does not front every model/tool bill |
| Trust | users know which accounts are connected |
| Adoption | self-hosted users can start without Workframe billing every token |
| Portability | users can move between local, VPS, BYOC, and managed modes |
| Compliance | companies can keep provider contracts directly |

BYOK should not mean agents see raw keys. The correct flow is:

```text
user connects account
secret stored in vault
run requests capability
Workframe issues short-lived lease
agent calls broker/proxy with lease
broker resolves real secret server-side
ledger records payer and run
lease expires/revokes
```

## Mode 2 - Company-level provider keys

Company-level keys are useful when a business wants centralized spend and centralized access.

This must be opt-in and policy-controlled.

Rules:

```text
company keys are never shown to users
agents never see raw company keys
users can trigger runs only if policy allows
all company-key usage is attributed to the initiating user/run
spend appears in workspace ledger
admins can revoke, rotate, and cap usage
sensitive tools require approval
```

This unlocks a real business workflow:

> A company can pay for the team's AI labor while still knowing exactly which user, agent, card, and run consumed the spend.

## Mode 3 - Workframe credits

For hosted/provisioned cells, Workframe can sell credits.

Credits abstract:

```text
text tokens
image generation requests
video seconds
audio generation/transcription
sandbox seconds
runtime CPU/memory
external tool calls
storage
egress
marketplace tool fees
```

The user sees simple budget controls. Workframe does the metering.

## Mode 4 - Hybrid company wallet

A workspace can use multiple funding sources:

| Work type | Payment source |
|---|---|
| personal experiments | user BYOK |
| official company tasks | company provider key or company credits |
| marketplace tools | workspace wallet |
| premium model burst | Workframe credits |
| enterprise private models | customer's provider contract |

The run ledger should record the funding source per line item.

## Mode 5 - Future agent-to-agent payments

Long term, Workframe can support agent-to-agent or run-to-run payment protocols:

```text
x402-style payment-gated API calls
crypto micropayments
stablecoin wallets
agent service invoices
marketplace tool billing
usage escrow
per-output payment
```

This should not be part of the first product's critical path. But the architecture should leave room for it by making every action a billable, auditable run line item.

## Credential-mode doctrine

The critical rule:

> Users may connect accounts. Companies may connect accounts. Agents may use capabilities. Agents should not possess secrets.

This gives Workframe the ability to support BYOK, company keys, hosted credits, enterprise contracts, and future micropayments without changing the core run model.
