#!/usr/bin/env bash
# ponytail: CI/harness entry — same checks as package.json typecheck script.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python}"
$PY -m py_compile server.py zk_auth.py email_sender.py profile_config_yaml.py route_registry.py
$PY test_public_routes.py
$PY test_route_registry.py
$PY test_billing_provider.py
$PY test_model_surface_consistency.py
$PY test_profile_model_yaml.py
