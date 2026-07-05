# Core Doctrine and First Principles

## Stable vs replaceable layers

Workframe should separate stable business primitives from replaceable technical substrates.

| Stable Workframe-owned layer | Replaceable layer |
|---|---|
| humans, users, teams | model providers |
| workspaces and cells | LLM runtimes |
| persistent agents | agent harnesses |
| boards, files, rooms | CLI tools |
| runs and audit | coding agents |
| budgets and billing | sandbox providers |
| credentials and policies | external connectors |
| approvals and governance | local/hosted compute providers |

The mistake would be to tie Workframe's identity to Hermes, AgentOS, Claude Code, Codex, OpenCode, or any single model provider. Those tools are powerful but replaceable.

The durable opportunity is the business system that can host them.

## Agents as persistent business actors

Agents should not be disposable prompts only. In Workframe, an agent is a persistent business entity:

```text
agent_id
role
job description
skills
memory
allowed tools
allowed files
budget
manager
reporting line
runtime preference
approval rules
audit history
```

This enables an organization-like structure: game director, architect, engineer, designer, QA agent, release manager, support agent, researcher, accountant, or sales assistant.

## Computer runs as the unit of authority

A run is the moment where intent becomes action.

Every meaningful operation should become a run:

```text
chat mention
board assignment
cron job
webhook
manual action
sub-agent delegation
tool call
external message
file write
deployment
```

A run records:

```text
who initiated it
which agent acted
which workspace/cell it belongs to
which files were available
which tools were available
which credentials were leased
which model/runtime was used
which network destinations were allowed
what it cost
what artifacts were produced
what approvals were required
what happened
```

## Capabilities, not ambient authority

Agents should not receive raw secrets, broad filesystem access, full internet access, or human OAuth tokens. Agents should receive scoped capabilities:

```text
read these files
write to this artifact directory
open a PR in this repo
post a draft message
request a production deploy
use model provider through this lease
run this command in this runtime
```

The capability is granted to a run, not permanently to the profile.

## Files are economic output

The economy moves through files and outcomes:

```text
.ppt
.pdf
.dwg
.docx
.xlsx
.zip
repo commits
pull requests
deployments
videos
images
audio
contracts
reports
invoices
support responses
```

Workframe's product should make the production chain visible: who requested work, which agent produced it, which tools were used, what it cost, which files changed, and who approved the result.
