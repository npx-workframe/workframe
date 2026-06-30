$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path "$Root\Agents")) {
  throw "Agents/ missing. Run Hermes setup first."
}

Write-Host "Creating profile: workframe-agent"
$profilesRoot = Join-Path $Root "Agents\profiles"
$profileDir = Join-Path $profilesRoot "workframe-agent"
$profileConfig = Join-Path $profileDir "config.yaml"
New-Item -ItemType Directory -Force -Path $profilesRoot | Out-Null

docker run --rm --name "workframe-bootstrap-workframe-agent-show-precheck" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile show workframe-agent 2>$null | Out-Null
$profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
if ($profileReady) {
  Write-Host "Profile workframe-agent already exists, continuing."
} else {
  docker run --rm --name "workframe-bootstrap-workframe-agent-clean" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile delete -y workframe-agent 2>$null | Out-Null
  if (Test-Path $profileDir) {
    Remove-Item -Recurse -Force $profileDir
  }
  $createOut = docker run --rm --name "workframe-bootstrap-workframe-agent" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile create workframe-agent --clone --description "Workframe Agent: Workframe Manager, orchestrator, and Workframe admin." 2>&1
  if ($LASTEXITCODE -ne 0) {
    docker run --rm --name "workframe-bootstrap-workframe-agent-show" --entrypoint hermes `
      -v "$Root\Agents:/opt/data" `
      -v "$Root\Files:/workspace" `
      nousresearch/hermes-agent:latest profile show workframe-agent 2>$null | Out-Null
    $profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
    if ($profileReady) {
      Write-Host "Profile workframe-agent already exists, continuing."
    } else {
      Write-Host "Retrying profile create after cleaning incomplete registration: workframe-agent"
      docker run --rm --name "workframe-bootstrap-workframe-agent-clean-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile delete -y workframe-agent 2>$null | Out-Null
      if (Test-Path $profileDir) {
        Remove-Item -Recurse -Force $profileDir
      }
      $createOut = docker run --rm --name "workframe-bootstrap-workframe-agent-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile create workframe-agent --clone --description "Workframe Agent: Workframe Manager, orchestrator, and Workframe admin." 2>&1
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to create profile workframe-agent: $createOut"
      }
    }
  }
}

$seed = Join-Path $Root "scripts\seed\profiles\workframe-agent\SOUL.md"
$destDir = Join-Path $Root "Agents\profiles\workframe-agent"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}
$setupSeed = Join-Path $Root "scripts\seed\profiles\workframe-agent\SETUP.md"
if (Test-Path $setupSeed) {
  Copy-Item $setupSeed (Join-Path $destDir "SETUP.md") -Force
}


Write-Host "Creating profile: visionary"
$profilesRoot = Join-Path $Root "Agents\profiles"
$profileDir = Join-Path $profilesRoot "visionary"
$profileConfig = Join-Path $profileDir "config.yaml"
New-Item -ItemType Directory -Force -Path $profilesRoot | Out-Null

docker run --rm --name "workframe-bootstrap-visionary-show-precheck" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile show visionary 2>$null | Out-Null
$profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
if ($profileReady) {
  Write-Host "Profile visionary already exists, continuing."
} else {
  docker run --rm --name "workframe-bootstrap-visionary-clean" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile delete -y visionary 2>$null | Out-Null
  if (Test-Path $profileDir) {
    Remove-Item -Recurse -Force $profileDir
  }
  $createOut = docker run --rm --name "workframe-bootstrap-visionary" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile create visionary --clone --description "Clarifies product purpose, positioning, strategy, user value, and long-term alignment." 2>&1
  if ($LASTEXITCODE -ne 0) {
    docker run --rm --name "workframe-bootstrap-visionary-show" --entrypoint hermes `
      -v "$Root\Agents:/opt/data" `
      -v "$Root\Files:/workspace" `
      nousresearch/hermes-agent:latest profile show visionary 2>$null | Out-Null
    $profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
    if ($profileReady) {
      Write-Host "Profile visionary already exists, continuing."
    } else {
      Write-Host "Retrying profile create after cleaning incomplete registration: visionary"
      docker run --rm --name "workframe-bootstrap-visionary-clean-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile delete -y visionary 2>$null | Out-Null
      if (Test-Path $profileDir) {
        Remove-Item -Recurse -Force $profileDir
      }
      $createOut = docker run --rm --name "workframe-bootstrap-visionary-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile create visionary --clone --description "Clarifies product purpose, positioning, strategy, user value, and long-term alignment." 2>&1
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to create profile visionary: $createOut"
      }
    }
  }
}

