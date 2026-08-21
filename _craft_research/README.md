# Craft Research — a reference shelf

Deep-research reports on the genres played here and on the interactive turn-loop itself.
**Research is complete:** fifteen reports are filed in `reports/`, one per mode. This is a
reference shelf, not a rule layer — the craft *floor* lives in the root `CLAUDE.md` five
rules and each story's one-page `STORY_BIBLE.md`.

The filed reports and what each covers: **[[index]]**. This file is the how-to.

## How to use it

- **The one-page distillation:** [[CRAFT_SPINE]] is the always-on cheat-sheet (the best of
  all fifteen reports) — eight through-lines, four ship tests, and the mode map. The
  craft-gate hook (`.claude/hooks/craft-gate.sh`) injects it every prompt, plus the active
  story's standing-register digests (the `<!-- digest:start/end -->` block at the end of
  each card in `cards/`). Its **`## Mode map`** section is the routing table: which mode am
  I in, which card do I read.

- **During play:** the injected spine + digests cover the standing register. A beat in any
  other mode (combat, intimacy, dread, institutional menace, dialect, choice design): Read
  that mode's card in `cards/`; a major set-piece: Read the full report — lazy, targeted
  reading, never a mandatory per-turn step.

- **The reports:** each follows the same shape — TL;DR, Key Findings, Details,
  Recommendations, Caveats, and a **Falsifiable techniques** section (before/after
  micro-examples + pass/fail checklist lines). The checklist lines are the payoff: testable
  against a draft beat.

- **A story's own best beats** are the highest-fidelity reference of all: each story keeps
  up to five in its `_exemplars.md`, read as part of the canon-read.

## Growing the shelf

- `prompts/_genre-comp-template.md` — fill the slots (or ask Claude) to research a new
  genre, then file the report in `reports/`, add the card in `cards/` (with a digest
  block), and add a row to [[index]].
- `reports/_report_template.md` — the filing skeleton, including the header block every
  report carries and the quotation rules below.
- `prompts/` holds that template plus the five prompts kept verbatim
  (dialogue-subtext, endings, foreshadowing, humor-in-dark-frames, openings). The other ten
  were folded into their reports; ask Claude to reconstruct one from its report if you want
  to re-run the topic.

## Why falsifiable

A report you can't test against a draft passage drifts into generic advice, useless at the
keyboard. Every report ends in pass/fail checklist lines for exactly that reason.

## On quotation

These reports quote published fiction, craft books, and interviews to show technique. The
rules they are held to, and that any new report must follow:

- Short excerpts only, always attributed, always with analysis attached — the quote exists
  to demonstrate a mechanism, never to stand in for the work.
- **No work's complete closing paragraph.** A novel's ending is the part most damaged by
  being handed over; where an ending is analyzed, only the sentence carrying the device is
  quoted.
- Nothing sourced from an unauthorized full text. If a passage can't be sourced
  legitimately, paraphrase the technique and say so.
- Screen dialogue is quoted as performance-adjacent craft, not prose to transcribe — see
  the caveats in `reports/grounded-sf-and-noir-menace.md`.

If you think a specific excerpt overreaches, open an issue and it will be trimmed.
