# Financial Model and Growth Estimates

These are planning estimates for product strategy and packaging.

## Revenue model by customer type

| Customer type | Likely product | Monthly revenue | Variable cost profile |
|---|---|---:|---|
| solo hacker | local/self-host | $0-$30 | minimal, mostly marketplace/support |
| small team | shared hosted | $50-$150 | model/runtime credits |
| indie studio | managed cell | $250-$750 | VPS/server + credits + support |
| agency/factory | business cell | $750-$2,500 | more runtime + storage + support |
| technical SMB | BYOC | $500-$5,000 | low infra COGS, higher support |
| enterprise | enterprise BYOC | $3,000-$25,000+ | support/compliance/customer success |

## Example monthly unit economics

| Plan | Price | Included variable budget | Infra/support reserve | Gross contribution target |
|---|---:|---:|---:|---:|
| Starter SaaS | $100 | $35-$50 | $10-$20 | $30-$55 |
| Studio Cell | $500 | $100-$200 | $75-$150 | $150-$325 |
| Business Cell | $1,000 | $200-$400 | $150-$250 | $350-$650 |
| BYOC Support | $1,000 | $0-$100 | $100-$250 | $650-$900 |
| Enterprise | $5,000 | contract-specific | $500-$1,500 | $2,500-$4,500 |

## Growth scenario

| Stage | Customers | Mix | MRR estimate |
|---|---:|---|---:|
| Design partners | 10 | mostly free/self-host | $0-$2k |
| Early pilots | 25 | 10 paid cells, 15 self-host | $5k-$15k |
| Seed traction | 100 | 40 starter, 40 studio, 15 BYOC, 5 enterprise pilots | $40k-$120k |
| Expansion | 500 | hosted + managed + BYOC mix | $250k-$750k |
| Marketplace phase | 2,000+ | platform + ecosystem revenue | $1M+ potential MRR |

## Workspaces and cells

| Metric | Early | Growth | Scale |
|---|---:|---:|---:|
| registered users | 500 | 10,000 | 100,000 |
| active workspaces | 50 | 1,000 | 10,000 |
| managed cells | 10 | 200 | 2,000 |
| BYOC cells | 5 | 100 | 1,000 |
| monthly runs | 10,000 | 1M | 100M |
| marketplace packages | 25 | 500 | 10,000 |

## COGS posture

BYOK and BYOC are strategically important because they reduce Workframe's need to front all model and compute costs.

| Mode | COGS burden on Workframe |
|---|---|
| Local BYOK | very low |
| Docker self-host BYOK | very low |
| VPS self-host | low, unless managed support included |
| Workframe-provisioned managed cell | medium |
| Shared hosted SaaS | higher, requires tight metering |
| Enterprise BYOC | low infrastructure COGS, higher support cost |

## Financial principle

Workframe should avoid becoming an unlimited AI usage wrapper. The product should sell governed business capacity:

```text
users
agents
workspaces
cells
runs
credits
connectors
runtime capacity
support
marketplace packages
```

The run ledger is the foundation of both trust and billing.
