# Audit 0027 ΓÇö Agent Vault Comparison

Date: 2026-07-04
Status: advisory architecture/security audit
Scope: Workframe credential vault, per-turn credential leases, internal LLM proxy, public multi-user deployment posture
External reference: Infisical Agent Vault ΓÇö open-source credential proxy and vault for agents

## Executive summary

Infisical Agent Vault is strongly aligned with Workframe's credential-security direction. Both systems are built around the same core invariant: agents should not receive long-lived raw credentials. Instead, a trusted broker should hold secrets, issue bounded capabilities, and inject the real credential only when making an authorized upstream request.

Workframe already contains an embedded version of this pattern:

- API-owned credential vault.
- Envelope-encrypted secrets.
- Per-run / per-turn lease tokens.
- Internal LLM proxy that resolves a lease into the upstream provider credential.
- Public deployment posture that keeps the gateway away from the vault database and raw provider secrets.

Agent Vault is narrower but more mature as a standalone security primitive. Its strongest lesson for Workframe is that credential brokering should become unavoidable at the network boundary. A lease-token proxy is not sufficient if an agent with terminal access can bypass the broker and reach arbitrary upstream APIs directly.

The architectural correction is:

> Credential brokers must be unavoidable. Public multi-user deployments should force outbound agent traffic through the broker rather than relying on agent cooperation, environment variables, or convention.

## What Agent Vault is

Agent Vault is a credential proxy and vault for AI agents. It is designed to sit between agent runtimes and external APIs. The agent sends traffic through a controlled proxy; the vault/proxy resolves policy and injects credentials outside the agent's direct reach.

The important characteristics are:

- Secrets are not exposed as raw environment variables inside the agent runtime.
- Existing tools and SDKs can often be supported by standard proxy configuration.
- The credential service can log, filter, and deny outbound requests.
- The proxy can become a central enforcement point for egress, credential scope, and auditability.

This is not a full agent operating system. It is a security subsystem. Workframe remains broader: UI, rooms, auth, runtime profiles, delegation, installer, supervisor, files, and Hermes lifecycle.

## Workframe equivalent primitives

Workframe already has several matching primitives.

### API-owned credential vault

Workframe's credential vault stores provider secrets in the API data directory, not inside the Hermes gateway profile. The vault uses envelope encryption with a key-encryption key and per-secret data-encryption keys.

Relevant source:

- `services/workframe-api/credential_vault.py`
- `services/workframe-api/vault_kek.py`
- `services/workframe-api/zk_auth.py`

Design intent:

- Store raw secrets only inside the API trust boundary.
- Persist encrypted ciphertext at rest.
- Avoid mounting the vault database into the agent gateway container.

### Per-turn credential leases

Workframe issues opaque `wf_rt_...` lease tokens for runs. The agent receives a lease token, not the underlying provider key. The lease is bound to run metadata, payer user, workspace, provider, credential binding, profile slug, and expiry.

Relevant source:

- `services/workframe-api/turn_credentials.py`

Design intent:

- Bound lifetime.
- Bound profile.
- Bound payer / credential owner.
- Revocable by run ID.
- Usable as the agent-facing credential value.

### Internal LLM proxy

Workframe's LLM proxy validates the lease token, checks provider match, validates profile binding, resolves the secret from the vault, and injects the provider-specific upstream authentication header.

Relevant source:

- `services/workframe-api/llm_proxy.py`
- `services/workframe-api/internal_proxy_auth.py`

Design intent:

- Hermes sends lease token.
- API validates the token.
- API resolves the raw provider key.
- API forwards to OpenRouter/OpenAI/Anthropic/Google/DeepSeek.
- Agent never needs the raw provider key.

### Public deployment controls

Workframe public deploy documentation already captures several matching controls:

- BYOK default.
- `user_only` providers do not fall back to workspace keys.
- Vault encrypted at rest.
- Gateway uses short-lived lease tokens.
- Gateway should not receive vault DB or raw auth secrets.
- Public mode requires HTTPS, vault KEK, SMTP, proxy token, supervisor token, and auth secrets.

Relevant docs:

- `docs/public/security.md`
- `docs/public/audit.md`
- `docs/public/architecture.md`
- `infra/compose/workframe/PUBLIC_DEPLOY.md`

## Similarities

| Concern | Agent Vault | Workframe |
| --- | --- | --- |
| Raw credential exposure | Avoid exposing raw secrets to agents | Same intended invariant via API vault + leases |
| Agent-facing credential | Proxy-mediated credential / token | `wf_rt_...` lease token |
| Secret storage | Dedicated vault | API-owned encrypted vault |
| Request mediation | Credential proxy | Internal LLM proxy |
| Auditability | Proxy can observe outbound requests | Workframe can observe mediated LLM/provider calls |
| Multi-agent use | Designed for agent runtimes | Designed for Hermes profiles and multi-user Workframe profiles |
| Scope | Generic HTTP/S API proxy | Currently narrower, strongest for LLM/provider paths |

## Differences

### 1. Agent Vault is generic; Workframe is currently provider-specific

Agent Vault is designed as a general credential proxy for arbitrary APIs. Workframe's current proxy is strongest for LLM providers and Workframe-known provider flows.

Workframe should generalize from `llm_proxy` to a broader `credential_broker` or `egress_broker` model.

### 2. Agent Vault emphasizes transparent proxy ergonomics

Agent Vault can work with existing CLIs and SDKs through proxy configuration. Workframe currently requires tools to use Workframe's internal proxy endpoint or a Workframe-configured provider base URL.

That is acceptable for native Workframe-managed LLM calls, but weaker for arbitrary terminal tools.

### 3. Agent Vault frames the problem as egress control

This is the key lesson.

Environment variables and proxy settings are advisory unless the container/network policy makes them unavoidable. If an agent has terminal access and unrestricted outbound internet, it can bypass an application-level proxy.

Workframe currently documents full terminal availability in public mode. That can be defensible only if credential-bearing traffic is either:

- impossible without the broker, because the raw secrets are absent; and
- unable to bypass broker policy, because outbound egress is constrained.

The first condition is mostly present. The second is not yet explicit enough.

## Security gap

### Gap: broker bypass through direct egress

Workframe's current design protects raw stored secrets, but a public multi-user agent runtime with terminal access still needs a clear network-level egress posture.

The risk is not that the agent reads `OPENAI_API_KEY` from its environment if Workframe configured things correctly. The risk is broader:

- future provider credentials may accidentally be mounted or propagated;
- tools may obtain credentials through OAuth flows or files;
- agents may call unsupported APIs outside the Workframe proxy;
- a malicious dependency may exfiltrate data directly;
- policy and spend controls are only enforceable on brokered traffic.

A credential broker should be an enforcement boundary, not just a convenience path.

## Recommended invariant

Add this as a Workframe public deployment invariant:

> In `public_multi_user`, agent runtime containers must not have unrestricted outbound network access. Credential-bearing outbound traffic must be routed through a Workframe-approved broker or explicitly denied.

Corollaries:

1. The gateway should not receive raw provider secrets.
2. The gateway should not mount the API vault database.
3. The gateway should receive only short-lived lease tokens or broker session tokens.
4. The gateway should not be able to reach the supervisor control plane.
5. The gateway should not be able to bypass the broker for credential-mediated providers.
6. Brokered requests should be attributable to user, workspace, profile, run, provider, and credential binding.

## Recommended architecture

### Near-term: keep native Workframe broker

Do not replace the current vault/lease/proxy with Agent Vault immediately. Workframe's native implementation is already integrated with:

- users;
- workspace membership;
- provider ownership;
- delegation payer semantics;
- Hermes profile slugs;
- install modes;
- API authorization.

