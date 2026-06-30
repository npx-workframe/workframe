#!/usr/bin/env python3
"""Static security hygiene scan for the Workframe package source."""

from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = {
    'aws_access_key': re.compile(r'AKIA[0-9A-Z]{16}'),
    'github_pat': re.compile(r'ghp_[A-Za-z0-9]{36}'),
    'slack_token': re.compile(r'xox[baprs]-[A-Za-z0-9-]{10,}'),
    'telegram_bot_token': re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b'),
    'discord_token': re.compile(r'[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}'),
    'private_key': re.compile(r'-----BEGIN (?:RSA|EC|OPENSSH|DSA|PGP|PRIVATE) KEY-----'),
    'generic_secret_assignment': re.compile(r'(?i)(api[_-]?key|token|secret)\s*[:=]\s*["\']?[A-Za-z0-9_\-]{16,}'),
}

IGNORE_PARTS = {'.venv', '__pycache__', '.pytest_cache', 'node_modules'}

REQUIRED_IGNORE_PATTERNS = [
    'Agents/', '.env', '*.db', 'logs/', 'memories/', 'sessions/', 'kanban/',
]

INSTANCE_ARTIFACT_PATTERNS = [
    re.compile(r'\buser_id\b', re.IGNORECASE),
    re.compile(r'\bmessage_id\b', re.IGNORECASE),
    re.compile(r'\bgateway_state\b', re.IGNORECASE),
    re.compile(r'\bkanban\.db\b', re.IGNORECASE),
]

# Project-specific / PII-adjacent names — must not appear in publishable templates
BANNED_TERM_PATTERNS = [
    ('glitch', re.compile(r'\bglitch\b', re.IGNORECASE)),
    ('zeta', re.compile(r'\bzeta\b', re.IGNORECASE)),
    ('alan', re.compile(r'\balan\b', re.IGNORECASE)),
]

# Skip docs that document the ban itself
BANNED_TERM_SKIP = {'security_audit.py'}


def iter_files(root: Path):
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        if any(part in IGNORE_PARTS for part in p.parts):
            continue
        yield p


def scan_secrets():
    findings = []
    for p in iter_files(ROOT):
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(errors='ignore')
        for name, pattern in SECRET_PATTERNS.items():
            for m in pattern.finditer(text):
                findings.append({
                    'severity': 'high',
                    'type': 'secret_pattern',
                    'rule': name,
                    'file': rel,
                    'excerpt': m.group(0)[:80],
                })
    return findings


def scan_gitignore_coverage():
    findings = []
    gi = ROOT / '.gitignore'
    if not gi.exists():
        findings.append({
            'severity': 'high',
            'type': 'missing_gitignore',
            'file': '.gitignore',
            'rule': 'required file missing',
        })
        return findings

    content = gi.read_text(errors='ignore')
    for req in REQUIRED_IGNORE_PATTERNS:
        if req not in content:
            findings.append({
                'severity': 'medium',
                'type': 'gitignore_gap',
                'file': '.gitignore',
                'rule': f'missing pattern {req}',
            })
    return findings


def scan_instance_artifacts():
    findings = []
    for p in iter_files(ROOT):
        if p.name in {'.gitignore', '.dockerignore', '.npmignore'}:
            continue
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(errors='ignore')
        for pattern in INSTANCE_ARTIFACT_PATTERNS:
            for m in pattern.finditer(text):
                findings.append({
                    'severity': 'medium',
                    'type': 'instance_artifact_reference',
                    'file': rel,
                    'rule': pattern.pattern,
                    'excerpt': m.group(0),
                })
    return findings


def scan_banned_terms():
    findings = []
    for p in iter_files(ROOT):
        rel = p.relative_to(ROOT).as_posix()
        if p.name in BANNED_TERM_SKIP:
            continue
        text = p.read_text(errors='ignore')
        for term, pattern in BANNED_TERM_PATTERNS:
            for m in pattern.finditer(text):
                findings.append({
                    'severity': 'medium',
                    'type': 'banned_term',
                    'rule': term,
                    'file': rel,
                    'excerpt': m.group(0),
                })
    return findings


def main():
    findings = []
    findings.extend(scan_secrets())
    findings.extend(scan_gitignore_coverage())
    findings.extend(scan_instance_artifacts())
    findings.extend(scan_banned_terms())

    high = [f for f in findings if f['severity'] == 'high']
    medium = [f for f in findings if f['severity'] == 'medium']

    report = {
        'root': str(ROOT),
        'findings_total': len(findings),
        'high': len(high),
        'medium': len(medium),
        'findings': findings,
    }

    print(json.dumps(report, indent=2))
    raise SystemExit(1 if high else 0)


if __name__ == '__main__':
    main()
