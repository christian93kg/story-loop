---
name: new-story
description: Scaffold a new interactive-fiction story — copy the template, fill master_index.md with the central tension / ending / target length, write the one-page STORY_BIBLE, set the House Register, and repoint ACTIVE_GAME.md. Use when starting, launching, or setting up a new story or adventure, or when the player wants to begin a new game.
---

# New-story setup

Rule 4 first: exactly one story may carry `status: active`. If another story is
live, finish or shelve it before starting here — shelving (`status: shelved`) is
reversible and destroys nothing.

## Sequence

1. **Copy `_template/` into a new story folder.** Name it `<slug>_01`. The copy
   brings a `scratchpad/` with it — that is where beats get drafted and linted
   before they reach a chapter log; leave it in place. Then confirm the copy has
   no links pointing back at the template: `grep -rn '_template/' <story>/`
   should return nothing.

2. **Fill `master_index.md` with the player.** Rule 2 says a story names three
   things before Chapter 1, and all three go in this file:
   - **central tension** — what the story is actually about
   - **the ending** — if you cannot say how it ends, it is not scoped yet
   - **target length** — chapters × beats, a number the story can realistically reach

   No open-ended epics. Also settle per-beat prose length here; that number is
   this story's only home for it, and nothing outside the folder should restate it.

3. **Write a one-page `STORY_BIBLE.md`** from the template skeleton. The skeleton
   is the cap, not a starting point to expand from (rule 3). Up to five forbidden
   patterns, each falsifiable. Write it against `_craft_research/CRAFT_SPINE.md`.

4. **Set the `## House Register`** in `master_index.md`. The craft-gate hook parses
   that heading every prompt and injects each listed mode's digest, so the format
   matters: bare backticked slugs, one per line, 3-5 standing modes. Keep the two
   universal-floor modes the template pre-seeds. Valid slugs are listed in the
   block itself; anything else is silently unmatched. Modes needed only
   occasionally go under the "As-needed" heading, which the hook deliberately
   stops at.

5. **Point `ACTIVE_GAME.md`** (vault root) at the new folder via its `active_path:`
   line, and note the previous story's disposition there. The hook follows
   `active_path` automatically — nothing else needs regenerating on a switch.

6. **Seed `game_state.md`** with a `## Resume` block. Keep it to the four bullets;
   craft retrospectives belong in `_craft_log.md`, never here.

7. **Read `_craft_research/cards/openings-and-cold-open-craft.card.md`**, then write
   the prologue and begin Chapter 1.

## Check before the first beat

- `sh .claude/hooks/craft-gate.sh | wc -c` — confirm the new story's digests are
  injected and no `CRAFT GATE WARNING` line appears.
- Exactly one `status: active` across the vault.