Replacing it now would create integration churn without fixing the primary gap by itself.

### Medium-term: generalize the internal proxy

Introduce a broker abstraction:

```text
agent runtime
  -> Workframe broker endpoint
  -> policy check
  -> lease validation
  -> vault secret resolution
  -> upstream API
```

Suggested module direction:

```text
services/workframe-api/
  credential_broker.py
  egress_policy.py
  broker_routes.py
  broker_audit.py
```

Do not overbuild this initially. Start by extracting shared logic from `llm_proxy.py` and applying it to a small number of known provider classes.

### Medium-term: add forced-egress public profile

For public multi-user mode, add an explicit deployment option:

```bash
WORKFRAME_FORCE_AGENT_EGRESS_BROKER=true
```

Expected behavior:

- Gateway cannot directly reach arbitrary internet except approved broker destinations.
- Broker can reach upstream APIs.
- API/supervisor control network remains inaccessible to gateway except explicitly required routes.
- Verification script fails public mode if forced-egress controls are requested but absent.

Implementation can use Docker network policy, sidecar routing, or a documented host firewall profile. The exact mechanism can evolve; the invariant should not.

### Long-term: support external broker backend

Add an adapter boundary so Workframe can eventually use either native broker or Agent Vault / Infisical-backed broker.

Possible config:

```bash
WORKFRAME_CREDENTIAL_BROKER=native
# later:
# WORKFRAME_CREDENTIAL_BROKER=agent-vault
# WORKFRAME_CREDENTIAL_BROKER=infisical
```

Do not add this config until there is a real adapter implementation. Premature flags are configuration debt.

## Concrete implementation tasks

### Critical

1. Add a public-mode egress invariant to `docs/public/security.md` and `infra/compose/workframe/PUBLIC_DEPLOY.md`.
2. Extend `scripts/workframe/verify-public-deploy.sh` to check and report current egress posture.
3. Add a failing or warning check when `public_multi_user` has unrestricted gateway outbound access and `WORKFRAME_FORCE_AGENT_EGRESS_BROKER=true`.

### High

4. Extract common broker authorization and lease validation out of `llm_proxy.py` into a provider-neutral broker layer.
5. Add structured broker audit events:
   - timestamp;
   - user ID;
   - workspace ID;
   - profile slug;
   - run ID;
   - provider;
   - upstream host;
   - status code;
   - denied reason.
6. Add tests proving a lease is rejected when:
   - expired;
   - revoked;
   - provider mismatch;
   - profile mismatch;
   - missing internal proxy token;
   - missing profile header where required.

### Medium

7. Add an `egress_policy.md` document explaining supported public-mode network topologies.
8. Add optional Agent Vault comparison notes to the architecture doc without creating a hard dependency.
9. Create a spike branch for Agent Vault sidecar integration only after the native egress invariant is documented and tested.

## Success criteria

Audit 0027 is addressed when all of the following are true:

- Workframe docs state that public multi-user credential brokers must be unavoidable.
- Public deploy verification reports whether gateway egress is unrestricted, brokered, or unknown.
- The gateway has no raw LLM/provider secrets in environment or mounted files.
- The gateway cannot reach the supervisor control network.
- Brokered requests are attributable to run/profile/user/workspace/provider.
- The lease validation path is covered by tests.
- There is a documented path to support an external Agent Vault backend without replacing Workframe's user/workspace/delegation model.

## Decision

Agent Vault should not be treated as a competitor to Workframe. It should be treated as confirmation that Workframe's vault/lease/proxy direction is correct, plus a warning that Workframe needs a stronger forced-egress story before public multi-user deployments are considered hardened.

Final recommendation:

- Keep Workframe's native credential vault and lease model.
- Generalize the broker beyond LLM calls.
- Make broker bypass impossible or explicitly detectable in public mode.
- Consider Agent Vault as a future optional backend, not an immediate replacement.
