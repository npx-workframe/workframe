# Reference compose (not local dogfood)

This directory is the **canonical Docker compose template** synced into `create-workframe` on publish.

**Do not use it as local dogfood.** Local dogfood is a generated install:

```powershell
# from workframe repo
.\scripts\workframe\reset-dogfood-docker.ps1 -Confirm
# → ../MyBusiness (npx create-workframe)
```

Use this folder for:

- Reviewing service topology before it ships in the installer
- `PUBLIC_DEPLOY.md` checklist (public VPS overlay semantics)
- Sync source for `packages/create-workframe` compose templates

Operator map: `scripts/workframe/README.md`
