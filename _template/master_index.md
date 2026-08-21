---
type: master_index
tags:
  - system
  - rules
adventure_name: "{{ADVENTURE_NAME}}"
status: setup
date_created: "{{DATE}}"
---

# {{ADVENTURE_NAME}} — Master Index

> The vault-level five rules (vault-root `CLAUDE.md`) govern every story. This file records this story's setup decisions.

## Setup Decisions

> Filled collaboratively before the story begins. Do not skip any step.

### 1. Genre & Tone
- **Genre**: {{e.g., dark fantasy, sci-fi, slice of life, horror, historical}}
- **Tone**: {{e.g., gritty, whimsical, melancholic, comedic, tense}}
- **Stakes**: {{e.g., life-and-death, personal growth, political intrigue, survival}}
- **Death/Failure Rules**: {{e.g., permadeath, checkpoint, narrative consequences only, no death possible}}

### 2. Narrative Style
- **POV**: {{first person, second person, third person}}
- **Prose Density**: {{lean/punchy, moderate, rich/literary}}
- **Response Length**: ~3,000 chars (~580 words) per beat — one readable sitting. {{The kit default; change the number if this story wants longer or shorter beats. `prose-lint.py` reads this line, so keep the `~N chars` shape.}}
- **Style References**: {{novels, fanfics, authors, or specific works to emulate}}
- **Dialogue Style**: {{naturalistic, stylized, dialect-heavy, minimal}}

### 3. Setting
- **Type**: {{original | IP-based}}
- **Setting Summary**: {{brief description — filled after world-building phase}}
- **World Docs**: {{yes/no — link to world/ folder if yes}}

### 4. Character
- **Player Character**: [[player_character]]
- **Name Generation**: {{player picks | Claude generates | collaborative}}
- **Character Sheet Style**: {{narrative tags, simplified stats, detailed}}

### 5. Combat
- **Style**: {{narrative only, mechanical, hybrid, none}}
- **Detail Level**: {{brief, moderate, detailed multi-response}}
- **Player Interaction in Combat**: {{choices each turn, freeform, mixed}}

### 6. Scope & Pacing

> Vault rule 2 — **scope to finish**. Do not begin Chapter 1 until the central tension, the ending, and a target length are all named.

- **Central Tension**: {{the one conflict the whole story turns on — what the player is always, ultimately, waiting to resolve}}
- **How It Ends**: {{the finish this story is written toward — the shape of the ending, set before Chapter 1}}
- **Target Length**: {{realistic chapter count to reach that ending — e.g. 8-12 chapters. Not "until it concludes."}}
- **Interactions per Chapter**: {{approximate number, default ~5}}
- **Ending Structure**: {{one canonical ending | multiple endings}}

---

## House Register

> **Standing register.** The craft-gate hook parses this section every prompt and injects each listed mode's digest. Bare backticked slugs only, one per line — 3-5 standing modes, chosen for the story's genre at setup. The first two are the universal floor; keep them. The hook stops reading at the second list below, so only the bullets in this list are injected — valid slugs and the size budget are documented there.
- `event-density-and-interiority-economy`
- `second-person-turn-loop-craft`

> **As-needed** — everything from this line down is ignored by the hook. Read the ~3 KB card when a beat hits the mode; the full report in `_craft_research/reports/` for a major set-piece:
- {{as-needed modes for this story, e.g. `romance-and-intimacy`, `genre-cosmic-horror`}}
- Final act: add `endings-and-final-chapter-craft` to the standing list above when the ending arc begins; remove after the reading copy is filed. See the `finish-story` skill.

<!-- Valid slugs — card filenames in _craft_research/cards/, minus .card.md.
     Anything not on this list is silently unmatched by the hook and injects nothing.

       accent-via-syntax                       grounded-sf-and-noir-menace
       clinical-dark-academia-restraint        humor-in-dark-frames
       dialogue-subtext-and-negotiation        openings-and-cold-open-craft
       endings-and-final-chapter-craft         physical-and-combat-choreography
       event-density-and-interiority-economy   romance-and-intimacy
       foreshadowing-and-payoff                second-person-turn-loop-craft
       genre-cosmic-horror                     voice-and-dialect
       grit-and-momentum-cadence

     status: setup | active | shelved | complete | archived  (exactly one story is active — rule 4)

     Budget: the ceiling lives in .claude/hooks/craft-gate.sh and is the single source of
     truth. A six-mode standing register fits. After editing this list, check:
         sh .claude/hooks/craft-gate.sh | wc -c      # expect no CRAFT GATE WARNING line
-->

---

## Interaction Rules

### Choices
- At the end of each response, present **1-4 numbered choices** for the player to select from.
- The player may also type their own action instead of choosing from the list.
- During **major events** (emotional climaxes, critical turning points, ambushes), present **no choices** — require the player to type their raw reaction.

### Pacing & Propulsion
- Every beat advances the central tension; whatever the player is waiting for is never more than ~2 beats away (vault rule 1). Time-skip the connective tissue.
- Every choice menu includes at least one option that advances the core conflict — never four variations on standing still.
- This story's rules live in one file: `STORY_BIBLE.md`, kept to about a page (vault rule 3). If prose drifts, write better or reset — never bolt on another rules layer.

### Immersion — Non-Negotiable
- Never break character or acknowledge being an AI during gameplay.
- Never contradict established facts from character sheets, chapter summaries, or world docs.
- **Read markdown files live** during play to verify continuity before writing responses.
- If a character is dead, they stay dead. If a character is alive, they exist. No exceptions.
- If the player attempts an action wildly inconsistent with their established character, gently redirect through narrative (the character hesitates, feels wrong about it) rather than breaking immersion.
- **Dialogue must sound like real people of their age and station.** Nobody speaks in polished literary prose. People stumble, trail off, use filler words, say dumb things, and occasionally land something sharp. Not everyone is witty. Not every line is clever. Authenticity over style — see `_craft_research/cards/dialogue-subtext-and-negotiation.card.md`.

### File Management During Play
- **`game_state.md`**: Update the `## Resume` block at the end of **every response** (play hygiene). Keep it lean — a pointer to the live moment, not a canon dump.
- **`chapters/chapter_XX.md`**: Append the **verbatim prose** of each beat **every response** — this file is the manuscript and the story's consistency anchor, not a summary log. A short recap goes in only at chapter close.
- **`characters/`**: Create NPC files when significant new characters are introduced. Update existing sheets when characters develop or reveal new information.
- **`plot_twists.md`**: Append entries when organic twists emerge. Log foreshadowing as it's planted.
- **`story_outline.md`**: Update as the story evolves and new arcs form.

---

## Pre-Game Setup Sequence

1. Greet the player and ask about **genre, tone, stakes, and death/failure rules**.
2. Determine **narrative style** — POV, prose density, response length, style references.
3. **Setting**: If IP-based, begin collaborative world-building (expect 3-5 messages). If original, present a brief premise and drop in.
4. **Character creation**: Ask the player questions about who they want to be. Build the sheet from their answers. Generate a name (unless player wants to choose).
5. Determine **combat style**, and **scope**: name the central tension, the ending, and a target length (vault rule 2 — do not begin Chapter 1 without an ending named).
6. Fill in all fields in this master_index — including the **House Register** (standing craft modes for this genre). Write the one-page `STORY_BIBLE.md` from the template skeleton.
7. Confirm no other story carries `status: active` (vault rule 4).
8. Write the **prologue** and begin Chapter 1.