---
name: obsidian-cli
description: Read, create, overwrite, append to, and search notes in an Obsidian vault via the obsidian CLI, plus plugin/theme development commands. Use for any non-trivial vault file operation — writing a chapter log, saving game state, creating or restructuring canon files, bulk edits, targeted in-place edits, or large (>30 KB) content — and whenever an obsidian command fails or writes the wrong thing.
---

# Obsidian CLI

Use the `obsidian` CLI to interact with a running Obsidian instance. Requires Obsidian to be open.

## Gotchas — read these first

Three of these have each caused a silent data loss or a write to the wrong vault.

1. **On Linux, `XDG_RUNTIME_DIR` must be set** or the CLI reports "unable to find
   Obsidian" even while Obsidian is running — it cannot locate the IPC socket. It
   is normally already in the environment; if a shell lacks it, prefix the call:
   `export XDG_RUNTIME_DIR=/run/user/$(id -u) && obsidian ...`
   (macOS does not use `XDG_RUNTIME_DIR`; if the CLI cannot find Obsidian there,
   the cause is something else.)

2. **Never `pkill -f obsidian`** — that kills the desktop app, which is the CLI's
   IPC target.

3. **`vault=` only works before the command name.** `obsidian vault="Your Vault" create ...`
   is correct; placed after the command it is silently ignored and the write lands
   in whichever vault the app currently has focus. Files have been lost this way.

4. **The documented `\n` encoding in `content=` can silently fail** — the CLI
   reports "Created" and writes an empty or mangled file. Pass real newlines
   through argv instead (`python3` + `subprocess.run([...])`), or use
   `obsidian eval` with `app.vault.create` / `app.vault.modify`, where JS `\n`
   behaves. Always verify after a large write: `wc -c` on the expected absolute
   path, and `head` to confirm real line breaks rather than literal `\n`.

5. **There is no edit/replace command.** For small in-place fixes use
   `create overwrite` with the full updated content, passing `path=` only —
   adding `name=` to an overwrite spawns a numbered duplicate. For targeted edits
   inside large files use `obsidian eval` with `app.vault.modify` for a
   read-modify-write, wrapped in an async IIFE (`(async()=>{...})()`; top-level
   `await` fails).

6. **Chunk content over ~30 KB**: `create overwrite` with the first chunk, then
   `append` the remainder.

Files under `.claude/` are outside the Obsidian tree — use the ordinary
Write/Edit tools there, not this CLI.

## Command reference

Run `obsidian help` to see all available commands. This is always up to date. Full docs: https://help.obsidian.md/cli

## Syntax

**Parameters** take a value with `=`. Quote values with spaces:

```bash
obsidian create name="My Note" content="Hello world"
```

**Flags** are boolean switches with no value:

```bash
obsidian create name="My Note" silent overwrite
```

For multiline content use `\n` for newline and `\t` for tab.

## File targeting

Many commands accept `file` or `path` to target a file. Without either, the active file is used.

- `file=<name>` — resolves like a wikilink (name only, no path or extension needed)
- `path=<path>` — exact path from vault root, e.g. `folder/note.md`

## Vault targeting

Commands target the most recently focused vault by default. Use `vault=<name>` as the first parameter to target a specific vault:

```bash
obsidian vault="My Vault" search query="test"
```

## Common patterns

```bash
obsidian read file="My Note"
obsidian create name="New Note" content="# Hello" template="Template" silent
obsidian append file="My Note" content="New line"
obsidian search query="search term" limit=10
obsidian daily:read
obsidian daily:append content="- [ ] New task"
obsidian property:set name="status" value="done" file="My Note"
obsidian tasks daily todo
obsidian tags sort=count counts
obsidian backlinks file="My Note"
```

Use `--copy` on any command to copy output to clipboard. Use `silent` to prevent files from opening. Use `total` on list commands to get a count.

## Plugin development

### Develop/test cycle

After making code changes to a plugin or theme, follow this workflow:

1. **Reload** the plugin to pick up changes:
   ```bash
   obsidian plugin:reload id=my-plugin
   ```
2. **Check for errors** — if errors appear, fix and repeat from step 1:
   ```bash
   obsidian dev:errors
   ```
3. **Verify visually** with a screenshot or DOM inspection:
   ```bash
   obsidian dev:screenshot path=screenshot.png
   obsidian dev:dom selector=".workspace-leaf" text
   ```
4. **Check console output** for warnings or unexpected logs:
   ```bash
   obsidian dev:console level=error
   ```

### Additional developer commands

Run JavaScript in the app context:

```bash
obsidian eval code="app.vault.getFiles().length"
```

Inspect CSS values:

```bash
obsidian dev:css selector=".workspace-leaf" prop=background-color
```

Toggle mobile emulation:

```bash
obsidian dev:mobile on
```

Run `obsidian help` to see additional developer commands including CDP and debugger controls.
