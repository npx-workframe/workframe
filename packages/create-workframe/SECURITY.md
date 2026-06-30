# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

Send details to the maintainers via a private channel (GitHub Security Advisories on
[npx-workframe/workframe](https://github.com/npx-workframe/workframe) when enabled, or
direct contact with the repository owner).

Include:

- Affected component (BFF, supervisor, installer, UI, compose)
- Steps to reproduce
- Impact assessment (data exposure, auth bypass, RCE, etc.)
- Suggested fix if you have one

We aim to acknowledge reports within a few business days.

## Scope notes

- **Host Hermes** (`%LOCALAPPDATA%\hermes` on Windows) is personal runtime state and is
  out of scope for Workframe product security reports unless the issue is in shared
  Workframe source code that affects all installs.
- Production deployments should run with `WORKFRAME_MODE=team`, invite-only access, and
  without `DEV_LOCAL_UNSAFE`.
- BYOK (bring-your-own-key) is the default credential mode; workspace company-pays is an
  explicit admin opt-in.

## Safe defaults

- Deny-by-default provider credentials (`user_only` providers do not fall back to workspace keys).
- Install-window gates for owner claim and stack configuration reads.
- Supervisor-mediated host actions when `SECURE_MODE=true`.
