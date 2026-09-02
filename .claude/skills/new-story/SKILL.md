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

   No open-ended epics. Settle the four **Beat Sizes** ceilings and the **Beats per
   Chapter** budget here; that line is this story's only home for both. There is no
   minimum length.

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

6. **Seed `game_state.md`** with a `## Resume` block. Keep it to the `**Position:**`
   line (the one the Stop meter reads and blocks on), `**Clock:**` and `**Plan:**`
   (for your own cold-start read), plus the four bullets; craft retrospectives
   belong in `_craft_log.md`, never here.

7. **Read `_craft_research/cards/openings-and-cold-open-craft.card.md`** — this is
   what "right" sounds like for an opening beat.

7a. **Plan Chapter 1**: `beat.py open-chapter --n 1 --title "…" --budget … --clock
   "…" --turns "<fact T1 changes>;<fact T2 changes>"`. It refuses without a clock;
   that is deliberate. `--turns` is the only way to write the plan's 2–3 turns — the
   chapter's non-negotiable content; omit it and the chapter opens with a single
   placeholder obligation instead. **Never show the plan to the player.**

7b. **Confirm `<story>/_craft_log.md` came across from the template** with its
   `## Standing watchlist` (the eight known mutations, pre-seeded) and an empty
   `## Log` — `game_state.md` points at this file as if it exists, and step 1's copy
   already brought it; this is a check, not a create.

8. **Begin play.** The prologue is the first beat and runs through the beat loop
   (`CLAUDE.md § The beat loop`) like every beat after it — the GM never writes it
   directly.

## Check before the first beat

- `python3 .claude/hooks/beat.py --selftest && python3 .claude/hooks/prose-lint.py --selftest && sh .claude/hooks/craft-gate.sh | wc -c`
  — both selftests pass, and the gate's byte count confirms the new story's digests
  are injected with no `CRAFT GATE WARNING` line.
- Exactly one `status: active` across the vault.
