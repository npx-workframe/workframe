"""Speed bump for cross-profile secret reads — not an ACL. Real isolation = vault + per-profile mount."""
from __future__ import annotations

import re

# ponytail: shared by workframe-api and workframe-supervisor (copy in supervisor image)
_PROFILE_SECRET_PATH = re.compile(
    r"(?:/opt/data/)?profiles/[^/\s]+/(?:\.env|auth\.json|credentials\.json|\.git-credentials|cookies\.txt)",
    re.IGNORECASE,
)
_PROFILE_SLUG_REF = re.compile(
    r"(?:/opt/data/)?profiles/([a-z0-9][a-z0-9-]{0,63})(?:/|$|\s)",
    re.IGNORECASE,
)
_READ_VERBS = re.compile(
    r"\b(?:cat|head|tail|sed|awk|grep|egrep|rg|less|more|od|xxd|nl|sort|wc|strings|dd|python3?|perl|ruby|node)\b",
    re.IGNORECASE,
)
_SHELL_BYPASS = re.compile(
    r"(?:\*|find\b[^\n]*-exec\b|xargs\b|\btar\b|\bbase64\b|\.e''nv|\.e\"\"nv"
    r"|&&\s*(?:cat|head|tail|sed|awk|grep|python3?|perl|dd|od|xxd|nl|sort|wc)\b"
    r"|\|\s*(?:cat|head|tail|sed|awk|grep|python3?|perl|dd|od|xxd|nl|sort|wc)\b)",
    re.IGNORECASE,
)
# ponytail: shell var indirection ceiling — catches `P=…profiles/u-bob; cat $P/.env`
# but NOT python string concat ('pro'+'files/…'). Real fix = per-profile secret broker.
_VAR_PROFILE_ASSIGN = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)=(?:[^\s;&|]*\s*)?(?:/opt/data/)?profiles/[a-z0-9][a-z0-9-]{0,63}",
    re.IGNORECASE,
)
_VAR_DEREF_SECRET = re.compile(
    r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?[^\s;&|]*/(?:\.env|auth\.json|credentials\.json|\.git-credentials|cookies\.txt)",
    re.IGNORECASE,
)


def _cmd_blob(cmd: list[str] | str) -> str:
    return " ".join(str(part) for part in cmd) if isinstance(cmd, list) else str(cmd)


def referenced_profile_slugs(cmd: list[str] | str) -> set[str]:
    return {m.group(1).lower() for m in _PROFILE_SLUG_REF.finditer(_cmd_blob(cmd))}


def is_secret_read_attempt(cmd: list[str] | str) -> bool:
    blob = _cmd_blob(cmd)
    if _PROFILE_SECRET_PATH.search(blob):
        return True
    if "profiles/" in blob.lower() and _SHELL_BYPASS.search(blob):
        return True
    if _PROFILE_SLUG_REF.search(blob) and _READ_VERBS.search(blob):
        return True
    assigned = {m.group(1) for m in _VAR_PROFILE_ASSIGN.finditer(blob)}
    if assigned:
        for m in _VAR_DEREF_SECRET.finditer(blob):
            if m.group(1) in assigned:
                return True
    return False


def touches_foreign_profile_secrets(cmd: list[str] | str, allowed_profile: str) -> bool:
    """True when command references another profile's tree (0022 N2 / 0023 C1)."""
    allowed = str(allowed_profile or "").strip().lower()
    if not allowed:
        return False
    slugs = referenced_profile_slugs(cmd)
    return bool(slugs - {allowed})


def exec_blocked_for_profile(cmd: list[str] | str, acting_profile: str = "") -> bool:
    if is_secret_read_attempt(cmd):
        return True
    if acting_profile and touches_foreign_profile_secrets(cmd, acting_profile):
        return True
    return False


if __name__ == "__main__":
    assert is_secret_read_attempt(["cat", "profiles/u-alice-dev/.env"])
    assert is_secret_read_attempt("cat profiles/u-bob-dev/*")
    assert is_secret_read_attempt("cd /opt/data/profiles/u-bob && head .env")
    assert is_secret_read_attempt("cd profiles/u-x && python3 -c \"print(open('.env').read())\"")
    assert touches_foreign_profile_secrets("cd profiles/u-bob && head .env", "u-alice-dev")
    assert not touches_foreign_profile_secrets("hermes -p u-alice-dev gateway status", "u-alice-dev")
    assert not is_secret_read_attempt(["hermes", "-p", "dev", "gateway", "run"])
    print("profile_secret_policy ok")
