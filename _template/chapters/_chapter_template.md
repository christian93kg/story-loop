---
type: chapter
tags:
  - chapter
chapter_number: "{{XX}}"
chapter_title: "{{TITLE}}"
adventure_name: "{{ADVENTURE_NAME}}"
status: "{{active|complete}}"
last_updated: "{{DATE}}"
---

<!-- plan:start  GM-ONLY. Never quoted, paraphrased, summarised or hinted at in chat.
     Written and updated by `beat.py open-chapter` / `close` / `rescope` — do not hand-edit.
chapter: {{N}}
title: {{TITLE}}
budget: {{6}}
clock: {{a named in-fiction deadline with a real consequence for missing it}}
turns:
  T1 | {{the fact this turn changes}} | status: open | earliest: 1 | latest: 2
  T2 | {{...}} | status: open | earliest: 2 | latest: 4
close: land the last open turn, then time-skip out. Do not ask the player.
forbidden:
rescope:
plan:end -->

# Chapter {{XX}} — {{TITLE}}

> **This file is the manuscript.** It holds the **verbatim prose** of each beat — the exact text shown
> to the player — not a summary of it, and it is the story's consistency anchor: the last beats land in
> every narrator brief automatically. Landed by `beat.py append` only (play hygiene, vault `CLAUDE.md`) —
> never write this file by hand. Keep state/threads in `game_state.md`, canon in the bible/world/character
> files — not here. A short recap goes at the bottom only when the chapter closes.

---

### Beat {{N}} — {{short label}} ({{DATE}})
<!-- beat: type={{bridge|scene|setpiece|close}} obligation="{{the fact that changed}}" onstage={{a,b}} -->

**Player input:** {{the choice number the player picked, or their free-typed action, that opened this beat}}

{{THE VERBATIM PROSE OF THE BEAT GOES HERE — the actual delivered text, in full. This is the story.}}

**Choices offered:**
1. {{...}}
2. {{...}}
3. {{...}}
4. {{free-type}}

---

<!-- Repeat the Beat block above for each response. -->

---

## Chapter recap (fill in at chapter close only)

> One short paragraph: what changed this chapter (state, relationships, threads opened/closed). For
> continuity scanning — the prose above is the source of truth.

- {{...}}
