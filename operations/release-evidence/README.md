# Release evidence

Machine-readable artifacts produced during **maintainer release sign-off** — not end-user product audits.

## Three evidence types (WF-003)

| Type | Schema | When produced |
|------|--------|----------------|
| **PackageInstallEvidence** | [schema/package-install-evidence.schema.json](schema/package-install-evidence.schema.json) | `install-gate.ps1` / pack-from-tarball path (WF-021) |
| **FirstRunEvidence** | [schema/first-run-evidence.schema.json](schema/first-run-evidence.schema.json) | After wizard + first chat (WF-020) |
| **NegativeInstallEvidence** | [schema/negative-install-evidence.schema.json](schema/negative-install-evidence.schema.json) | Deny paths, no mutation (WF-019) |

Shared field definitions: [schema/evidence-common.schema.json](schema/evidence-common.schema.json).

## Examples

Illustrative fixtures (not live run output):

- [examples/package-install-evidence.example.json](examples/package-install-evidence.example.json)
- [examples/first-run-evidence.example.json](examples/first-run-evidence.example.json)
- [examples/negative-install-evidence.example.json](examples/negative-install-evidence.example.json)

Validate:

```bash
node scripts/workframe/validate-release-evidence.mjs
```

Produce package install evidence (no Docker):

```bash
node scripts/workframe/run-package-install-evidence.mjs --build
# --skip-prep after install-gate / test:ci prep
```

Produce first-run and negative evidence:

```bash
node scripts/workframe/run-first-run-evidence.mjs
node scripts/workframe/run-negative-install-evidence.mjs
```

Output default: `runs/latest-package-install.json` (gitignored).

## Authority

- **Product security audit** → [docs/public/audit.md](../docs/public/audit.md)
- **Harness scenarios** → `.harness/feature_list.json`
- **Release evidence** → this folder (maintainer-only, may contain redacted paths)

Evidence does not ship in the `create-workframe` npm pack unless explicitly copied for debugging.

## Storage layout (future runners)

```text
operations/release-evidence/
  schema/
  examples/
  runs/<package_version>/<scenario_id>.json   # gitignored or CI artifacts
```

`runs/` is not committed by default — examples + schema are the contract.
