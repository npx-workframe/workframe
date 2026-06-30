#!/usr/bin/env python3
"""DEV/CI helper — NOT the canonical installer.

Canonical scaffold: bin/create-workframe.js (npm / npx create-workframe).
This script exists for Python-only smoke tests and security audit workflows.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PKG_ROOT = SCRIPT_DIR.parent
PACKS_JSON = PKG_ROOT / 'shared' / 'WORKFRAME_AGENT_PACKS.json'
WORKSPACE_DOCS = PKG_ROOT / 'docs' / 'workspace-instructions'

PROJECT_AGENT_SLOT = 'project-agent'
NATIVE_SOUL_TEMPLATE = 'workframe-agent'

PROFILE_DESCRIPTIONS = {
    'visionary': 'Clarifies product purpose, positioning, strategy, user value, and long-term alignment.',
    'architect': 'Defines system design, technical boundaries, implementation plans, and code-review standards.',
    'docs': 'Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries.',
    'dev': 'Builds and modifies project files, scripts, tests, and implementation artifacts.',
    'research': 'Performs technical research, market research, references, competitive analysis, and R&D notes.',
    'designer': 'Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback.',
}

SHARED_DOCS = ['WORKFRAME_AGENT_LIBRARY.md', 'WORKFRAME_HANDOFF_SCHEMA.md']

GITIGNORE = """# Runtime state: do not commit instance data
Agents/
**/Agents/
*.db
*.db-shm
*.db-wal
*.log
logs/
cache/
memories/
sessions/
kanban/
state/

# Bootstrap seed (optional cleanup after profile bootstrap)
scripts/seed/

# Secrets
.env
.env.local
.env.*.local
*.pem
*.key
*.p12
*.pfx
secrets/

# Build/tool noise
node_modules/
.venv/
__pycache__/
.pytest_cache/
.DS_Store
Thumbs.db
.vscode/
.idea/
"""

DOCKERIGNORE = """.git
.gitignore
node_modules
.venv
__pycache__
.pytest_cache
*.pyc
*.pyo
*.db
*.db-shm
*.db-wal
*.log
.env
.env.*
Agents
cache
logs
memories
sessions
kanban
state
scripts/seed
"""


def slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or 'workframe'


def native_profile_slug(project_name: str) -> str:
    return f'{slugify(project_name)}-agent'


def native_agent_name(project_name: str) -> str:
    return f'{project_name} Agent'


def render_context(project_name: str) -> dict[str, str]:
    return {
        'projectName': project_name,
        'nativeProfileSlug': native_profile_slug(project_name),
        'nativeAgentName': native_agent_name(project_name),
    }


def render_placeholders(text: str, ctx: dict[str, str] | str) -> str:
    context = render_context(ctx) if isinstance(ctx, str) else ctx
    out = text
    for key, value in context.items():
        out = out.replace(f'{{{key}}}', value)
    return out


def resolve_pack_profiles(base_profiles: list[str], project_name: str) -> list[str]:
    native = native_profile_slug(project_name)
    seen: set[str] = set()
    resolved: list[str] = []
    for profile in base_profiles:
        slug = native if profile == PROJECT_AGENT_SLOT else profile
        if slug not in seen:
            seen.add(slug)
            resolved.append(slug)
    return resolved


def profile_description(profile: str, project_name: str) -> str:
    if profile == native_profile_slug(project_name):
        return (
            f'{native_agent_name(project_name)}: host, concierge, project manager, '
            'orchestrator, and Workframe admin.'
        )
    return PROFILE_DESCRIPTIONS.get(profile, f'{profile} specialist profile.')


def profile_soul_source(profile: str, project_name: str) -> Path:
    template_dir = NATIVE_SOUL_TEMPLATE if profile == native_profile_slug(project_name) else profile
    return PKG_ROOT / 'profiles' / template_dir / 'SOUL.md'


def docker_container_names(project_name: str) -> dict:
    slug = slugify(project_name)
    stack = slug
    return {
        'slug': slug,
        'stack': stack,
        'image': 'nousresearch/hermes-agent:latest',
        'network': f'{stack}-net',
        'gateway': f'{stack}-gateway',
        'dashboard': f'{stack}-dashboard',
        'workframe_api': f'{stack}-workframe-api',
        'workframe': f'{stack}-workframe',
        'chat': f'{stack}-chat',
        'setup': f'{stack}-setup',
        'bootstrap_use': f'{stack}-bootstrap-use',
        'bootstrap_list': f'{stack}-bootstrap-list',
        'profile_dashboard': lambda profile: f'{stack}-dashboard-{profile}',
    }


def hermes_service_volumes_block() -> str:
    return """    volumes:
      - ./Agents:/opt/data
      - ./Files:/workspace
      - ./scripts:/opt/install/scripts:ro"""


def profile_dashboard_service_yaml(profile: str, docker: dict, label_project: str, network: str) -> str:
    profile_esc = profile.replace('"', '\\"')
    return f"""
  dashboard-{profile}:
    image: {docker['image']}
    container_name: {docker['profile_dashboard'](profile)}
    restart: unless-stopped
    command: ["hermes", "-p", "{profile_esc}", "dashboard", "--host", "0.0.0.0", "--insecure", "--tui"]
    labels:
      com.workframe.project: "{label_project}"
      com.workframe.role: profile-dashboard
      com.workframe.profile: "{profile_esc}"
    expose:
      - "9119"
{hermes_service_volumes_block()}
    environment:
      - GATEWAY_HEALTH_URL=http://gateway:8642
      - HERMES_DASHBOARD_TUI=1
    depends_on:
      - gateway
    networks:
      - {network}"""


def docker_compose_yaml(project_name: str, docker: dict, native_profile: str, _pack_profiles: list[str]) -> str:
    label_project = project_name.replace('\\', '\\\\').replace('"', '\\"')
    profile_esc = native_profile.replace('"', '\\"')
    dashboard_profiles = [native_profile]
    profile_services = ''.join(
        profile_dashboard_service_yaml(p, docker, label_project, docker['network']) for p in dashboard_profiles
    )
    profile_depends = ''.join(f'\n      - dashboard-{p}' for p in pack_profiles)
    volumes = hermes_service_volumes_block()
    return f"""name: {docker['stack']}

