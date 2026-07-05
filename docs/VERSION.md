# Workframe v0.1.9

| Component | Version |
|-----------|---------|
| create-workframe | 0.1.9 |
| workframe CLI | 0.1.9 |
| @workframe/workframe | 0.1.9 |
| Workframe API / UI | 0.1.9 |

```bash
npx create-workframe@0.1.9 MyProject
```

Hermes gateway image: `nousresearch/hermes-agent:latest` (updated via stack admin).

## 0.1.9

- Fix in-app Workframe apply on SECURE_MODE: API prefetches npm, supervisor rebuilds (control-net has no registry egress).
- Fix compose apply from supervisor on Windows (skip host-bindings when host path is not visible in-container).
- Record installed pack version in `workframe-api/data/package-version` after apply.
