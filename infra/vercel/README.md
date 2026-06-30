# Vercel Deployment

Deploy `apps/web` as the Vercel project root.

Required environment:

```text
VITE_WORKFRAME_PROJECT=Workframe
VITE_WORKFRAME_API_BASE_URL=https://api.example.com
```

`apps/web` sends `/api/*` calls to `VITE_WORKFRAME_API_BASE_URL` when that value is set. In local dev, Vite proxies `/api` to `VITE_WORKFRAME_API_PORT` or `19120`.

The active backend is `services/workframe-api` on the VPS, not `apps/api`.
