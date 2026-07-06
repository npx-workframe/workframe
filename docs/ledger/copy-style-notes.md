# Workframe in-app copy style notes

Brief reference for wizard, settings, errors, and feedback strings. **Copy only** — no layout/CSS.

## Voice and tone

- **Product name:** Workframe (capital W). Avoid "workspace" for the product; reserve "workspace" for internal/API IDs only when shown to admins (`Workframe ID`, not `Workspace ID`).
- **Audience:** Professional, security-aware operators and teammates. Credentials belong in secure UI, never chat.
- **Style:** Clear and direct. Short labels; fuller sentences in descriptions, hints, and errors. Prefer "verification code" over "OTP" in user-facing copy.
- **Billing vocabulary:** **BYOK** (bring your own keys) vs **company-pays** (shared keys). Wizard rail summaries use `BYOK` / `Company-pays`.
- **Admin role:** "Workframe admin" — not "workspace owner" in UI copy.

## Wizard ↔ settings term mapping

| Concept | Wizard (rail / step) | Settings location | Shared label |
|--------|----------------------|-------------------|--------------|
| Install identity | Business profile | Workframe Settings → Identity & Bio | Workframe name, tagline, mission |
| User identity | Your profile | Settings → Identity & Bio | Display name, tagline, about you |
| LLM keys | Model keys → Provider keys | Settings → Provider keys | Provider keys |
| OAuth identities | Model keys → Linked accounts | Settings → Linked accounts | Linked accounts |
| Model selection | Model keys → LLM models | Agent Settings → LLM models | LLM models |
| Billing mode | Model billing | (wizard-only today) | BYOK / Company-pays |
| SMTP | Email & admin | Workframe Settings → Integrations → Email delivery | SMTP host, port, from |
| Sign-in OAuth | Integrations → Sign-in | Workframe Settings → Sign-in apps | Google, GitHub, Discord, Telegram |
| Agent bots | Integrations (messaging) | Workframe Settings → Agent messaging | Discord / Telegram bot tokens |
| Invites | Invite team | Workframe Settings → Invites | Invite teammate |
| Public deploy | Public URL | — | DNS, HTTPS, test connection |

## Error and success patterns

**Errors (didactic):**

1. **What happened** — one sentence, no blame.
2. **What to do next** — hint with a concrete path (`Settings → Provider keys`, `Workframe Settings → Integrations`).
3. **Action label** when the UI can open the right place (`Connect provider`, `Choose model`).

Avoid bare "Something went wrong." Prefer "An unexpected error occurred." plus a hint. Replace dev jargon (PAT, OTP, stack) with plain language unless the audience is clearly admin/technical.

**Success / status:**

- Present tense or past tense, one line: `Profile saved. Your identity updates are live.`
- Loading: progressive verb + ellipsis: `Saving…`, `Sending invites…`
- Integrations: note deferred effect when relevant: `Changes apply on the next agent run.`

**Optional steps:**

- Rail detail: `Optional` when unset.
- Skip buttons keep explicit escape: wizard Integrations Skip; Invites Skip with hint to invite later in Workframe Settings.

## Files touched (copy pass)

Primary: `components/onboarding/*`, `components/workspace/*Settings*.tsx`, `components/settings/*`, `components/auth/EmailOtpVerification.tsx`, `lib/workframeErrors.ts`, selected dialogs and panels.

## Follow-up (not in this pass)

- Activity panel empty states and tool labels
- Browser panel chrome
- `apps/web/src/pages/dev/` showcase
- Credential mode (BYOK / company-pays) in Workframe Settings when exposed in UI
- Deeper rail/panel strings (files explorer, composer placeholders)
