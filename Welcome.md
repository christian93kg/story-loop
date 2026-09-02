---
type: vault_index
tags:
  - system
---

# story-loop

> Interactive fiction played through Claude Code, backed by this Obsidian vault.

## How to Start

1. Tell Claude: "Let's start an adventure."
2. Claude reads the vault-root **`CLAUDE.md`** (the five rules) and invokes the **`new-story`** skill, which copies `_template/` into a new story folder.
3. Collaborate on setup — including the three things rule 2 requires before Chapter 1: the **central tension**, the **ending**, and a **target length**.
4. Play.

The five rules (full text in `CLAUDE.md`): **1.** Propulsion over texture · **2.** Scope to finish · **3.** Keep the machinery light · **4.** One story at a time · **5.** Fun is the metric.

## Adventures

> **[[ACTIVE_GAME]] names the live story** — check there, not here; this file does not track state
> and will go stale if it tries. One story may be `active` at a time (rule 4). Past playthroughs are
> preserved, not deleted: shelve or finish them and they move to `_archive/`, revivable at any time.

- [[ACTIVE_GAME]] — **the live story, and the roster of shelved and archived ones**
- [[_template/master_index|Template Reference]] — the scaffold for a new story
- `_archive/` — retired and shelved stories accumulate here as you play (reference only, not part of this kit)

## Template Structure

```
_template/
├── master_index.md      setup decisions — incl. central tension, ending, target length,
│                          Beat Sizes ceilings, Beats per Chapter budget, Chapter Clock
├── STORY_BIBLE.md        the one-page north star (rule 3 — keep it to a page)
├── game_state.md         live save state (Position/Clock/Plan + four bullets)
├── story_outline.md      arc skeleton + the ending
├── plot_twists.md        twist & foreshadowing tracker
├── _exemplars.md         up to five of this story's own best beats — packed into every
│                          narrator brief automatically
├── characters/           player_character.md + _npc_template.md
├── chapters/             _chapter_template.md — carries a GM-only plan block (the chapter's
│                          turns and clock; never shown to the player) under the frontmatter
├── scratchpad/           beats are drafted, linted and read here before beat.py append
│                          lands them in a chapter log — the ledger also lives here
└── world/                canon_notes / factions / setting_overview
```
