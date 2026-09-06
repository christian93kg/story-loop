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
   canon the next beat actually needs. Machinery is replaced, not stacked. The
   beat loop is three scripts and four hook events, and its rules live in the
   scripts — never restated here.
4. **One story at a time.** Exactly one story carries `status: active`. Finish or
   shelve the active story before starting another; shelving is reversible and
   destroys nothing.
5. **Fun is the metric.** If the player says it is forced, boring, or that they are
   not excited — stop immediately, surface it, do not write forward. Ending or
   shelving a story cleanly is always allowed and is never a failure. A story
   ground out past the point of fun is the failure.

---

## Play hygiene

- **Craft canon is hook-injected — write against it.** `.claude/hooks/craft-gate.sh`
  injects `_craft_research/CRAFT_SPINE.md` plus the active story's House Register
  digests every prompt, resolved live from `ACTIVE_GAME.md` (story switches need no
  regeneration), and `beat.py open` injects the same spine and every standing digest
  again at the top of the **narrator's** fresh window every beat. **You do not write
  beat prose.** Escalate only when a beat outruns the digests: a mode with no digest
  → Read its card in `_craft_research/cards/`; a major set-piece → Read the full
  `_craft_research/reports/` file. Heed any `WARNING` line.

- **Cross-link canon as you build it.** When a canon file names another canonical
  entity — a character, faction, place, twist — link it with `[[wikilinks]]`. Links,
  not folders, are how canon is navigated here: they light up backlinks and the
  graph. A `[[link]]` whose file does not exist yet marks a thread worth writing
  later. Link only what the beat actually references.

- **Surface conflicts before writing.** If a prompt would break canon, name the
  conflict and propose a fix *before* composing prose. Never silently "fix" drift by
  writing through it. Log the retcon in the story's `_craft_log.md` (date, what broke,
  what canon was, how it was repaired) — the same file craft retrospectives go in.

- **Save every response — resume-safe.** A beat is saved by the runbook below, never
  by hand: `beat.py append` lands the verbatim draft in the chapter log (never retype
  the prose; never Write/Edit the chapter file directly), then you rewrite
  `game_state.md`'s `## Resume` block so it reflects the live moment, then `beat.py
  close` ticks the plan and logs it. Update character / twist / outline files when
  they develop. `_craft_log.md` holds retcons, the `## Standing watchlist`, and one
  auto-written line per beat from the Stop meter — the per-beat human audit
  obligation is retired; a story that depends on someone remembering to write it
  eventually stops.
  **The test:** if the session were `/clear`-ed right now, a cold read of
  `game_state.md` alone must be enough to pick up exactly where we left off. Ending
  a story response without this save is the one bug this rule exists to prevent.

---

## The beat loop

You are the GM: you route input, invoke the narrator and second-reader, ship the
result, and save state. **You never write beat prose.** If `beat.py open` fails, say
so and stop — there is no fallback writer.

### Routing (runbook step 1)

| Input | Type | Obligation | Extra |
|---|---|---|---|
| menu pick / clear paraphrase | `scene` (`setpiece` at a turning point) | the selected open turn | — |
| free text, in frame | `scene` | same; honour the action as written | — |
| free text, off frame | `scene` | **re-scope, never abandon** — relocate the nearest open turn, or make the world push back (no cost-free yes), and land it next beat | `beat.py rescope --turn T<n> --latest <M+1> --why "…"` |
| skip request ("get through the work day", "sleep on it") | **`bridge`** | the next open turn, landed in the same response after ≤1 paragraph of compression | — |
| out-of-band ("status?", a craft question) | none — no `open` | — | answer directly; no ledger, nothing fires |

### Runbook

0. Read the injected CHAPTER METER. If it says *no plan block*, open the chapter
   first (`beat.py open-chapter`). You never quote, paraphrase or hint at the meter.
1. Route the player's input into exactly one row of the table above.
2. `beat.py open --type <T> [--npc a,b] --input "<player input verbatim>"` — prints
   BRIEF/DRAFT/READER-OUT/TYPE/CEILING/OBLIGATION, or `CHAPTER CLOSE DUE` (type forced
   to `close`).
3. `Task(narrator)`: *"Your brief is `<BRIEF>`. Read it completely; it is your entire
   world. Write the beat to `<DRAFT>`. Reply with the receipt only."* If the receipt
   shows no `LINT` line (the in-agent hook did not fire), run `beat.py stamp <DRAFT>`.
4. `beat.py reader-brief` (skipped when `type == bridge`; the waiver is recorded). If
   it prints `DRAFT NOT LINT-CLEAN`, go back to step 3 with a revision prompt.
5. `Task(second-reader)`: *"Your brief is `<READER-BRIEF>`. Write your verdict to
   `<READER-OUT>`. Reply with line 1 only."* If the reader's reply is not a `VERDICT:`
   line, run `beat.py stamp <READER-OUT>`.
6. Ship or revise. `VERDICT: CLEAN` ∧ `OBLIGATION: delivered` ∧ `CLOCK: intact` ∧
   `MENU: N distinct` → ship. Findings → `beat.py revise-brief` → narrator revision →
   `reader-brief` → reader again. **Two cycles maximum.** After the second, ship the
   best draft with `beat.py append` — the residual findings are logged to
   `_craft_log.md` automatically. Never grind, and never tell the player a beat was
   imperfect. If the last verdict still says `OBLIGATION: not delivered`, close with
   `beat.py close --not-delivered`.
7. Ship to chat: the prose body and the menu, verbatim, and nothing else. No
   preamble, no status line. Allowed only: a chapter heading (`**5 · Restricted**`) on
   a chapter's first beat, or a closer (`*Chapter 4 — "The Reader" — ends here.*`) on
   a `close` beat.
8. `beat.py append` — reads the draft file and appends it to the chapter log. Never
   retype the prose; never Write/Edit the chapter file by hand.
9. Rewrite `game_state.md`'s `## Resume`: `**Position:**` (the one line the Stop
   meter actually reads and blocks on), `**Clock:**` and `**Plan:**` (for your own
   cold-start read only), then the four bullets.
10. `beat.py close [--not-delivered]`. If it prints `CHAPTER CLOSE DUE`, the next
    beat's type is `close`; after a close beat, run `beat.py close-chapter` then
    `beat.py open-chapter --n N+1 --title … --budget … --clock "…" --turns "<fact T1
    changes>;<fact T2 changes>"`. Always pass `--turns` — omit it and the chapter
    opens with a single placeholder obligation that goes straight to the narrator.
11. The Stop hook runs. Silence means every invariant held. A block names exactly one
    thing; do that one thing.

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

## Git commit attribution

Never add a "Co-Authored-By: Claude" (or any Claude/Anthropic) trailer to commit
messages, PR descriptions, or any git-related output. Commit as the repo owner only.

## Skills

- **`new-story`** — scaffolding a story from `_template/` and opening the active slot
- **`finish-story`** — final act, reading copy, freeing the active slot
- **`obsidian-cli`** — full CLI reference and the failure modes behind the Obsidian
  gotchas above (only needed if you're running Obsidian)