services:
  gateway:
    image: {docker['image']}
    container_name: {docker['gateway']}
    restart: unless-stopped
    command: ["hermes", "-p", "{profile_esc}", "gateway", "run"]
    labels:
      com.workframe.project: "{label_project}"
      com.workframe.role: gateway
    ports:
      - "127.0.0.1:18642:8642"
{volumes}
    networks:
      - {docker['network']}

  dashboard:
    image: {docker['image']}
    container_name: {docker['dashboard']}
    restart: unless-stopped
    command: dashboard --host 0.0.0.0 --insecure --tui
    labels:
      com.workframe.project: "{label_project}"
      com.workframe.role: dashboard
    ports:
      - "127.0.0.1:19119:9119"
{volumes}
    environment:
      - GATEWAY_HEALTH_URL=http://gateway:8642
      - HERMES_DASHBOARD_TUI=1
    depends_on:
      - gateway
    networks:
      - {docker['network']}
{profile_services}

networks:
  {docker['network']}:
    driver: bridge
"""


def setup_sh() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p Agents Files

echo "Pulling Hermes image..."
docker pull nousresearch/hermes-agent:latest

echo ""
echo "Run Hermes setup (interactive):"
echo "  docker run --rm -it --entrypoint hermes \\\\"
echo "    -v \\"\\$PWD/Agents:/opt/data\\" \\\\"
echo "    -v \\"\\$PWD/Files:/workspace\\" \\\\"
echo "    nousresearch/hermes-agent:latest setup"
echo ""
echo "Then bootstrap profiles:"
echo "  ./scripts/bootstrap-profiles.sh"
echo ""
echo "Start gateway + dashboard:"
echo "  docker compose up -d"
"""


def setup_ps1() -> str:
    return """$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

New-Item -ItemType Directory -Force -Path Agents, Files | Out-Null

Write-Host 'Pulling Hermes image...'
docker pull nousresearch/hermes-agent:latest

Write-Host ''
Write-Host 'Run Hermes setup (interactive):'
Write-Host '  docker run --rm -it --entrypoint hermes `'
Write-Host '    -v "$PWD\\Agents:/opt/data" `'
Write-Host '    -v "$PWD\\Files:/workspace" `'
Write-Host '    nousresearch/hermes-agent:latest setup'
Write-Host ''
Write-Host 'Then bootstrap profiles:'
Write-Host '  .\\scripts\\bootstrap-profiles.ps1'
Write-Host ''
Write-Host 'Start gateway + dashboard:'
Write-Host '  docker compose up -d'
"""


