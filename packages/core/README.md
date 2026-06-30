# Core

Pure product and domain logic.

This package owns reusable rules, invariants, policies, entities, and value objects once they become foundational.

It must not import apps, database clients, HTTP frameworks, environment loaders, telemetry side effects, or UI frameworks.

Early feature logic can start inside `apps/api/src/modules/<feature>/` and be promoted here when the boundary earns its keep.
