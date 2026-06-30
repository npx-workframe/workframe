# Telemetry

Logging, tracing, metrics, analytics adapters, and redaction helpers.

Telemetry must be explicit. Export factories such as `createLogger` or `initTracing`; do not run provider initialization as an import side effect.

Production behavior should be configured by the app or service that runs it.