def bootstrap_profiles_sh(profiles: list[str], project_name: str, native_profile: str, docker: dict) -> str:
    blocks = []
    for p in profiles:
        desc = profile_description(p, project_name).replace('"', '\\"')
        create_name = f"{docker['stack']}-bootstrap-{p}"
        show_name = f"{create_name}-show"
        blocks.append(f"""echo "Creating profile: {p}"
docker run --rm --name "{create_name}" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/workspace" \\
  {docker['image']} profile create {p} --clone --description "{desc}" || true

if [ -f "$ROOT/scripts/seed/profiles/{p}/SOUL.md" ]; then
  mkdir -p "$ROOT/Agents/profiles/{p}"
  cp "$ROOT/scripts/seed/profiles/{p}/SOUL.md" "$ROOT/Agents/profiles/{p}/SOUL.md"
fi
""")
    body = '\n'.join(blocks)
    return f"""#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d "$ROOT/Agents" ]; then
  echo "Agents/ missing. Run Hermes setup first."
  exit 1
fi

{body}
echo "Setting default profile to {native_profile}..."
docker run --rm --name "{docker['bootstrap_use']}" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/workspace" \\
  {docker['image']} profile use {native_profile}

echo "Profile bootstrap complete."
docker run --rm --name "{docker['bootstrap_list']}" --entrypoint hermes \\
  -v "$ROOT/Agents:/opt/data" \\
  -v "$ROOT/Files:/workspace" \\
  {docker['image']} profile list
"""


def bootstrap_profiles_ps1(profiles: list[str], project_name: str, native_profile: str, docker: dict) -> str:
    blocks = []
    for p in profiles:
        desc = profile_description(p, project_name).replace('"', '`"')
        create_name = f"{docker['stack']}-bootstrap-{p}"
        blocks.append(f"""Write-Host "Creating profile: {p}"
docker run --rm --name "{create_name}" --entrypoint hermes `
  -v "$Root\\Agents:/opt/data" `
  -v "$Root\\Files:/workspace" `
  {docker['image']} profile create {p} --clone --description "{desc}" 2>$null

$seed = Join-Path $Root "scripts\\seed\\profiles\\{p}\\SOUL.md"
$destDir = Join-Path $Root "Agents\\profiles\\{p}"
if (Test-Path $seed) {{
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}}
""")
    body = '\n'.join(blocks)
    return f"""$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path "$Root\\Agents")) {{
  throw "Agents/ missing. Run Hermes setup first."
}}

{body}
Write-Host "Setting default profile to {native_profile}..."
docker run --rm --name "{docker['bootstrap_use']}" --entrypoint hermes `
  -v "$Root\\Agents:/opt/data" `
  -v "$Root\\Files:/workspace" `
  {docker['image']} profile use {native_profile}

Write-Host "Profile bootstrap complete."
docker run --rm --name "{docker['bootstrap_list']}" --entrypoint hermes `
  -v "$Root\\Agents:/opt/data" `
  -v "$Root\\Files:/workspace" `
  {docker['image']} profile list
"""


CI_WORKFLOW = """name: workframe-security

on:
  push:
  pull_request:

jobs:
  security-and-scaffold:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Run security audit
        run: python3 scripts/security_audit.py
        working-directory: packages/create-workframe

      - name: Generate scaffold with Python
        run: python3 scripts/create_workframe_scaffold.py CiDemo --pack core --output /tmp --force
        working-directory: packages/create-workframe

      - name: Generate scaffold with Node installer
        run: node bin/create-workframe.js --name CiNodeDemo --pack core --out /tmp --ci --force
        working-directory: packages/create-workframe

      - name: Verify generated layout
        run: |
          test -f /tmp/CiDemo/Files/AGENTS.md
          test -f /tmp/CiDemo/docker-compose.yml
          test -f /tmp/CiNodeDemo/Files/docs/SETUP.md
          test -f /tmp/CiNodeDemo/scripts/bootstrap-profiles.sh
"""


def load_packs(path: Path) -> dict:
    data = json.loads(path.read_text())
    packs = data.get('packs', {})
    if not packs:
        raise SystemExit(f'No packs found in {path}')
    return packs


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for p in src.rglob('*'):
        if p.is_file():
            rel = p.relative_to(src)
            out = dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)