$seed = Join-Path $Root "scripts\seed\profiles\visionary\SOUL.md"
$destDir = Join-Path $Root "Agents\profiles\visionary"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}


Write-Host "Creating profile: architect"
$profilesRoot = Join-Path $Root "Agents\profiles"
$profileDir = Join-Path $profilesRoot "architect"
$profileConfig = Join-Path $profileDir "config.yaml"
New-Item -ItemType Directory -Force -Path $profilesRoot | Out-Null

docker run --rm --name "workframe-bootstrap-architect-show-precheck" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile show architect 2>$null | Out-Null
$profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
if ($profileReady) {
  Write-Host "Profile architect already exists, continuing."
} else {
  docker run --rm --name "workframe-bootstrap-architect-clean" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile delete -y architect 2>$null | Out-Null
  if (Test-Path $profileDir) {
    Remove-Item -Recurse -Force $profileDir
  }
  $createOut = docker run --rm --name "workframe-bootstrap-architect" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile create architect --clone --description "Defines system design, technical boundaries, implementation plans, and code-review standards." 2>&1
  if ($LASTEXITCODE -ne 0) {
    docker run --rm --name "workframe-bootstrap-architect-show" --entrypoint hermes `
      -v "$Root\Agents:/opt/data" `
      -v "$Root\Files:/workspace" `
      nousresearch/hermes-agent:latest profile show architect 2>$null | Out-Null
    $profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
    if ($profileReady) {
      Write-Host "Profile architect already exists, continuing."
    } else {
      Write-Host "Retrying profile create after cleaning incomplete registration: architect"
      docker run --rm --name "workframe-bootstrap-architect-clean-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile delete -y architect 2>$null | Out-Null
      if (Test-Path $profileDir) {
        Remove-Item -Recurse -Force $profileDir
      }
      $createOut = docker run --rm --name "workframe-bootstrap-architect-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile create architect --clone --description "Defines system design, technical boundaries, implementation plans, and code-review standards." 2>&1
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to create profile architect: $createOut"
      }
    }
  }
}

$seed = Join-Path $Root "scripts\seed\profiles\architect\SOUL.md"
$destDir = Join-Path $Root "Agents\profiles\architect"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}


Write-Host "Creating profile: docs"
$profilesRoot = Join-Path $Root "Agents\profiles"
$profileDir = Join-Path $profilesRoot "docs"
$profileConfig = Join-Path $profileDir "config.yaml"
New-Item -ItemType Directory -Force -Path $profilesRoot | Out-Null

docker run --rm --name "workframe-bootstrap-docs-show-precheck" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile show docs 2>$null | Out-Null
$profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
if ($profileReady) {
  Write-Host "Profile docs already exists, continuing."
} else {
  docker run --rm --name "workframe-bootstrap-docs-clean" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile delete -y docs 2>$null | Out-Null
  if (Test-Path $profileDir) {
    Remove-Item -Recurse -Force $profileDir
  }
  $createOut = docker run --rm --name "workframe-bootstrap-docs" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile create docs --clone --description "Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries." 2>&1
  if ($LASTEXITCODE -ne 0) {
    docker run --rm --name "workframe-bootstrap-docs-show" --entrypoint hermes `
      -v "$Root\Agents:/opt/data" `
      -v "$Root\Files:/workspace" `
      nousresearch/hermes-agent:latest profile show docs 2>$null | Out-Null
    $profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
    if ($profileReady) {
      Write-Host "Profile docs already exists, continuing."
    } else {
      Write-Host "Retrying profile create after cleaning incomplete registration: docs"
      docker run --rm --name "workframe-bootstrap-docs-clean-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile delete -y docs 2>$null | Out-Null
      if (Test-Path $profileDir) {
        Remove-Item -Recurse -Force $profileDir
      }
      $createOut = docker run --rm --name "workframe-bootstrap-docs-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile create docs --clone --description "Maintains AGENTS.md, .hermes.md, docs indexes, source-of-truth maps, and change summaries." 2>&1
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to create profile docs: $createOut"
      }
    }
  }
}

