# Workframe Website

Public acquisition, content, legal, docs, and SEO surface — separate from the authenticated product in `apps/web`.

## Stack

- Next.js (App Router)
- Tailwind CSS v4
- PWA: `manifest.webmanifest` + installable shell service worker
- Native-like viewport: fixed 1:1 scale, no pinch zoom jitter, safe-area insets

## Local dev

```bash
cd apps/website
npm install
npm run dev
```

Open http://localhost:3000

## Vercel

1. Import the GitHub repo in Vercel.
2. Set **Root Directory** to `apps/website`.
3. Framework preset: **Next.js** (uses `vercel.json` install/build commands).
4. Optional env: `NEXT_PUBLIC_APP_URL` → your product app URL (defaults to `https://app.workframe.io`).

`vercel.json` uses `npm install` so this app deploys independently of the monorepo pnpm workspace graph.

## Boundaries

- No authenticated product workflows here unless deployment intentionally combines website and app.
- Link out to `apps/web` for signup, chat, and workspace UI.
