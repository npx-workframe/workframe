# Restore dogfood workspace memberships after a bad cleanup-test-users run.
$ErrorActionPreference = 'Stop'
$dbPath = (Resolve-Path (Join-Path $PSScriptRoot '..\..\runtime\workframe-api-data\workframe.db')).Path
$ws = '1f90a94f-f10b-4838-a81e-df5a6dc508c5'
$py = @"
import sqlite3, time
ws = '$ws'
now = str(int(time.time()))
conn = sqlite3.connect(r'$dbPath')
rows = [
    ('ceebd6bf-e08b-472b-bbc9-84834555449a', '44fb344c-0954-47b6-a19a-ebbcf20e9680', 'owner'),
    ('bd272e01-eb2d-4f53-9301-55193bc49ee5', '215ffc8a-3c09-4b5d-86d9-c63b3c665e61', 'member'),
    ('a5c137c9-ffd7-43a2-b020-ea7682e2a1db', 'cb6a2db4-ac86-4c49-8247-14a1d68aca72', 'member'),
]
for mid, uid, role in rows:
    conn.execute(
        '''UPDATE workspace_memberships
           SET deleted_at = NULL, status = 'active', role = ?, updated_at = ?
           WHERE id = ? AND workspace_id = ?''',
        (role, now, mid, ws),
    )
    conn.execute(
        'UPDATE users SET current_workspace_id = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL',
        (ws, now, uid),
    )
conn.commit()
active = conn.execute(
    'SELECT user_id, role, status, deleted_at FROM workspace_memberships WHERE workspace_id = ?',
    (ws,),
).fetchall()
print('memberships', active)
conn.close()
"@
python -c $py
Write-Host "Restored dogfood memberships in $dbPath"
