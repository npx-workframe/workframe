#!/bin/bash
# Register dev and qa gateway services with s6

for profile in dev qa; do
  # Add to user bundle
  touch /etc/s6-overlay/s6-rc.d/user/contents.d/gateway-${profile}
  echo "Added gateway-${profile} to user bundle"
done

echo "User bundle contents:"
ls /etc/s6-overlay/s6-rc.d/user/contents.d/

# Now compile the s6-rc database
if command -v s6-rc-compile >/dev/null 2>&1; then
  echo "Compiling s6-rc database..."
  s6-rc-compile /etc/s6-overlay/s6-rc/compiled /etc/s6-overlay/s6-rc.d/ 2>&1
  echo "Compilation done"
else
  echo "s6-rc-compile not found, trying s6-rc update..."
  s6-rc -u change 2>&1 || true
fi

# Start the new services
sleep 2
for profile in dev qa; do
  echo "Starting gateway-${profile}..."
  # The service directory already exists at /run/service/gateway-${profile}
  # We need to tell s6-svscan to pick it up
  # Send a command to s6-svscan via the control pipe
  if [ -d /run/service/gateway-${profile} ]; then
    echo "Service directory exists for ${profile}"
    # Tell s6 about the new service
    s6-svscanctl -an /run/service 2>/dev/null || true
    sleep 2
    # Check if s6-supervise picked it up
    if [ -d /run/service/gateway-${profile}/supervise ]; then
      echo "s6-supervise picked up gateway-${profile}"
    else
      echo "s6-supervise has NOT picked up gateway-${profile} yet"
    fi
  fi
done

# Final status check
echo ""
echo "=== Gateway Status ==="
hermes -p dev gateway status 2>&1
echo "---"
hermes -p qa gateway status 2>&1
