export default {
  id: "workframe",
  name: "Workframe",
  slug: "workframe",

  repository: {
    provider: "github",
    name: "npx-workframe/workframe",
  },

  surfaces: {
    web: { enabled: true, role: "primary-authenticated-workframe-ui", deploysTo: ["vercel"] },
    api: { enabled: false, role: "future-typescript-api-boundary" },
    worker: { enabled: false, role: "future-asynchronous-backend-executor" },
    website: { enabled: false, role: "public-acquisition-content-docs-legal-surface" },
    admin: { enabled: false, role: "future-operator-admin-surface" },
    mobile: { enabled: false, role: "future-ios-android-surface" },
    desktop: { enabled: true, role: "electron-shell-for-web-plus-local-filesystem" },
  },

  activeRuntime: {
    web: "apps/web",
    api: "services/workframe-api",
    installer: "packages/create-workframe",
    desktop: "apps/desktop",
  },

  doctrine: {
    transplantedVerticalSlice: true,
    noRewriteFirst: true,
    promotePackagesOnlyAfterStable: true,
    backendAuthority: "services/workframe-api until apps/api is intentionally promoted",
  },
} as const;
