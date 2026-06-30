# Workframe API Service

**Version:** `0.1.0` (`workframe-api-0.1.0`). See `docs/VERSION.md`.

Active backend service for the transplanted Workframe vertical slice.

This is intentionally preserved as the current Python BFF instead of being rewritten into `apps/api`.

## Local

```bash
cd services/workframe-api
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
HOST=0.0.0.0 PORT=8080 HERMES_DATA=/opt/data WORKSPACE=/workspace python3 server.py
```

## Runtime state

Runtime files are intentionally not committed:

- `data/*.db`
- `data/.auth_keys`
- Hermes `Agents/`
- workspace `Files/`

For VPS deployment, mount clean persistent volumes into `/opt/data` and `/workspace`.
