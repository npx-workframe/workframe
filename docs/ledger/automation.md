# Workframe rail automation

Automations consume `docs/ledger/ledger.json`; they do not create priorities.
Select one dependency-clear `ready` item, claim it when the run survives a
session, inspect named source, act within stop lines, verify acceptance, record
evidence, transition, and stop. Review requires patch/evidence references;
approval-gated and blocked items are not runnable. No eligible item means a
clean stop with no repository write.
