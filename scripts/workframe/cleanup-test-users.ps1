# Soft-delete test workspace members from local runtime workframe.db.
param(
  [string]$DataDir = (Join-Path $PSScriptRoot '..\..\runtime\workframe-api-data'),
  [string[]]$Emails = @('hosttest3@example.com', 'proxytest@example.com')
)

$ErrorActionPreference = 'Stop'
$dbPath = (Resolve-Path (Join-Path $DataDir 'workframe.db')).Path
$emailLiterals = ($Emails | ForEach-Object { "'" + $_.Replace("'", "''").ToLower() + "'" }) -join ', '
$py = @"
import sqlite3, time
emails = ($emailLiterals)
ts = int(time.time())
conn = sqlite3.connect(r'$dbPath')
ph = ','.join('?' * len(emails))
conn.execute(
    f'''UPDATE workspace_memberships SET deleted_at = ?, status = 'removed'
        WHERE user_id IN (SELECT id FROM users WHERE lower(email) IN ({ph}))
          AND deleted_at IS NULL''',
    [ts, *emails],
)
conn.execute(
    f'''UPDATE users SET deleted_at = ? WHERE lower(email) IN ({ph}) AND deleted_at IS NULL''',
    [ts, *emails],
)
conn.commit()
conn.close()
print('ok')
"@
python -c $py
Write-Host "Cleanup applied for: $($Emails -join ', ')"
Write-Host "DB: $dbPath"
