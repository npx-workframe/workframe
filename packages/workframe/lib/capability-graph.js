export function buildCapabilityGraph(report) {
  const runtimes = Object.fromEntries(report.runtimes.map((item) => [item.id, item]));
  const providers = Object.fromEntries(report.providers.map((item) => [item.id, item]));
  const candidates = [];

  const codex = runtimes.codex;
  if (codex?.status === 'verified' || codex?.status === 'detected') {
    candidates.push({
      id: 'codex-runtime',
      label: 'Codex CLI',
      kind: 'runtime',
      credential_class: 'account',
      payer: 'user_codex_or_chatgpt_account',
      eligibility: codex.status === 'authenticated' ? 'authenticated_account' : 'installed_not_authenticated',
      status: codex.status,
      invocation: 'codex exec',
      cancellable: true,
    });
  }

  const claude = runtimes.claude;
  if (claude?.status === 'verified' || claude?.status === 'detected') {
    candidates.push({
      id: 'claude-runtime',
      label: 'Claude Code',
      kind: 'runtime',
      credential_class: 'account',
      payer: 'user_claude_account',
      eligibility: claude.status === 'authenticated' ? 'authenticated_account' : 'verified_runtime',
      status: claude.status,
      invocation: 'claude -p',
      cancellable: true,
    });
  }

  if (providers.anthropic?.status === 'configured') {
    candidates.push({
      id: 'anthropic-api',
      label: 'Anthropic API',
      kind: 'provider',
      credential_class: 'api_key',
      payer: 'user_anthropic_api_key',
      eligibility: 'configured_key',
      status: 'configured',
      invocation: 'anthropic_api',
      cancellable: true,
    });
  }

  for (const id of ['openrouter', 'openai', 'google']) {
    const provider = providers[id];
    if (provider?.status === 'configured') {
      candidates.push({
        id: `${id}-api`,
        label: provider.label,
        kind: 'provider',
        credential_class: 'api_key',
        payer: `user_${id}_api_key`,
        eligibility: 'configured_key',
        status: 'configured',
        invocation: `${id}_api`,
        cancellable: true,
      });
    }
  }

  return {
    schema_version: '0.1',
    candidates,
    notes: [
      'installed does not imply authenticated',
      'authenticated does not imply verified inference',
      'no candidate is selected automatically',
    ],
  };
}

export function listEligibleVerificationCandidates(graph) {
  return graph.candidates.filter((item) =>
    item.eligibility === 'authenticated_account'
    || item.eligibility === 'configured_key'
    || item.eligibility === 'verified_runtime',
  );
}
