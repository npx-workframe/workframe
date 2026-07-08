# Workframe operator log

Append-only. Format: ISO timestamp | Role | one-line outcome

## Entries

2026-07-08T10:45-03:00 | pm-workframe | Dogfood MyBusiness up @ 0.1.13; fixed handler_admin health 500; install-gate green; pushed main + tag v0.1.13 for CI npm publish.
2026-07-08T10:40-03:00 | pm-workframe | Release 0.1.13 prep — install-gate green, dogfood reset @ local pack 0.1.13 (MyBusiness slot 1); npm publish blocked on npm login (run publish-npm.ps1 or tag v0.1.13 for CI).
2026-07-08T11:00-03:00 | pm-workframe | WF-036 done — build:web green; provider labels unified; useConciergeFlow unused-import fix; backlog flipped.
2026-07-08T10:15-03:00 | functional-lane | WF-036 HermesSessionContext split — 194-line provider + hermes-session/{bind,history,stream} hooks (max 449 lines); pnpm build:web green; provider-label unification still partial.

2026-07-08T09:45-03:00 | pm-workframe | WF-032 — workspace_bootstrap.py extracted (~530 lines: default workspace seed, DM lane bootstrap, member onboarding, provision runtimes); server.py ~5.6k lines; test_server_reexports extended.

2026-07-08T09:30-03:00 | gate-run G0.2 | verify-matrix @ 3fe0405: 13 pass / 3 fail / 2 skip. WF-021 allow (sync+bundle prep, ui_bundle_identity green). Fixes: server _ensure_profile_terminal_cwd re-export, test-scaffold WF-032 API bundle, npm pack --ignore-scripts after prep. FAIL: verify-public (operator path patterns), build-web + harness web-build (cosmetic lane TS6133 useConciergeFlow). Evidence: operations/release-evidence/runs/latest-verify-matrix.json