def make_setup_doc(project_name: str, pack: str, profiles: list[str], telegram: bool, discord: bool) -> str:
    tg = 'Enabled in plan (optional integration chosen).' if telegram else 'Skipped (can enable later).'
    dc = 'Enabled in plan (optional integration chosen).' if discord else 'Skipped (can enable later).'
    return (
        f"# {project_name} setup\n\n"
        "## 1) Hermes base\n"
        "- Run `./scripts/setup.sh` or `./scripts/setup.ps1`\n"
        "- Then Hermes setup (interactive):\n"
        "```bash\n"
        "docker run --rm -it --entrypoint hermes \\\n"
        '  -v "${PWD}/Agents:/opt/data" \\\n'
        '  -v "${PWD}/Files:/workspace" \\\n'
        "  nousresearch/hermes-agent:latest setup\n"
        "```\n\n"
        "## 2) Bootstrap agent profiles\n"
        "- `./scripts/bootstrap-profiles.sh` or `./scripts/bootstrap-profiles.ps1`\n\n"
        "## 3) API/model keys\n"
        "- `hermes auth add <provider>` at runtime\n\n"
        "## 4) Start gateway + dashboard\n"
        "- `docker compose up -d`\n\n"
        "## 5) Chat integrations (optional)\n"
        f"- Telegram: {tg}\n"
        f"- Discord: {dc}\n\n"
        "## 6) Agent pack\n"
        f"- Pack: **{pack}**\n"
        f"- Profiles: {', '.join(profiles)}\n"
    )


def docs_index() -> str:
    return (
        "# Docs Index\n\n"
        "- SETUP.md — first-run onboarding\n"
        "- WORKFRAME_ONBOARDING.md — concierge loop\n"
        "- WORKFRAME_ROUTING.md — lane routing\n"
        "- WORKFRAME_KANBAN.md — execution + handoffs\n"
        "- WORKFRAME_DOCUMENTS_AND_ARTIFACTS.md — file conventions\n"
        "- WORKFRAME_TELEGRAM.md — optional Telegram\n"
        "- WORKFRAME_DISCORD.md — optional Discord\n"
        "- WORKFRAME_AGENT_LIBRARY.md — crew model\n"
        "- WORKFRAME_HANDOFF_SCHEMA.md — task handoff fields\n"
    )


