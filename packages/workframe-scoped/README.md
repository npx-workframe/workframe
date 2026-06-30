# @workframe/workframe

Scoped mirror of the `workframe` lifecycle CLI.

This package exists to establish the `@workframe/workframe` npm path without introducing a second, different product surface.

Current public package surfaces:

- `workframe`: unscoped lifecycle CLI for existing Workframe projects
- `create-workframe`: unscoped scaffold package for creating Workframe projects
- `@workframe/workframe`: scoped mirror of the same lifecycle CLI

Both of these commands should mean the same thing:

```bash
npx workframe help
npx @workframe/workframe help
```

Use `create-workframe` when you want to scaffold a new Workframe project:

```bash
npx create-workframe --help
```