$seed = Join-Path $Root "scripts\seed\profiles\docs\SOUL.md"
$destDir = Join-Path $Root "Agents\profiles\docs"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}


Write-Host "Creating profile: dev"
$profilesRoot = Join-Path $Root "Agents\profiles"
$profileDir = Join-Path $profilesRoot "dev"
$profileConfig = Join-Path $profileDir "config.yaml"
New-Item -ItemType Directory -Force -Path $profilesRoot | Out-Null

docker run --rm --name "workframe-bootstrap-dev-show-precheck" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile show dev 2>$null | Out-Null
$profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
if ($profileReady) {
  Write-Host "Profile dev already exists, continuing."
} else {
  docker run --rm --name "workframe-bootstrap-dev-clean" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile delete -y dev 2>$null | Out-Null
  if (Test-Path $profileDir) {
    Remove-Item -Recurse -Force $profileDir
  }
  $createOut = docker run --rm --name "workframe-bootstrap-dev" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile create dev --clone --description "Builds and modifies project files, scripts, tests, and implementation artifacts." 2>&1
  if ($LASTEXITCODE -ne 0) {
    docker run --rm --name "workframe-bootstrap-dev-show" --entrypoint hermes `
      -v "$Root\Agents:/opt/data" `
      -v "$Root\Files:/workspace" `
      nousresearch/hermes-agent:latest profile show dev 2>$null | Out-Null
    $profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
    if ($profileReady) {
      Write-Host "Profile dev already exists, continuing."
    } else {
      Write-Host "Retrying profile create after cleaning incomplete registration: dev"
      docker run --rm --name "workframe-bootstrap-dev-clean-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile delete -y dev 2>$null | Out-Null
      if (Test-Path $profileDir) {
        Remove-Item -Recurse -Force $profileDir
      }
      $createOut = docker run --rm --name "workframe-bootstrap-dev-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile create dev --clone --description "Builds and modifies project files, scripts, tests, and implementation artifacts." 2>&1
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to create profile dev: $createOut"
      }
    }
  }
}

$seed = Join-Path $Root "scripts\seed\profiles\dev\SOUL.md"
$destDir = Join-Path $Root "Agents\profiles\dev"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}


Write-Host "Creating profile: research"
$profilesRoot = Join-Path $Root "Agents\profiles"
$profileDir = Join-Path $profilesRoot "research"
$profileConfig = Join-Path $profileDir "config.yaml"
New-Item -ItemType Directory -Force -Path $profilesRoot | Out-Null

docker run --rm --name "workframe-bootstrap-research-show-precheck" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile show research 2>$null | Out-Null
$profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
if ($profileReady) {
  Write-Host "Profile research already exists, continuing."
} else {
  docker run --rm --name "workframe-bootstrap-research-clean" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile delete -y research 2>$null | Out-Null
  if (Test-Path $profileDir) {
    Remove-Item -Recurse -Force $profileDir
  }
  $createOut = docker run --rm --name "workframe-bootstrap-research" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile create research --clone --description "Performs technical research, market research, references, competitive analysis, and R&D notes." 2>&1
  if ($LASTEXITCODE -ne 0) {
    docker run --rm --name "workframe-bootstrap-research-show" --entrypoint hermes `
      -v "$Root\Agents:/opt/data" `
      -v "$Root\Files:/workspace" `
      nousresearch/hermes-agent:latest profile show research 2>$null | Out-Null
    $profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
    if ($profileReady) {
      Write-Host "Profile research already exists, continuing."
    } else {
      Write-Host "Retrying profile create after cleaning incomplete registration: research"
      docker run --rm --name "workframe-bootstrap-research-clean-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile delete -y research 2>$null | Out-Null
      if (Test-Path $profileDir) {
        Remove-Item -Recurse -Force $profileDir
      }
      $createOut = docker run --rm --name "workframe-bootstrap-research-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile create research --clone --description "Performs technical research, market research, references, competitive analysis, and R&D notes." 2>&1
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to create profile research: $createOut"
      }
    }
  }
}

