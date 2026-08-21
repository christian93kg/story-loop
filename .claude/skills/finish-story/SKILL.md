---
name: finish-story
description: Take a story through its final act and close it out — add the endings craft mode to the House Register, concatenate the chapter logs into a reading copy, optionally export with Pandoc, and free the active slot. Use when a story is entering its last chapters, reaching its ending, or being finished, completed, shelved, or archived.
---

# Finishing a story

## Entering the final act

Add `endings-and-final-chapter-craft` to the story's `## House Register` in
`master_index.md` (the standing list, not the As-needed block). The hook picks it
up on the next prompt — verified to fit alongside a five-mode register. Remove it
once the reading copy is filed.

## At the ending

One terminal deliverable: a **reading copy**. Concatenate the chapter logs in
order into `<story>/_reading_copy.md` via the `obsidian` CLI — a clean,
front-to-back read of the finished text, kept separate from the working files.
That is the whole requirement.

Chapter logs run ~20-24 KB each, so a finished story exceeds the ~30 KB
single-call limit: `create overwrite` with the first chapter, then `append` the
rest in order.

Optional, only if the player asks for a shareable artifact:

```bash
pandoc _reading_copy.md -o story.pdf     # or -o story.epub
```

Markdown stays the source of truth. Formatting is a last, optional step — no
plugin install is required or implied.

## Free the active slot (rule 4)

1. Take the story's `status:` off `active` — `complete` when finished,
   `shelved` when set aside, `archived` once moved under `_archive/`.
2. Repoint `ACTIVE_GAME.md`'s `active_path:` line, and note the story there as
   complete with its final position.
3. If the folder moves to `_archive/`, make sure no stale `status: active`
   remains in `master_index.md`, `STORY_BIBLE.md`, or `game_state.md` — rule 4
   should be true on disk, checkable with a grep, not just by convention.

## Shelving instead of finishing

Rule 5: ending or shelving a story cleanly is always allowed and is never a
failure. A story ground out past the point of fun is the failure. Shelving is
reversible — record in `ACTIVE_GAME.md` what it would take to revive it.
