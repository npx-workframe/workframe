# Tests, Validation, and Success Criteria

## Product validation

The product is working if teams use Workframe weekly to run real projects.

Leading indicators:

```text
weekly active workspaces
runs per workspace
cards created by agents
cards completed by agents
artifacts produced
approvals requested
repeat scheduled jobs
provider accounts connected
team members invited
agent retention
```

## Security validation

Required tests:

```text
API has no Docker socket in secure mode
raw provider keys never appear in Hermes .env during turns
LLM proxy rejects invalid/expired leases
lease provider mismatch is rejected
member cannot access owner dashboard
user-only credentials do not cross users
company key usage is attributed to initiating user/run
agent cannot read files outside run manifest
tool call without capability is rejected
egress to blocked destinations is denied
```

## Billing validation

Required tests:

```text
every run has a payer/funding source
every model call creates line item
every marketplace tool call creates line item
child runs inherit parent cost center
budget exceeded stops run or requires approval
workspace ledger sums to invoice/credit deduction
```

## Deployment validation

Required tests by mode:

| Mode | Required validation |
|---|---|
| Local | installs, starts, connects provider, runs first agent |
| Docker trusted team | invite user, connect BYOK, run agent, see ledger |
| VPS self-host | domain works, email allowlist works, backups work |
| Provisioned cell | one-click deploy, health check, upgrade, restore |
| Enterprise BYOC | SSO, audit export, private network, CMK path |

## Success if

Near-term success:

```text
Workframe can run a real Auto Game Dev Shop pilot
users return weekly
agents produce visible artifacts
company/user provider keys are safe enough for trusted teams
runs are logged and billable
```

Medium-term success:

```text
managed cells sell repeatedly
BYOC deploys work reliably
runtime adapters are real
marketplace packages start emerging
```

Long-term success:

```text
Workframe becomes the default cockpit for operating autonomous teams and businesses
```
