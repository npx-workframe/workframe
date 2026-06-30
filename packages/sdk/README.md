# SDK

Typed API client.

Create this package when multiple consumers need a shared client for `apps/api`, such as web, mobile, desktop, admin, scripts, or external integrations.

The SDK may consume `packages/contracts`; it must not redefine API shapes or import API implementation internals.
