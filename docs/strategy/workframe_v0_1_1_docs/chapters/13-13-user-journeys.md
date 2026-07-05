# User Journeys

## Journey 1 - Local solo builder

1. User installs Workframe locally.
2. Workframe detects or configures Hermes/local agent harness.
3. User connects BYOK model provider.
4. User creates an Auto Game Dev workspace.
5. Workframe creates default agents: Director, Engineer, Designer, QA.
6. User chats with Director Agent.
7. Director creates board cards.
8. Engineer Agent starts scoped runs against local files.
9. User reviews artifacts and approves changes.
10. Repeated workflows become playbooks.

## Journey 2 - Trusted Docker team

1. Founder deploys Workframe via Docker Compose.
2. Invites trusted team members.
3. Each member connects their own provider keys.
4. Team creates project rooms and boards.
5. Agents are assigned tasks through boards and mentions.
6. Runs are logged to the workspace ledger.
7. The team upgrades to managed VPS when project becomes serious.

## Journey 3 - VPS self-host with company domain

1. Business deploys Workframe to a VPS.
2. DNS points `workframe.mybusiness.com` to the instance.
3. Owner enables email-domain allowlist for `mybusiness.com`.
4. Contractors require explicit invites.
5. Admin connects company-level model provider key.
6. Users trigger runs; provider cost is attributed to users/cards/runs.
7. Owner reviews ledger, artifacts, approvals, and spend.

## Journey 4 - Workframe-provisioned cell

1. Customer signs up for managed Workframe Cell.
2. Chooses Hostinger, Hetzner, AWS, GCP, or Workframe-hosted infrastructure.
3. Connects domain and identity policy.
4. Workframe provisions the cell.
5. Customer installs Auto Game Dev Shop template.
6. Workframe manages updates, backups, health, and usage credits.
7. Customer upgrades runtime capacity as agent usage grows.

## Journey 5 - Enterprise BYOC

1. Enterprise signs annual contract.
2. Workframe deploys into customer cloud/VPC.
3. SSO/SAML and SCIM are configured.
4. Customer-managed keys and private networking are enabled.
5. Internal teams create Workframe Cells per business unit/project.
6. Agents operate only through approved tools and private model endpoints.
7. Audit logs export to SIEM.
8. Enterprise adds custom templates and internal marketplace packages.

## Journey 6 - Marketplace purchase

1. User browses marketplace.
2. Installs "Game QA Agent" or "Weekly Build Playbook."
3. Workframe shows requested capabilities, cost model, and publisher.
4. Admin approves installation.
5. The agent/playbook becomes available in selected workspaces.
6. Runs created by the package are line-itemed and auditable.
7. Marketplace vendor earns usage or subscription revenue.
