# DEPRECATED — dogfood runtime lives under projects/MyBusiness/Agents, not repo runtime/.
Write-Error @'
restore-docker-runtime-from-meta.ps1 is deprecated.

Reset local dogfood:
  .\scripts\workframe\reset-dogfood-docker.ps1 -Confirm

See scripts/workframe/README.md
'@
exit 1
