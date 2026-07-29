# Origin Minimal Bootstrap — Local Fixture Test

**Date:** 2026-07-29  
**Environment:** isolated Linux container, Node.js 22.16.0, npm 10.9.2  
**Evidence class:** fixture-backed local execution, not packed-package or host-runtime proof

## Constraint

The execution container had no outbound DNS and did not contain a Workframe checkout, npm cache entry, `specify`, Codex, Claude, or Hermes. The current `workframe.js` discovery contract was represented by a faithful deterministic fixture. The exact new branch files were executed unchanged:

- `packages/workframe/bin/workframe-cli.js`
- `packages/workframe/bin/origin-start.js`
- `packages/workframe/scripts/test-origin-start.mjs`

This evidence does not close cross-platform package verification. That remains `ORI-005`.

## Commands exercised

```bash
npm test
node bin/workframe-cli.js start --json \
  --purpose="Build a durable operating context for my work." \
  --forms=organization,project
node bin/workframe-cli.js help
```

## Results

- Node syntax checks passed for the existing-status fixture, dispatcher, and Origin module.
- Standard-library Origin checks passed.
- `version` delegated through `workframe-cli.js`.
- `status --json` delegated through `workframe-cli.js`.
- `help` preserved existing output and appended the experimental `start` command.
- Purpose preceded provisional form.
- `none` handling, form normalization, and candidate priority passed.
- JSON contained:
  - `mode: plan_only`
  - the supplied `purpose_statement`
  - normalized `candidate_forms`
  - `authorization_required: true`
  - `inspected_paths: []`
  - `mutations: []`
- No provider call, path inspection, or filesystem mutation was implemented by Origin.

## Sample output

```json
{
  "schema_version": "0.1",
  "mode": "plan_only",
  "purpose_statement": "Build a durable operating context for my work.",
  "candidate_forms": ["organization", "project"],
  "inference_candidate": {
    "kind": "runtime",
    "id": "codex",
    "label": "Codex CLI"
  },
  "authorization_required": true,
  "inspected_paths": [],
  "mutations": [],
  "next_question": "Which existing sources should be considered before this purpose and structure become durable doctrine?"
}
```

## Remaining proof

Run the packed branch package on a real checkout and record:

- Windows execution;
- at least one macOS or Linux execution;
- real current `status --json` delegation;
- a real TTY session;
- package contents and executable permissions.
