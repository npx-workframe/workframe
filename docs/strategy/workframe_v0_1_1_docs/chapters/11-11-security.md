# Required Product Security

## Security doctrine

Agents are useful precisely because they can act. That makes them dangerous if they receive ambient authority.

The required posture:

```text
agents do not receive raw secrets
agents do not get whole-workspace filesystem access by default
agents do not get unrestricted outbound internet by default
agents do not inherit user OAuth tokens automatically
agents do not create broader sub-agents
agents do not deploy production without policy
agents do not spend unlimited money
```

## Credential security

All sensitive credentials should flow through the broker model:

```text
user/company connects account
secret is stored in vault/KMS
run requests capability
policy evaluates request
short-lived lease is issued
broker resolves real credential server-side
agent receives only opaque token/capability
run ends, lease expires or is revoked
ledger records usage
```

## Company provider keys without exfiltration

A company-level provider key can be safe enough if:

```text
users cannot read it
agents cannot print it
runtime only receives lease tokens
all calls go through proxy/broker
ledger attributes cost to user/agent/run/card
admins can revoke and rotate
spend is capped
sensitive output requires approval
```

The key idea is not secrecy by prompt instruction. It is secrecy by architecture.

## Filesystem security

Every run should eventually have a file manifest:

```json
{
  "run_id": "run_123",
  "mounts": [
    { "source": "project://game/repo", "target": "/work/repo", "mode": "rw" },
    { "source": "project://game/brand", "target": "/work/brand", "mode": "ro" }
  ],
  "denied": ["workspace://other-project/*", "user://private/*"]
}
```

A run should not see files merely because they exist somewhere in the same VPS or volume.

## Egress security

Exfiltration cannot be fully prevented if an agent can both read sensitive data and communicate freely. Therefore Workframe should separate access and output.

Controls:

```text
default-deny outbound internet
allowlist model providers through model gateway
allowlist GitHub/GitLab through tool broker
allow package registries through cache/proxy
block direct SMTP/chat/webhooks unless brokered
block cloud metadata/private IP access
log network destinations
scan/redact outputs where possible
require approval for external sends
```

## Tool security

Tools should be capabilities, not raw shell access.

Example:

```json
{
  "tool": "github.open_pull_request",
  "scope": {
    "workspace": "game-studio",
    "repo": "space-runner",
    "branch_prefix": "agent/",
    "actions": ["create_branch", "commit", "open_pr"]
  },
  "approval_required": false,
  "ttl_seconds": 900
}
```

## Audit security

A customer should be able to answer:

```text
who initiated this?
which agent acted?
which files were read?
which files were written?
which credentials were used?
which external tools were called?
which network destinations were contacted?
what did it cost?
which approvals happened?
what artifact was produced?
```

That is the trust product.
