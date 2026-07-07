#!/bin/sh
# WF-025: iptables sidecar for gateway — block direct brokered provider egress.
# Runs in gateway network namespace (docker-compose.egress-broker.yml).
set -eu

API_HOST="${WORKFRAME_API_HOST:-workframe-api}"
PROVIDER_HOSTS="${WORKFRAME_BROKERED_PROVIDER_HOSTS:-openrouter.ai api.openai.com api.anthropic.com generativelanguage.googleapis.com api.deepseek.com api.github.com api.vercel.com api.netlify.com}"

install_packages() {
  if command -v apk >/dev/null 2>&1; then
    apk add --no-cache iptables bind-tools >/dev/null 2>&1 || true
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq >/dev/null 2>&1 || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iptables dnsutils >/dev/null 2>&1 || true
  fi
}

install_rules() {
  iptables -N WF_EGRESS_BROKER 2>/dev/null || iptables -F WF_EGRESS_BROKER
  iptables -C OUTPUT -j WF_EGRESS_BROKER 2>/dev/null || iptables -I OUTPUT 1 -j WF_EGRESS_BROKER

  iptables -A WF_EGRESS_BROKER -o lo -j ACCEPT
  iptables -A WF_EGRESS_BROKER -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null \
    || iptables -A WF_EGRESS_BROKER -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null \
    || true

  api_ip="$(getent ahostsv4 "$API_HOST" 2>/dev/null | awk '{print $1}' | head -n1 || true)"
  if [ -n "$api_ip" ]; then
    iptables -A WF_EGRESS_BROKER -d "$api_ip" -j ACCEPT
  fi

  for host in $PROVIDER_HOSTS; do
    for ip in $(getent ahostsv4 "$host" 2>/dev/null | awk '{print $1}' | sort -u); do
      [ -n "$ip" ] || continue
      iptables -A WF_EGRESS_BROKER -d "$ip" -p tcp -m multiport --dports 80,443 -j DROP 2>/dev/null \
        || iptables -A WF_EGRESS_BROKER -d "$ip" -p tcp --dport 443 -j DROP
    done
  done

  iptables -A WF_EGRESS_BROKER -j RETURN
}

install_packages
install_rules
# ponytail: hourly refresh — provider IPs drift; sidecar stays alive with gateway netns.
while true; do
  sleep 3600
  install_rules
done
