# Set APP_BASE_URL + related keys in dogfood/VPS compose .env.
param(
  [Parameter(Mandatory = $true)][string]$PublicUrl,
  [string]$EnvFile = ""
)

$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$script = Join-Path $PSScriptRoot "set-compose-public-url.mjs"
$args = @($PublicUrl)
if ($EnvFile) { $args += @('--env', $EnvFile) }
node $script @args
