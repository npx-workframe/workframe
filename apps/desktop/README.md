# Workframe Desktop

Thin Electron shell for Workframe. Loads the web UI (local dogfood or hosted URL) with a native title bar and embedded browser tabs via `BrowserView`.

## Dev

1. Start the Workframe stack (dogfood UI on `http://127.0.0.1:18644`) or point at another URL.
2. From the repository root or this package:

```bash
pnpm --filter @workframe/desktop dev
# or override target:
WORKFRAME_WEB_URL=http://127.0.0.1:18644 pnpm --filter @workframe/desktop dev
```

`dev` compiles main (ESM) + preload (CJS) and launches Electron.

## Package

```bash
pnpm desktop:package
```

Packaged builds use `WORKFRAME_PRELOAD_URL` (optional) as the default server URL when no `lastUrl` is stored.
