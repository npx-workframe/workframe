# Workframe licensing

Workframe open-source components ship under **Apache License 2.0**.

## Open source surface

```text
apps/web/                      Product UI
services/workframe-api/        BFF
services/workframe-supervisor/ Secure-mode host actions
packages/create-workframe/     npx installer
infra/compose/workframe/       Reference Docker stack
```

See [`LICENSE`](../LICENSE) and [`NOTICE`](../NOTICE).

## Third-party

| Component | License |
|-----------|---------|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | MIT |
| [NVIDIA NemoClaw](https://github.com/NVIDIA/NemoClaw) | Apache 2.0 |

Hermes is MIT; Workframe is Apache 2.0 — mixed stacks are normal.
