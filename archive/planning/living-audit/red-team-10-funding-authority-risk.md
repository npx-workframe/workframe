# Red team 10 — funding authority, delegation, and silent-key risk

Temporary living-audit planning material. Not public release doctrine. Planning only; no product source-code changes are implied by this file.

## Inspected ref / SHAs

Repository resolved directly: `npx-workframe/workframe`, default branch `main`.

| Area | Path | Blob SHA |
|---|---|---|
| Entry | `README.md` | `b97cd64e4f899dc758bb73a0e04ec9a89a344317` |
| Agent rules | `AGENTS.md` | `f648f29fdb9569c3bb7a5c6c8e178173582cde03` |
| Repo map | `START_HERE.md` | `cf65246dc937256099d8297e79487635c3b724d2` |
| Harness docs | `.harness/README.md` | `e21ce2d468b8f8baaa4660edf7054bd04d4f7ec0` |
| Harness scenarios | `.harness/feature_list.json` | `ed32c988e668d813e99d8f332ebd2d22b3fbb95e` |
| Harness runner | `.harness/verify.mjs` | `e8785ebc99091abfa295e9062613c4db208c840f` |
| Monorepo package | `package.json` | `7b8232a887d2c3558078c18cbbc6cac20051f363` |
| Installer package | `packages/create-workframe/package.json` | `72fc7bf7625c8e786baf0f9d44c389e5f4ad6547` |
| Docs index | `docs/README.md` | `e8a2a847ef29f784655f348fb1a53e535ff4915e` |
| Security docs | `docs/public/security.md` | `3ab7a2408a92be7e8b6115bd798684b342cd5424` |
| Session docs | `docs/public/session-architecture.md` | `65481ee7cac21e4575b3284be7a6d5d2bdcd1c62` |
| Operations docs | `docs/public/operations.md` | `06dae7747e242f59a6c82b1ea5d01a101d8a0e4b` |
| Latest planning pass | `docs/living-audit/multi-user-provider-policy.md` | `7a02a4c87250458dc2826df6aaf63a9b91d24480` |
| Previous red-team pass | `docs/living-audit/red-team-09-surface-contract-risk.md` | `4f77155336907bd863b1ed6f6b7fd8db7ad72bae` |
| Operator log | `operations/log.md` | `ea08be43dc1c2b5bd41b9557459593c3727bbdac` |

## Planning slice challenged

Adversarial review of `multi-user-provider-policy.md`: whether BYOK, company-pays, hybrid, delegated work, and per-user profiles can be made understandable and safe without accidentally creating key lending, silent workspace fallback, or misleading audit semantics.

## Current-state facts

- README frames Workframe as a multi-user web shell around Hermes, not yet an adapter-neutral runtime broker.
- Security docs state BYOK is default, `user_only` providers have no workspace fallback, credentials are vault/lease mediated, and public multi-user mode depends on HTTPS, SMTP, vault KEK, proxy token, supervisor token, invite-only auth, dashboard gating, runtime RBAC, allowlisted gateway env, and supervisor path blocking.
- Session docs bind browser chat to per-user runtime profiles named `u-{user}-{template}` so each member's keys and chat history remain isolated.
- Operations docs say each user connects LLM keys and that agent chat / space @mentions require the acting user to have an LLM provider connected.
- The latest planning pass says delegated work should record actor, assignee/profile owner, payer, runtime, provider, model, and credential scope, while preserving the rule that delegation grants assignment authority, not key lending.
- Harness evidence currently has provider/model checks, but no multi-user funding gate, no company-pays explicitness gate, no delegated-run payer gate, and no minimal run receipt gate.

## Red-team contradictions / weak assumptions

### 1. `acting user has key` conflicts with `profile owner pays`

Operations docs say the acting user needs a connected provider. The planning pass says delegated runs generally charge the profile owner unless workspace/company policy applies. Both can be valid, but not in the same unqualified rule.

Risky ambiguity:

```text
Bob triggers Alice agent
  acting_user_has_key? Bob
  profile_owner_pays? Alice
  profile_credentials? Alice
```

If Bob's key is used, Alice did not pay. If Alice's key is used, delegation can become key lending unless Alice explicitly authorized that profile to execute delegated tasks. If workspace key is used, neither user's BYOK boundary is the payer.

### 2. Company-pays can silently erase BYOK expectations

A workspace key is convenient, but it changes the trust model. In BYOK, failure is useful: no key means no run. In company-pays or hybrid, an agent may run even when the user has no key, causing users to misunderstand cost, authority, privacy, and data exposure.

Rule to challenge: `fallback exists` must never mean `fallback is invisible`.

### 3. `user_only` is under-specified as an enforcement boundary

The docs say `user_only` providers have no workspace fallback. That is necessary, but insufficient. `user_only` should be treated as a provider-binding invariant with a failing test, not a documentation phrase.

Minimum invariant:

```text
request.provider.user_only == true
  and selected_binding.owner_scope != user
  -> deny before runtime invocation
```

### 4. Funding policy is not only billing; it is authority

The planning pass correctly avoids billing-grade accounting, but `payer` still controls which credential is allowed to be leased to the runtime. That makes funding policy part of the execution security boundary.

Bad mental model:

```text
funding = accounting metadata after run
```

Better model:

```text
funding_authority = pre-run credential lease authorization
receipt = evidence of the decision and outcome
```

### 5. Minimal receipts may create false audit confidence

A non-billing receipt is useful, but if it omits the authorization decision it can become decorative. A receipt that says `workspace paid` without recording why a workspace credential was permitted is not enough for debugging or trust.

### 6. Public multi-user cannot rely on installer copy alone

The funding policy must be visible at three times:

```text
before invite acceptance
before first run
inside activity/receipt after run
```

If the wizard stores the policy but UI/runtime surfaces do not show the effective decision, invited users still experience opaque execution.

### 7. Hybrid mode is too complex for the next proof unless constrained

Hybrid looks attractive but multiplies cases:

```text
user key present + workspace key present
user key absent + workspace fallback allowed
user_only provider + workspace key present
delegated profile + actor key present
assignee profile + assignee key absent
admin changes policy during session
```

For v0.1.x, hybrid should either be disabled or limited to a visible `prefer_user_key_else_block` posture until receipts and denial states are reliable.

## Hidden complexity inventory

| Area | Hidden failure mode | Simpler posture |
|---|---|---|
| BYOK | Actor/profile-owner ambiguity | One rule per run kind; deny ambiguous delegated runs. |
| Company-pays | Workspace key silently used | Admin opt-in plus visible pre-run payer banner. |
| Hybrid | Too many fallback paths | Defer or constrain to explicit fallback only after receipt gate. |
| Delegation | Assignment becomes key lending | Profile owner must grant execution authority separately from assignment visibility. |
| User-only providers | Docs promise no fallback but runtime selects workspace key | Pre-runtime invariant and failing test. |
| Receipts | Decorative audit events | Include decision reason and credential scope, not just status. |
| Public mode | Funding hidden after invite | Show policy before invite acceptance and before run. |
| Adapter future | Provider/funding tied to Hermes profile layout | Define binding objects independent of Hermes before adding adapters. |

## Simpler first-principles alternative

Define a `RunAuthorityGate` before implementing broad multi-user/company-pays behavior:

```text
RunAuthorityGate
  actor_user_id
  requested_agent_profile_id
  profile_owner_user_id
  run_context: dm | space_mention | kanban_delegation | loop | admin_test
  runtime_kind: managed_hermes for v0.1.x
  provider_kind
  provider_user_only
  workspace_funding_mode
  candidate_bindings: redacted ids only
  selected_binding_scope: user | workspace | none
  selected_payer_scope: user | workspace | none
  delegation_authority: none | assign_only | execute_allowed
  fallback_used: boolean
  decision: allow | deny
  decision_reason
```

No runtime invocation should occur until this gate returns `allow`.

## Stricter v0.1.x policy proposal

```text
single_user_local
  -> BYOK only
  -> actor == profile_owner
  -> deny if no user key

trusted_team / public_multi_user, BYOK
  -> actor can message own profiles
  -> delegated runs require execute_allowed grant from profile owner
  -> deny if selected profile owner has no usable key

company_pays
  -> admin opt-in before invites
  -> workspace LLM binding may be used only for non-user-only providers
  -> show workspace-pays before run

hybrid
  -> defer, or restrict to explicit admin/user confirmation per fallback path
```

This is less flexible, but easier to prove.

## Security issues to pin before implementation

1. A user must not cause another user's personal provider key to be used merely by mentioning that user's agent.
2. A workspace key must not be used for a `user_only` provider under any funding mode.
3. A workspace key must not silently satisfy a missing user key in BYOK mode.
4. Delegation needs two grants: assignment visibility and execution authority.
5. Every allowed run needs a pre-run funding/credential decision and a post-run receipt derived from that decision.
6. Policy changes during an active session must not retroactively change an already-started run's payer or credential scope.
7. Public-mode invitees must see whether their runs are blocked, BYOK-funded, or workspace-funded before they act.

## Proposed migration / refactor steps

1. Rename the planning concept from `RunFundingDecision` to `RunAuthorityDecision` or make funding a subfield of authority.
2. Define run-context-specific payer rules before adding more UI for provider/model choice.
3. Add `delegation_authority = assign_only | execute_allowed` to the planning model.
4. Make `user_only no fallback` a release-blocking validation gate.
5. Keep hybrid disabled or visibly experimental until receipts prove fallback decisions.
6. Require public/trusted-team invite flow to display funding policy before acceptance.
7. Emit activity from `RunAuthorityDecision`, not from inferred provider availability.
8. Keep non-Hermes adapters inert until `RunAuthorityGate` is runtime-neutral.

## Diagnostic conclusion

The multi-user funding plan is directionally correct, but it is still framed too much like billing/product policy. In Workframe, payer selection determines credential lease authority, so it belongs in the security path before runtime invocation. The simplest credible next product path is not full BYOK/company/hybrid flexibility; it is a narrow, provable `RunAuthorityGate` with explicit denials, visible payer state, and receipts that explain why a credential was allowed.

## Next best planning target

Final convergence synthesis, constrained by the new red-team conclusion: v0.1.x should prove managed-Hermes package truth, cell authority, surface contracts, and run authority before claiming adapter-first multi-runtime execution.
