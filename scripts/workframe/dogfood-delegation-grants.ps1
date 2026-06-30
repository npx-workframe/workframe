# Dogfood: mutual agent-delegation grants (Alan <-> Fab) for cross-user kanban assign.
$ErrorActionPreference = 'Stop'
$Alan = '44fb344c-0954-47b6-a19a-ebbcf20e9680'
$Fab = 'cb6a2db4-ac86-4c49-8247-14a1d68aca72'
$py = @"
import server
conn = server._workframe_db()
row = conn.execute('SELECT id FROM workspaces ORDER BY created_at LIMIT 1').fetchone()
conn.close()
if not row:
    raise SystemExit('no workspace')
ws = row[0]
for g, e in [('$Alan', '$Fab'), ('$Fab', '$Alan')]:
    try:
        r = server.create_delegation_grant(ws, g, e)
        print('grant', g[:8], '->', e[:8], r.get('id', 'ok'))
    except Exception as ex:
        print('skip', g[:8], '->', e[:8], ex)
"@
docker exec workframe-api python -c $py
