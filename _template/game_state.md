---
type: game_state
tags:
  - system
  - state
adventure_name: "{{ADVENTURE_NAME}}"
current_chapter: 0
status: setup
last_updated: "{{DATE}}"
---

# Game State — {{ADVENTURE_NAME}}

## Resume — read this first on a cold start

> Rewritten every response (CLAUDE.md play hygiene). A `/clear`-ed or brand-new session must be able to read THIS block alone and continue exactly where we left off.
>
> **Keep it lean** — the three lines below (Position/Clock/Plan) are rewritten BY YOU
> at runbook step 9 (`CLAUDE.md § The beat loop`), not by beat.py; only
> `**Position:**` is machine-read — the Stop meter blocks the turn until it matches
> the beat just shipped. `**Clock:**` and `**Plan:**` are for your own cold-start
> read. The four bullets after them stay a few lines each. This block is a pointer
> to the live moment, not a canon store. Canon lives
> in `STORY_BIBLE.md`, `world/`, and the character files; the prose lives in the chapter
> files; craft retrospectives live in `_craft_log.md`. If the Resume block is swelling
> into a dump of rules, lore, or every thread's history, that is drift — trim it back.

- **Position:** ch {{N}} · beat {{M}} · budget {{B}} · type {{scene}}
- **Clock:** {{the live in-fiction deadline, one clause}}
- **Plan:** {{T1 delivered · T2 open}}
- **Where we are:** {{chapter / scene / location}}
- **Last beat (recap):** {{one paragraph — what just happened}}
- **Open choice / next action:** {{the pivot the player is mid-decision on, or what happens next}}
- **Body / inventory / live threads at a glance:** {{quick state}}

## Setup Decisions

| Setting              | Value |
| -------------------- | ----- |
| Genre                |       |
| Tone                 |       |
| Stakes               |       |
| Death/Failure Rules  |       |
| POV                  |       |
| Prose Density        |       |
| Beat Sizes           | bridge ≤900 · scene ≤2,400 · setpiece ≤3,200 · close ≤2,600 chars — ceilings, no floor |
| Style References     |       |
| Combat Style         |       |
| Pacing (per chapter) |       |

## Current Position

- **Chapter**: —
- **Chapter Title**: —
- **Scene/Location**: —
- **Last Major Decision**: —

## Unresolved Threads

> Active plot threads the story needs to address. Remove when resolved.

- 

## Craft log

Per-beat craft self-audits, catches, and rewrite postmortems live in `_craft_log.md`,
not here — they are a retrospective, not state, and are not part of the canon-read.
Append there after shipping a beat. This file stays lean enough to cold-read.