def generate(
    project_name: str,
    pack: str,
    output_root: Path,
    force: bool,
    telegram: bool,
    discord: bool,
) -> Path:
    packs = load_packs(PACKS_JSON)
    if pack not in packs:
        raise SystemExit(f"Unknown pack '{pack}'. Available: {', '.join(sorted(packs.keys()))}")

    profiles = resolve_pack_profiles(packs[pack]['profiles'], project_name)
    native_slug = native_profile_slug(project_name)
    native_name = native_agent_name(project_name)
    ctx = render_context(project_name)
    docker = docker_container_names(project_name)
    target = output_root / project_name
    files_root = target / 'Files'
    slug = slugify(project_name)

    if target.exists():
        if not force:
            raise SystemExit(f'Target exists: {target}. Use --force to overwrite.')
        shutil.rmtree(target)

    target.mkdir(parents=True, exist_ok=True)
    (target / 'Agents').mkdir(parents=True, exist_ok=True)
    files_root.mkdir(parents=True, exist_ok=True)
    (files_root / 'artifacts').mkdir(parents=True, exist_ok=True)
    (files_root / 'docs').mkdir(parents=True, exist_ok=True)
    (files_root / 'prompts').mkdir(parents=True, exist_ok=True)
    (target / 'Agents' / '.gitkeep').write_text('')
    (files_root / '.gitkeep').write_text('')

    rules_agents = PKG_ROOT / 'rules' / 'AGENTS.md'
    rules_hermes = PKG_ROOT / 'rules' / '.hermes.md'
    (files_root / 'AGENTS.md').write_text(render_placeholders(rules_agents.read_text(), ctx))
    (files_root / '.hermes.md').write_text(render_placeholders(rules_hermes.read_text(), ctx))
    (files_root / 'README.md').write_text(
        f"# {project_name}\n\nProject workspace (`/workspace` in Hermes).\n\nStart: `docs/SETUP.md`\n"
    )

    copy_tree(WORKSPACE_DOCS, files_root / 'docs')
    (files_root / 'docs' / 'SETUP.md').write_text(make_setup_doc(project_name, pack, profiles, telegram, discord))
    (files_root / 'docs' / 'INDEX.md').write_text(docs_index())

    for doc in SHARED_DOCS:
        src = PKG_ROOT / 'shared' / doc
        if src.exists():
            (files_root / 'docs' / doc).write_text(render_placeholders(src.read_text(), ctx))

    copy_tree(PKG_ROOT / 'prompts', files_root / 'prompts')

    for prof in profiles:
        src = profile_soul_source(prof, project_name)
        if not src.exists():
            raise SystemExit(f'Missing profile template: {src}')
        seed = target / 'scripts' / 'seed' / 'profiles' / prof / 'SOUL.md'
        seed.parent.mkdir(parents=True, exist_ok=True)
        seed.write_text(render_placeholders(src.read_text(), ctx))

    (target / '.gitignore').write_text(GITIGNORE)
    (target / '.dockerignore').write_text(DOCKERIGNORE)
    (target / '.env.example').write_text(
        '# Do not commit .env\n# Add provider creds at runtime via hermes auth add <provider>\n'
    )
    (target / 'docker-compose.yml').write_text(docker_compose_yaml(project_name, docker, native_slug, [native_slug]))
    (target / 'README.md').write_text(
        f"# {project_name}\n\nGenerated by create-workframe.\n\n"
        "Quick start: see `Files/docs/SETUP.md`\n"
    )

    scripts = target / 'scripts'
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / 'setup.sh').write_text(setup_sh())
    (scripts / 'setup.sh').chmod(0o755)
    (scripts / 'setup.ps1').write_text(setup_ps1())
    (scripts / 'bootstrap-profiles.sh').write_text(bootstrap_profiles_sh(profiles, project_name, native_slug, docker))
    (scripts / 'bootstrap-profiles.sh').chmod(0o755)
    (scripts / 'bootstrap-profiles.ps1').write_text(bootstrap_profiles_ps1(profiles, project_name, native_slug, docker))

    wf = target / '.github' / 'workflows'
    wf.mkdir(parents=True, exist_ok=True)
    (wf / 'workframe-security.yml').write_text(CI_WORKFLOW)

    manifest = {
        'generator': 'workframe/scripts/create_workframe_scaffold.py',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'project_name': project_name,
        'project_slug': slug,
        'pack': pack,
        'profiles': profiles,
        'native_agent': {
            'display_name': native_name,
            'profile_slug': native_slug,
        },
        'docker': {
            'image': docker['image'],
            'stack': docker['stack'],
            'network': docker['network'],
            'containers': {
                'gateway': docker['gateway'],
                'dashboard': docker['dashboard'],
                'chat': docker['chat'],
                'setup': docker['setup'],
            },
        },
        'integrations': {'telegram': telegram, 'discord': discord},
        'layout': {'workspace': 'Files', 'runtime': 'Agents'},
        'security': {
            'no_instance_data_in_template': True,
            'runtime_state_directory': 'Agents',
        },
    }
    (target / 'workframe-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description='Generate minimal project workspace from Workframe package')
    ap.add_argument('project_name', nargs='?', help='Project folder name to generate')
    ap.add_argument('--pack', default='vanilla', help='Starter pack: vanilla/core/product/engineering/full')
    ap.add_argument('--output', default='/workspace/generated', help='Output root directory')
    ap.add_argument('--force', action='store_true', help='Overwrite target if exists')
    ap.add_argument('--ci', action='store_true', help='Non-interactive strict mode')
    ap.add_argument('--telegram', action='store_true', help='Include Telegram onboarding steps')
    ap.add_argument('--discord', action='store_true', help='Include Discord onboarding steps')
    ap.add_argument('--list-packs', action='store_true', help='List available packs')
    args = ap.parse_args()

    packs = load_packs(PACKS_JSON)

    if args.list_packs:
        for name, info in packs.items():
            print(f"{name}: {info.get('description', '')}")
        return

    if not args.project_name:
        raise SystemExit('project_name is required unless --list-packs is used')

    target = generate(
        args.project_name,
        args.pack,
        Path(args.output),
        args.force,
        args.telegram,
        args.discord,
    )
    print(target)


if __name__ == '__main__':
    main()
