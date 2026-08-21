# Claude working rules — story-loop

This vault holds interactive-fiction stories. Each story lives in its own folder,
scaffolded from `_template/`. These are the **vault-level** rules; story-specific
rules live inside that story's folder, never here.

---

## The five rules

These exist because stories kept stalling in the middle, accumulating enforcement
machinery, and never getting finished. They override any cozier defaults a story
inherits.

1. **Propulsion over texture.** Every beat advances the central tension; whatever
   the player is waiting for is never more than ~2 beats away. Time-skip the
   connective tissue — not every day, meal, or corridor gets rendered. Every choice
   menu includes at least one option that advances the core conflict, never four
   variations on standing still.
2. **Scope to finish.** Before Chapter 1 a story names three things in
   `master_index.md`: its **central tension**, its **ending**, and a **target
   length** it can realistically reach. If you cannot say how it ends, it is not
   scoped yet. No open-ended epics.
3. **Keep the machinery light.** A story's rules live in one ~one-page
   `STORY_BIBLE.md`. When prose drifts, the fix is to write better or to reset —
   never to bolt on another enforcement layer. A stack of rule-sections is the
   symptom of an over-managed, un-fun story. Build canon lazily: write only the
   canon the next beat actually needs.
4. **One story at a time.** Exactly one story carries `status: active`. Finish or
   shelve the active story before starting another; shelving is reversible and
   destroys nothing.
5. **Fun is the metric.** If the player says it is forced, boring, or that they are
   not excited — stop immediately, surface it, do not write forward. Ending or
   shelving a story cleanly is always allowed and is never a failure. A story
   ground out past the point of fun is the failure.

---

## Play hygiene

- **Canon-read before in-fiction prose.** At the start of any turn that will write
  a beat: identify the live story from `ACTIVE_GAME.md`, then read that story's
  `STORY_BIBLE.md`, `game_state.md` (its `## Resume` block first, so a `/clear`-ed
  session can pick up cold), `_exemplars.md`, and the current chapter log. Read a
  character file before writing that character's dialogue. The vault is
  authoritative; if working memory and the vault disagree, the vault wins.

- **Craft canon is hook-injected — write against it.** `.claude/hooks/craft-gate.sh`
  injects `_craft_research/CRAFT_SPINE.md` plus the active story's House Register
  digests every prompt, resolved live from `ACTIVE_GAME.md` (story switches need no
  regeneration). Run every beat against the through-lines, the ship tests, and each
  injected digest — already in context, no Read needed. Escalate only when a beat
  outruns them: a mode with no digest injected → Read its card in
  `_craft_research/cards/`; a major set-piece → Read the full
  `_craft_research/reports/` file. If the injection shows a `CRAFT GATE WARNING`
  line, do what it says before writing prose. The hook's size budget lives in the
  script header and is the single source of truth — do not restate the number here
  or anywhere else. Draft each beat to `<story>/scratchpad/ch<N>_beat<M>_draft.md` first
  — the directory ships with the template, and the `_draft.md` suffix is what fires the
  lint:
  `prose-lint.py` fires automatically on that write and blocks on `FAIL`, then run
  the `second-reader` agent on `prose-lint.py --brief <draft>` before the prose
  reaches the chat or the vault. Thresholds and rules live in the script, never here.

- **Cross-link canon as you build it.** When a canon file names another canonical
  entity — a character, faction, place, twist — link it with `[[wikilinks]]`. Links,
  not folders, are how canon is navigated here: they light up backlinks and the
  graph, so the canon-read above is a click, not a search. A `[[link]]` whose file
  does not exist yet marks a thread worth writing later. Link only what the beat
  actually references.

- **Surface conflicts before writing.** If a prompt would break canon, name the
  conflict and propose a fix *before* composing prose. Never silently "fix" drift by
  writing through it. Log the retcon in the story's `_craft_log.md` (date, what broke,
  what canon was, how it was repaired) — the same file craft retrospectives go in.

- **Save every response — resume-safe.** End every response containing story prose
  by writing to the vault: append the verbatim beat to the chapter log, and update
  `game_state.md` so its **`## Resume`** block reflects the live moment — current
  position, a one-paragraph recap of the latest beat, and the open choice or next
  action. Update character / twist / outline files when they develop. Session-level
  craft retrospectives go in the story's `_craft_log.md` — create it the first time you
  need it — never in `game_state.md`.
  **The test:** if the session were `/clear`-ed right now, a cold read of
  `game_state.md` alone must be enough to pick up exactly where we left off. Ending
  a story response without this save is the one bug this rule exists to prevent.

---

## Vault file operations

If you play through [Obsidian](https://obsidian.md), route vault writes through the
`obsidian` CLI rather than raw file edits — see the `obsidian-cli` skill for the
command reference and its gotchas (a missing `XDG_RUNTIME_DIR`, `vault=` placement,
`\n` encoding in `content=`, no in-place edit command). Files under `.claude/` are
outside the Obsidian tree — use ordinary file edits there regardless.

If you're playing from plain Markdown files with no Obsidian instance running, skip
that skill and just edit the files directly; nothing else in this kit depends on
Obsidian being open.

## Skills

- **`new-story`** — scaffolding a story from `_template/` and opening the active slot
- **`finish-story`** — final act, reading copy, freeing the active slot
- **`obsidian-cli`** — full CLI reference and the failure modes behind the Obsidian
  gotchas above (only needed if you're running Obsidian)
