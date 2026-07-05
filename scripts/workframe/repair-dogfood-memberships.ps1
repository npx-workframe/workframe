# DEPRECATED — hardcoded runtime/ DB repair. Reset dogfood instead.
Write-Error @'
repair-dogfood-memberships.ps1 is deprecated (targeted runtime/workframe-api-data).

Reset local dogfood:
  .\scripts\workframe\reset-dogfood-docker.ps1 -Confirm

See scripts/workframe/README.md
'@
exit 1
