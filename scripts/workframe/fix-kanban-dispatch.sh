#!/bin/bash
# Add kanban dispatch config to dev and qa profiles

for profile in dev qa; do
  CONFIG="/opt/data/profiles/${profile}/config.yaml"
  
  # Check if kanban dispatch config already exists
  if grep -q 'dispatch_in_gateway' "$CONFIG"; then
    echo "dispatch_in_gateway already in ${profile} config"
    continue
  fi
  
  # Add kanban block after toolsets section
  # Find the line with "toolsets:" and add after the last toolset item
  python3 << PYEOF
import yaml
import sys

config_path = "${config}"
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

config['kanban'] = {
    'dispatch_in_gateway': True,
    'dispatch_interval_seconds': 60,
    'failure_limit': 2,
}

with open(config_path, 'w') as f:
    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

print(f"Updated {config_path}")
PYEOF
done

# Restart dev and qa gateways to pick up new config
echo ""
echo "Restarting dev gateway..."
hermes -p dev gateway restart 2>&1 || true
sleep 2

echo "Restarting qa gateway..."
hermes -p qa gateway restart 2>&1 || true
sleep 2

echo ""
echo "=== Gateway Status ==="
hermes -p dev gateway status 2>&1 | head -3
echo "---"
hermes -p qa gateway status 2>&1 | head -3