$seed = Join-Path $Root "scripts\seed\profiles\research\SOUL.md"
$destDir = Join-Path $Root "Agents\profiles\research"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}


Write-Host "Creating profile: designer"
$profilesRoot = Join-Path $Root "Agents\profiles"
$profileDir = Join-Path $profilesRoot "designer"
$profileConfig = Join-Path $profileDir "config.yaml"
New-Item -ItemType Directory -Force -Path $profilesRoot | Out-Null

docker run --rm --name "workframe-bootstrap-designer-show-precheck" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile show designer 2>$null | Out-Null
$profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
if ($profileReady) {
  Write-Host "Profile designer already exists, continuing."
} else {
  docker run --rm --name "workframe-bootstrap-designer-clean" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile delete -y designer 2>$null | Out-Null
  if (Test-Path $profileDir) {
    Remove-Item -Recurse -Force $profileDir
  }
  $createOut = docker run --rm --name "workframe-bootstrap-designer" --entrypoint hermes `
    -v "$Root\Agents:/opt/data" `
    -v "$Root\Files:/workspace" `
    nousresearch/hermes-agent:latest profile create designer --clone --description "Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback." 2>&1
  if ($LASTEXITCODE -ne 0) {
    docker run --rm --name "workframe-bootstrap-designer-show" --entrypoint hermes `
      -v "$Root\Agents:/opt/data" `
      -v "$Root\Files:/workspace" `
      nousresearch/hermes-agent:latest profile show designer 2>$null | Out-Null
    $profileReady = ($LASTEXITCODE -eq 0) -and (Test-Path $profileConfig)
    if ($profileReady) {
      Write-Host "Profile designer already exists, continuing."
    } else {
      Write-Host "Retrying profile create after cleaning incomplete registration: designer"
      docker run --rm --name "workframe-bootstrap-designer-clean-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile delete -y designer 2>$null | Out-Null
      if (Test-Path $profileDir) {
        Remove-Item -Recurse -Force $profileDir
      }
      $createOut = docker run --rm --name "workframe-bootstrap-designer-retry" --entrypoint hermes `
        -v "$Root\Agents:/opt/data" `
        -v "$Root\Files:/workspace" `
        nousresearch/hermes-agent:latest profile create designer --clone --description "Handles UI direction, design docs, visual assets, image prompts, brand direction, and layout feedback." 2>&1
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to create profile designer: $createOut"
      }
    }
  }
}

$seed = Join-Path $Root "scripts\seed\profiles\designer\SOUL.md"
$destDir = Join-Path $Root "Agents\profiles\designer"
if (Test-Path $seed) {
  New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  Copy-Item $seed (Join-Path $destDir "SOUL.md") -Force
}


Write-Host "Setting default profile to workframe-agent..."
docker run --rm --name "workframe-bootstrap-use" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile use workframe-agent

Write-Host "Full pack bootstrap complete. Start chat with: .\scripts\chat.ps1"
docker run --rm --name "workframe-bootstrap-list" --entrypoint hermes `
  -v "$Root\Agents:/opt/data" `
  -v "$Root\Files:/workspace" `
  nousresearch/hermes-agent:latest profile list
