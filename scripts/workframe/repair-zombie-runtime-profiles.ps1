# Repair zombie per-user runtime profiles (Hermes registry without profile/config yaml).
# Safe to run with stack up. Does NOT touch local %LOCALAPPDATA%\\hermes.
$ErrorActionPreference = 'Stop'
$py = @'
import server, re
root = server._profile_dir('')
profiles = server._profile_dir('').parent
uuid_rt = re.compile(r'^u-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{8}-[a-z0-9-]+$')
for path in sorted(profiles.iterdir()):
    if not path.is_dir():
        continue
    slug = path.name
    if not uuid_rt.fullmatch(slug):
        continue
    cfg = path / 'config.yaml'
    if not cfg.is_file():
        cfg = path / 'profile.yaml'
    if cfg.is_file():
        if not server._runtime_gateway_registered(slug):
            ok, out, _ = server._configure_profile_api(slug)
            print('repair gw', slug, 'ok' if ok else out[:120])
        continue
    print('purge zombie', slug)
    server._purge_runtime_profile(slug)
print('done')
'@
docker exec workframe-api python -c $py