2026-07-08T16:00-03:00 | pm-workframe | WF-032 â€” hermes_admin.py extracted (~757 lines: usage/profile/soul/debug/insights/gquota/commands); server.py ~6.0k lines / 95 defs; test_hermes_admin.py green.
2026-07-08T09:15-03:00 | pm-workframe | WF-032 â€” avatar_registry.py extracted (~343 lines: catalog, preset picks, agent avatar assignment); server.py ~6.8k lines; test_server_reexports extended.
2026-07-08T12:05-03:00 | backend-lane | WF-012 done â€” workframe-build.json stamped at bundle; /api/meta package_version + ui_build; ui_bundle_identity asserts stamp == packed version; run-package-install-evidence --skip-prep allow @ HEAD.
2026-07-08T09:00-03:00 | pm-workframe | WF-016 done â€” receipt per run on all six surfaces (mention/kanban/cron-webhook gaps closed); test_run_ledger + test_run_surface_wiring + test_run_authority green; amounts deferred Stage E.
2026-07-08T15:45-03:00 | pm-workframe | WF-032 â€” profile_api_lifecycle.py extracted (~65 lines: ensure_profile_api); server.py ~7.8k lines; test_server_reexports extended.
2026-07-08T15:30-03:00 | pm-workframe | WF-032 â€” docker_gateway.py extracted (~165 lines: Docker socket + gateway exec); server.py ~8.5k lines; test_server_reexports extended.
2026-07-08T15:15-03:00 | pm-workframe | WF-032 â€” chat_sessions.py extracted (~472 lines: session info, chat bootstrap/messages, segment parsing); server.py ~8.8k lines.
2026-07-08T15:00-03:00 | pm-workframe | WF-032 â€” turn_overlay.py extracted (~696 lines: per-turn credential leases, LLM proxy overlays); server.py ~9.3k lines; test_server_reexports extended.
2026-07-08T08:15-03:00 | pm-workframe | Removed owner@local.workframe synthetic identity â€” local bootstrap + complete_install require real email; test_local_bootstrap.py.
2026-07-08T08:10-03:00 | pm-workframe | Hotfix 73afd5d â€” restored _strip_profile_action_env + action-env helpers dropped in WF-032 oauth_redirect extract; reverted broken ConciergeFlow session-gate WIP; dogfood API recreated.
2026-07-08T14:30-03:00 | pm-workframe | WF-032 â€” credential_store.py extracted; server.py ~8.9k lines.
2026-07-08T14:20-03:00 | pm-workframe | WF-032 â€” credential_resolve.py extracted; server.py ~9.1k lines.
2026-07-08T14:10-03:00 | pm-workframe | WF-032 â€” mention_invoke.py extracted; server.py ~9.3k lines.
2026-07-08T14:00-03:00 | pm-workframe | WF-032 â€” provider_catalog + oauth_redirect extracted; server.py ~9.6k lines.
2026-07-08T13:15-03:00 | pm-workframe | WF-032 â€” provider_bindings.py extracted; server.py ~10.1k lines.
2026-07-08T13:00-03:00 | pm-workframe | WF-032 â€” oauth_pending.py + mention_helpers.py extracted; server.py ~10.7k lines.
2026-07-08T12:50-03:00 | pm-workframe | WF-032 â€” runtime_tokens.py extracted; server.py ~10.9k lines; Wave 1 complete (4 items flipped).
2026-07-08T12:45-03:00 | pm-workframe | Wave 0â€“1 backend â€” G0.1 commits (create-workframe /compose, install-gate build guard); WF-035/007/NS-P1/NS-P2 flipped with test evidence; ledger-next â†’ WF-032.
2026-07-08T05:30-03:00 | fable-planning | Gate run planned â€” docs/ledger/handoffs/gate-run-2026-07-08.md (waves 0â€“5: hygiene â†’ P1 flips â†’ WF-032 split â†’ WF-012/016 â†’ WF-017 VPS evidence â†’ WF-036 functional). program-status.md refreshed (29/8/2/11); now.md synced to 0.1.12; verified run-ledger six surfaces + tests green; E stop line unchanged.
2026-07-07T05:45-03:00 | pm-workframe | WF-037 done â€” invites_accept guard fix; test_route_registry audits all 62 patterns; backlog + program-status updated; ledger-next â†’ WF-032.
2026-07-06T19:42-03:00 | pm-workframe | WF-017 verify gaps â€” packages verify-public-deploy synced; backup/egress/broker checks.
2026-07-06T19:39-03:00 | pm-workframe | WF-007 verified â€” test_cell_authority.py green; CLI wire deferred WF-014.
2026-07-06T19:38-03:00 | pm-workframe | WF-016 verified â€” test_run_authority.py green; billing amounts deferred.
2026-07-06T19:35-03:00 | pm-workframe | WF-035 partial â€” _log_handler_error on auth/vault/provider-sync paths.
2026-07-07T04:25-03:00 | pm-workframe | WF-037 batch 6 â€” stripped 20 redundant startswith guards from pattern handlers; oauth/disconnect 404 fallthrough.
2026-07-07T04:25-03:00 | pm-workframe | WF-032 â€” api_meta.py extract (workframe_meta, hermes_bootstrap, dashboard gate/skills).
2026-07-07T04:15-03:00 | pm-workframe | WF-037 batch 5 â€” PATCH workspace/members + supervisor POST in registry; do_POST/do_PATCH if-chains removed.
2026-07-07T04:15-03:00 | pm-workframe | WF-032 â€” doctor_runtime.py extract; WF-NS-P2 webhook test + DATA_DIR patch in test_run_surface_wiring.
2026-07-06T18:15-03:00 | pm-workframe | WF-040 done â€” program_stages in backlog.json; ledger-next picks Bâ†’Câ†’D (WF-037 next); PM README/runbook reference program-status.md.
2026-07-06T17:50-03:00 | verify-matrix | Full matrix @ 9a06d88: 16 pass / 1 fail / 2 skip. FAIL: package-install-evidence --skip-prep (ui_bundle_identity stale UI). Evidence: operations/release-evidence/runs/latest-verify-matrix.json. WF-019/020/005 green; WF-021 runner fails without bundle prep.
2026-07-06T19:15-03:00 | pm-workframe | WF-032 Stage 3 complete â€” lane_bindings.py; server ~12.2k lines; pushed; next WF-037 route dispatch batches.
2026-07-06T18:48-03:00 | pm-workframe | WF-037 batch 2 (f831c93) â€” 22 routes to registry; 47 GET + 36 POST dispatched; continue batch 3.
2026-07-06T18:42-03:00 | pm-workframe | WF-032 Stage 3 complete â€” lane_bindings.py (7c00a21), server ~12.1k; dispatch WF-037 batches next.
2026-07-06T18:38-03:00 | pm-workframe | WF-032 Stage 3 partial â€” chat_stream.py (8b6c56f), server ~12.5k lines; pushed; continue-agent next for lane bindings + WF-037/035.
2026-07-06T18:32-03:00 | pm-workframe | WF-032 Stage 2 complete (4 commits, server 14385 lines); continue-agent dispatched for S3 + gaps.
2026-07-06T18:26-03:00 | pm-workframe | Merged lane-d-authority â†’ main (fast-forward 2ed9dbd); cosmetic-ui-wip stashed; continue-agent dispatched for WF-032 S2/S3 + gaps.
2026-07-06T18:18-03:00 | pm-workframe | WF-032 Stage 1 complete on lane-d-authority (6 commits, server âˆ’2938 lines); all push subagents reported â€” merge branch next.
2026-07-06T18:15-03:00 | pm-workframe | lane-copy-ux complete â€” 22 files, copy-style-notes.md, 3 commits on lane-d-authority.
2026-07-06T18:12-03:00 | pm-workframe | lane-c-broker partial â€” WF-026â†’025 done on lane-d-authority; WF-017 partial (VPS run manual).
2026-07-06T18:08-03:00 | pm-workframe | lane-d-authority partial â€” 5 commits on branch; WF-009/008 done; run ledger + cell scaffold landed; merge lane-d-authority â†’ main pending.
2026-07-06T18:02-03:00 | pm-workframe | lane-b-api â€” WF-037 done (2651025), WF-032 partial db_schema (bca2747); broker/authority unblocked for server.py wiring.
2026-07-06T17:59-03:00 | pm-workframe | Dispatch copy-ux agent â€” strings only; wizard first, settings mirror, errors/feedback; no layout/CSS.
2026-07-06T17:53-03:00 | pm-workframe | Push-to-deferred dispatch â€” 4 lanes: B (037/032), C (broker), D (NS-P2/009/007/008/016), meta WF-040.
2026-07-06T18:10-03:00 | pm-workframe | verify-matrix 16/1/2 â€” WF-021 ui_bundle stale without sync+bundle; all subagent lanes closed; next WF-037 impl.
2026-07-06T18:05-03:00 | doc-audit | program-status.md refreshed â€” Stage A complete; B WF-037 partial; backlog.md pointer updated; verify:docs/version green.
2026-07-06T17:48-03:00 | pm-workframe | api-decompose verify â€” WF-037 stays partial (no commit); WF-032 gap documented; stash wf037-verify optional.
2026-07-06T17:47-03:00 | pm-workframe | Stage A closed â€” WF-006/019/020/004 done (release-truth subagent); Wave 2 unblocked on broker lane after B1.
2026-07-06T17:46-03:00 | pm-workframe | Spawn doc-audit + verify-matrix subagents â€” document program state vs backlog; run full verify matrix.
2026-07-06T17:44-03:00 | pm-workframe | Agent discipline: verify-first, backlog may be stale, no arbitrary changes, no UI â€” relayed to active subagents.
2026-07-06T17:43-03:00 | pm-workframe | Alan constraint: NO UI changes â€” frontend lane cancelled; WF-036/WF-012 out of scope for push-to-deferred.
2026-07-06T17:40-03:00 | pm-workframe | Dispatch 4 subagents â€” Stages Aâ†’D push until deferred threshold; lanes: release-truth, api-decompose, domain-design, frontend.
2026-07-06T17:37-03:00 | pm-workframe | Session open â€” orient backlog (50 items: 13 done, 7 partial, 18 todo, 12 deferred); ledger-next WF-006; uncommitted cosmetic UI lane on main.
2026-07-05T06:02-03:00 | pm-workframe | WF-037 partial â€” route_registry.py + auth gate; commit 317aea4.
2026-07-05T05:50-03:00 | pm-workframe | Wave A checkpoint â€” WF-031/034/038 done, WF-033 partial; 4 commits (da30d00..539f5ae); orchestration.md live.
2026-07-05T04:56-03:00 | pm-workframe | Dogfood sign-off done (Alan) â€” WF-002 done; harness dogfood-install-gate + installer-ui-bundle passes:true.
2026-07-05T04:15-03:00 | pm-workframe | WF-005 done â€” verify-release-gates.mjs; harness reports blocked-local; publish fails closed.
2026-07-05T04:05-03:00 | pm-workframe | WF-021 done â€” run-package-install-evidence.mjs (packâ†’scaffold, allow). WF-002 partial pending WF-020.
2026-07-03T21:00-03:00 | Scaffold | operations rail + START_HERE.md + harness README added for agent entry cascade.
2026-07-04T00:00-03:00 | Planning Rail | created docs/living-audit/README.md with installer decision-tree convergence map.
2026-07-04T00:04-03:00 | Red Team Smoke Test | verified docs/living-audit write path with red-team-smoke-test-2026-07-04.md; no product source code changed.
2026-07-04T00:15-03:00 | Planning Rail | created docs/living-audit/first-run-wizard.md with cell-first first-run wizard convergence map; no product source code changed.
2026-07-04T00:45-03:00 | Red Team | created docs/living-audit/red-team-01-adoption-risk.md challenging non-destructive runtime adoption assumptions; no product source code changed.
2026-07-04T01:15-03:00 | Planning Rail | created docs/living-audit/runtime-detection-map.md with mutation-free detection schema and probe boundaries; no product source code changed.
2026-07-04T01:45-03:00 | Red Team | created docs/living-audit/red-team-02-detection-privacy.md challenging detection privacy, false confidence, and public launch-gate drift; no product source code changed.
2026-07-04T02:15-03:00 | Planning Rail | created docs/living-audit/agent-runtime-config.md with agent/runtime/provider/funding config model; no product source code changed.
2026-07-04T02:45-03:00 | Red Team | created docs/living-audit/red-team-03-agent-runtime-matrix.md challenging premature agent/runtime/provider matrix complexity; no product source code changed.
2026-07-04T03:15-03:00 | Planning Rail | created docs/living-audit/refactor-map.md mapping Hermes-centered seams to adapter-first cell boundaries; no product source code changed.
2026-07-04T03:45-03:00 | Red Team | created docs/living-audit/red-team-04-refactor-seam-risk.md challenging adapter seam, profile identity, and admin/runtime boundary assumptions; no product source code changed.
2026-07-04T04:15-03:00 | Planning Rail | created docs/living-audit/release-readiness.md with next-release blockers and adapter-first deferrals; no product source code changed.
2026-07-04T04:45-03:00 | Red Team | created docs/living-audit/red-team-05-release-gate-risk.md challenging release evidence, public launch, doctor/preflight, and funding gate assumptions; no product source code changed.
2026-07-04T05:15-03:00 | Planning Rail | created docs/living-audit/installer-validation-plan.md with branch-by-branch installer validation matrix; no product source code changed.
2026-07-04T05:45-03:00 | Red Team | created docs/living-audit/red-team-06-validation-matrix-risk.md challenging validation matrix scope, evidence provenance, destructive rerun risk, and package truth; no product source code changed.
2026-07-04T06:15-03:00 | Planning Rail | created docs/living-audit/deployment-order.md with local/Docker/VPS mode-selection sequence; no product source code changed.
2026-07-04T06:45-03:00 | Red Team | created docs/living-audit/red-team-07-open-update-connect-risk.md challenging open/update/connect hidden-installer risk; no product source code changed.
2026-07-04T07:15-03:00 | Planning Rail | created docs/living-audit/existing-runtime-adoption-policy.md with non-destructive host/runtime adoption boundaries; no product source code changed.
2026-07-04T07:45-03:00 | Red Team | created docs/living-audit/red-team-08-manifest-authority-risk.md challenging manifest/provenance authority, default destructive create, and false-safe adoption assumptions; no product source code changed.
2026-07-04T08:15-03:00 | Planning Rail | created docs/living-audit/workframe-surface-baseline.md defining minimum surface contract; no product source code changed.
2026-07-04T08:45-03:00 | Red Team | created docs/living-audit/red-team-09-surface-contract-risk.md challenging surface promise, release claims, and false-OS risk; no product source code changed.
2026-07-04T09:15-03:00 | Planning Rail | created docs/living-audit/multi-user-provider-policy.md mapping BYOK/company-pays/hybrid funding journey and receipt gates; no product source code changed.
2026-07-04T09:45-03:00 | Red Team | created docs/living-audit/red-team-10-funding-authority-risk.md challenging BYOK/company/hybrid funding as credential authority; no product source code changed.
2026-07-04T10:15-03:00 | Planning Rail | created docs/living-audit/final-convergence-synthesis.md with v0.1.x package-truth to v0.2 adapter-first roadmap; no product source code changed.
2026-07-04T10:45-03:00 | Red Team | created docs/living-audit/red-team-11-gate-theater-risk.md challenging named gates without owners, evidence schemas, and negative tests; no product source code changed.
2026-07-04T11:15-03:00 | Planning Rail | created docs/living-audit/package-truth-gate.md with v0.1.x release decision memo and evidence schema; no product source code changed.
2026-07-04T11:45-03:00 | Red Team | created docs/living-audit/red-team-12-evidence-authority-collapse.md challenging overloaded PackageTruthGate evidence and release-claim scope; no product source code changed.
2026-07-04T12:05-03:00 | Manual Audit | created docs/living-audit/25-audit.md consolidating the 24-run rail plus fresh source sampling; no product source code changed.
2026-07-04T23:50-03:00 | DevOps | consolidated dogfood doctrine: reset = npx create-workframe MyBusiness only; scripts/workframe/README.md; deprecated legacy compose/runtime paths.
2026-07-06T18:00-03:00 | Copy | wizard/settings/error copy pass; docs/ledger/copy-style-notes.md term map (BYOK, company-pays, Workframe admin).
