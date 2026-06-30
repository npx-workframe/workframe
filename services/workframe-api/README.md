# Workframe API Service

Python BFF for the Workframe UI. See [docs/VERSION.md](../../docs/VERSION.md) for release version.

Canonical implementation — not rewritten into a separate `apps/api` service.

## Local (outside Docker)

```bash
cd services/workframe-api
python3 -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
HOST=0.0.0.0 PORT=8080 HERMES_DATA=/opt/data WORKSPACE=/workspace python3 server.py
```

## Runtime state (not committed)

- `data/*.db`, vault files under `WORKFRAME_API_DATA_DIR`
- Hermes `Agents/` tree on mounted volume

## Docs

- [Runtime operations](../../docs/public/runtime-operations.md)
- [Security](../../docs/public/security.md)
- [BFF route map](../../docs/public/bff-route-map.md)
