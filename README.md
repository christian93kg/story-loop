<div align="center">

<img src="docs/og.svg" alt="story-loop — causality, not chronology. A five-beat chain linked by therefore/but, handed back on an open want at the last beat." width="820">

<h1>story-loop</h1>

<p><b>Interactive fiction that reads like it was actually written, past the last chapter.</b><br>
Built for <a href="https://obsidian.md">Obsidian</a> + <a href="https://www.claude.com/claude-code">Claude Code</a>.<br>
Fifteen craft reports distilled into a standard the prose is held to — the hooks below exist to protect that standard, not to be the point.</p>

[![Read the craft canon](https://img.shields.io/badge/▶_read_the_craft_canon-15_reports-ffa657?style=for-the-badge&labelColor=0d0c0b)](_craft_research/CRAFT_SPINE.md)
[![Use this template](https://img.shields.io/badge/use_this_template-→-a8a49c?style=for-the-badge&labelColor=0d0c0b)](https://github.com/christian93kg/story-loop/generate)

![Obsidian](https://img.shields.io/badge/Obsidian-vault-6e6a63?style=flat-square&labelColor=0d0c0b)
![Claude Code](https://img.shields.io/badge/Claude_Code-skills_+_hooks-6e6a63?style=flat-square&labelColor=0d0c0b)
![Play](https://img.shields.io/badge/play-one_beat_per_response-6e6a63?style=flat-square&labelColor=0d0c0b)
![Setup](https://img.shields.io/badge/setup-~5_min-6e6a63?style=flat-square&labelColor=0d0c0b)
![License](https://img.shields.io/badge/license-MIT-6e6a63?style=flat-square&labelColor=0d0c0b)

</div>

---

## Why this exists

Most LLM-run interactive fiction reads the way you'd expect improvised fiction to read: competent, forgettable, and prone to sliding into slice-of-life filler once the premise runs dry. Feelings get named instead of shown, choices multiply without changing anything, and a story scoped for twelve chapters is still setting up its premise in chapter twenty. None of that is a model capability problem — a model that has read a huge amount of good fiction can write it too. It just needs the actual craft in front of it as a standard to write against, not as advice it read once in a system prompt and quietly drifted past.

So the product here is the writing, in this order:

|  | |
|:--:|---|
| **1** | **The craft.** Fifteen deep-research reports (`_craft_research/index.md`), distilled into one always-on spine (`CRAFT_SPINE.md`) and a mode-specific card shelf — literary technique (withheld emotion, causality over chronology, restraint under pressure) stated as falsifiable rules with before/after examples, not "write tense prose." |
| **2** | **The shape.** Before Chapter 1, a story has to name its ending and a realistic length — the discipline that keeps a story arriving somewhere instead of drifting until it's abandoned. |
| **3** | **What holds the line.** A hook injects the canon before a beat is drafted; a linter checks the draft after; a separate second reader catches what regex can't. None of this writes a word of fiction — it exists so point 1 survives to the last chapter instead of eroding by chapter ten, which is the part a chat window can't give you on its own. |

The proof isn't the mechanism in point 3. It's what that mechanism is protecting — here's the same beat, written once against the standard in point 1 and once without it.

---

## The prose this is built to produce

`CRAFT_SPINE.md` is eight through-lines, not eight suggestions. Same beat, same facts, written once against them and once without — this is the actual difference, not a claim about it:

**Without the spine:**

> You walk into the lab, which is cold and a little unsettling, and you wonder why Voss keeps it that way. The benches are old but well-maintained, with steel fittings that show someone cares about the equipment. You find your bench, which is the third one from the front on the left side, and then you notice that your lab partner has already set everything up for both of you, which is a thoughtful thing to do. You feel grateful and a little surprised that she would bother, and you wonder if you should say something about it.

**Against it** (`.claude/hooks/fixtures/ch3b3_good.md`, the kit's own lint fixture):

> The lab sits four degrees under the corridor and Voss never says why. The steel on the benches is polished. The floor underneath is not. Third from the front, left side, is yours.
>
> It's laid out when you get there. Both halves — scales trued, burner set, your mortar squared to the bench edge at the same distance as hers.
>
> [...]
>
> You look at your half of the bench. "Why?"
>
> "Because it was going to bother me." She doesn't say which part.
>
> [...four exchanges later, the beat hands back on:]
>
> "Are you going?"

Line by line, against the actual spine text:

| Without | Against | Through-line |
|---|---|---|
| "which is cold and a little unsettling" | "The steel on the benches is polished. The floor underneath is not." | **Perception over stated emotion** — report what the body notices, not what it feels |
| "old but well-maintained, with steel fittings that show someone cares" | "Third from the front, left side, is yours." | **One telling particular over catalogue** — a single load-bearing detail beats piled adjectives |
| "which is a thoughtful thing to do" | "She doesn't say which part." | **Narrator stays out** — no authorial scoring; the shown detail forces the conclusion |
| "You feel grateful and a little surprised... you wonder if you should say something" | "Why?" / "Because it was going to bother me." | **Withhold / omission** — cut the named feeling; the reader supplies more force than you can |
| "and then you notice" | bench laid out → "Why?" → withheld answer | **Causality, not chronology** — beats join on therefore/but, never "and then" |
| ends on a trailed-off thought | "Are you going?" | **Hand back on a want-at-risk** — end on the cusp of an outcome still in doubt |

Nothing in the right-hand column is hand-waved. `owner` fields in the linter point back to the same through-lines, and the mode card for this beat (`dialogue-subtext-and-negotiation.card.md`) is what says the unspoken want has to stay unspoken — spine and index agree, because the spine is a distillation of the index, not a separate opinion.

---

## The least interesting part: what's actually enforced

Everything above is the point. This section exists only so that claim is checkable instead of asserted — a linter can't tell you the "against" column reads better than the "without" one; craft judgment isn't a grep target. What it *can* do is catch the tics that keep recurring once you know to look for them. This is the actual tool, run on the exact "without" paragraph above, saved as a draft (with no beat-type header, so the tool also shows you the one thing it always insists on before anything else):

```
$ python3 .claude/hooks/prose-lint.py my_story_01/scratchpad/ch1_beat1_draft.md

!! PROSE LINT WARNING: no <!-- beat: type=... --> header found — defaulting to type=scene
L1 FAIL gloss-clause  You walk into the lab, which is cold and a little unsettling, and…
       [narrator-stays-out / event-density KILL: editorial verdicts]
L1 FAIL gloss-clause  …the equipment. You find your bench, which is the third one from the front on t…
       [narrator-stays-out / event-density KILL: editorial verdicts]
L1 FAIL gloss-clause  …set everything up for both of you, which is a thoughtful thing to do. You fee…
       [narrator-stays-out / event-density KILL: editorial verdicts]
L1 FAIL filter-word  …front on the left side, and then you notice that your lab partner has already…
       [event-density KILL: filter-word openers]
L1 FAIL filter-word  …hich is a thoughtful thing to do. You feel grateful and a little surprised t…
       [event-density KILL: filter-word openers]
   FAIL beat-header  declare the beat type — bridge/scene/setpiece/close — the ceiling depends on it
       [draft output contract: line 1 must be <!-- beat: type=... -->]
```

Six real FAILs, one paragraph — five of them on the prose itself (this is what would have blocked the "without" version from shipping), the sixth because a real draft's first line is machine-checked too. `owner` names the exact through-line each rule mechanizes; nothing above is invented for the README. The linter also stops adding new rules once its list gets long enough to signal the story itself is over-managed, not just the prose (`.claude/hooks/prose-lint.py`, `TRIPWIRE` comment). What it structurally can't catch — over-polished dialogue, a passive protagonist, whether a *clean* draft actually reads well and isn't just spine-shaped — is the `second-reader` agent's job, not the linter's.

One correction, because it's easy to assume otherwise: `beat.py --post` is the `PostToolUse` hook, and it calls `prose-lint.py` as a module (not as its own hook — `prose-lint.py`'s own `--hook` mode is unwired, kept only as a manual/legacy entry point) — the file is already on disk when it runs, so an `exit 2` here doesn't block the write, it returns the report as feedback and the writer complies on the next attempt. What **does** block a write is a separate `PreToolUse` guard on the chapter log itself: it denies appending a beat until the draft is lint-clean *and* the second reader has filed a verdict. Linting is a feedback loop; the guard is the actual lock.

---

## What you get

The craft shelf is the product. Everything else exists to keep it from eroding once a story gets long:

| | |
|---|---|
| **`[canon]`** | **`_craft_research/`** — 15 filed reports (combat, dread, dialogue subtext, dialect-via-syntax, foreshadowing, endings, and more), indexed in `index.md`, each ending in falsifiable before/after checklist lines. `CRAFT_SPINE.md` distills all of them into one always-on cheat-sheet. |
| **`[gates]`** | **Four hooks, three scripts** — `craft-gate.sh` (`UserPromptSubmit`) injects the spine, the active story's standing modes, and the chapter meter every prompt; `beat.py --guard` (`PreToolUse`) denies a chapter-log write until the chain is complete; `beat.py --post` (`PostToolUse`, calling `prose-lint.py` as a module) lints every draft and stamps the ledger; `beat.py --meter` (`Stop`) checks eight invariants from file truth before the turn is allowed to end. |
| **`[beat loop]`** | **`beat.py` + `narrator`** — the GM never writes fiction. It opens a beat (`beat.py open`), hands a self-contained brief to a fresh `narrator` subagent, then a fresh `second-reader`, ships only on a clean verdict, and appends through `beat.py append` — never by retyping prose into the chapter file. |
| **`[reader]`** | **A `second-reader` agent** — never wrote the draft, so it can't approve its own habits. Runs on every non-bridge beat, and it's enforced: the guard denies the append and the Stop meter blocks the turn until its verdict file exists. Catches over-polished dialogue, a passive protagonist, repeated closing shapes, clock/menu/obligation drift — the things no regex can see; findings drive at most two revisions, then the beat ships and the residue is logged. |
| **`[scaffold]`** | **`_template/`** — the full per-story skeleton: master index, one-page story bible, chapter/character/world files (chapters carry a GM-only plan block), a resume-safe save state. |
| **`[skills]`** | **`new-story`, `finish-story`, `obsidian-cli`** — scaffold a story and open the active slot, close one out into a reading copy, and drive an Obsidian vault safely if you're playing through one. |

**You bring the story. The kit stops it from quietly going soft.**

> [!IMPORTANT]
> **This ships with zero prose.** No sample story, no pre-built characters — `_template/` is a skeleton of `{{TBD}}` placeholders. The "against" excerpt above is the kit's own lint fixture, kept only to prove the gates work — not a story you're inheriting. The craft canon is the whole product; the story is yours from the first prompt.

---

## Install · about five minutes

### 1 · Get your own copy

Click **Use this template ▸ Create a new repository** at the top of this page, name it, then clone it:

```bash
git clone https://github.com/<you>/<your-repo>.git ~/my-story
```

### 2 · (Optional) Open it as an Obsidian vault

Playing through [Obsidian](https://obsidian.md) gives you backlinks, the graph view, and the `obsidian` CLI that `CLAUDE.md` routes writes through. None of this is required — plain Markdown files and Claude Code alone work fine; skip straight to step 3 if that's your setup.

### 3 · Open Claude Code in the folder

```bash
cd ~/my-story && claude
```

`CLAUDE.md` auto-loads on startup — the five rules, play hygiene, and the hook wiring are already live.

### 4 · Start

> **"Let's start an adventure."**

Claude invokes the `new-story` skill, which walks you through genre, tone, POV, and — before Chapter 1 — the three things rule 2 requires: the central tension, the ending, and a target length.

---

## How you play it

It's an adventure game underneath the prose, not a story generator wearing one. Setup (`master_index.md` §4-5) asks for a real character sheet — narrative tags up to a detailed stat block — and a combat style anywhere from narrative-only to fully mechanical, same as any other IF/RPG hybrid. None of that is optional flavor text; it's what the story is actually tracking.

**One beat per response, always.** That is the unit every gate is built around: each
response ends with 1-4 numbered choices, or you free-type your own action instead; a
climax, revelation, or ambush drops the menu entirely and hands you the raw moment
(`second-person-turn-loop-craft`). Every single beat is opened, drafted by a fresh
`narrator` subagent, read by a fresh `second-reader`, and appended to the chapter log
before it reaches you — there's no faster path that skips a stage. A skip request
("get through the work day", "sleep on it") doesn't buy a longer rendered scene; it
buys a `bridge` — at most one compressed paragraph, then the next real beat lands in
the same response.

---

## How it works

The mechanism behind point 3 above — what actually keeps a draft honest between the prompt and the page. The GM (your session) never writes fiction; it routes, invokes, ships, and saves:

```
player types
  │  UserPromptSubmit — craft-gate.sh: spine + beat.py --gate
  │    → CHAPTER METER (GM-only: chapter, next beat, clock, open turns)
  │    → the active story's standing craft digests            ≈7.3 KB, one prompt
  ▼
GM (your session) — routes the input, never writes fiction
  ├─ beat.py open --type <bridge|scene|setpiece|close>  → ledger + a canon-first brief
  ├─ Agent(narrator)   [opus, high effort]  → writes <story>/scratchpad/chN_beatM_draft.md
  │     PostToolUse beat.py --post fires inside the subagent: lint + ceiling;
  │     a FAIL exits 2 and the narrator cuts before returning
  ├─ beat.py reader-brief   (re-lints, refuses if dirty — skipped only for a bridge)
  ├─ Agent(second-reader)  [sonnet, high effort]  → writes a VERDICT file
  ├─ clean → ship the beat verbatim to chat · findings → one narrator revision (max two)
  ├─ beat.py append   → lands the draft in chapters/chapter_N.md
  │     PreToolUse beat.py --guard DENIES a Write/Edit/MultiEdit or a
  │     recognisable Bash write (cat/tee/sed -i/dd/redirect) to the chapter
  │     file until lint is clean AND the reader has filed AND the text matches
  │     the draft — obfuscated paths (shell variables, globs) are not parsed
  ├─ GM rewrites game_state.md's ## Resume
  └─ beat.py close   → ticks the chapter plan, logs one line, flags a close at budget
  ▼
Stop — beat.py --meter checks eight invariants from file truth (not from memory) and
        blocks with the one thing still missing, or is silent
```

Each stage is a real file, not a convention: `craft-gate.sh` and `beat.py` are the four
hooks wired in `.claude/settings.json` (`UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
`Stop`); `narrator.md` and `second-reader.md` are agent definitions. Nothing here
depends on the model remembering to check itself, and nothing ships without the chain
being complete — that's what the guard and the meter are for.

<details>
<summary><b>What each stage actually does</b></summary>

<br>

- **Craft Gate** — Reads `_craft_research/CRAFT_SPINE.md` (the always-on through-lines and ship tests) plus the digest block from each mode in the active story's `## House Register`, and injects all of it fresh every prompt, followed by the chapter meter. A story switch needs no regeneration — the hook resolves everything live from `ACTIVE_GAME.md`. Degrades loudly: a missing spine, an unparseable register, or no chapter plan prints a `WARNING` naming the fix instead of silently injecting less.
- **Beat Open** — `beat.py open` resolves the story, chapter, and next beat number; reads the chapter's plan block for the one obligation this beat must deliver; and writes a self-contained brief (~28 KB) — spine, digests, the standing watchlist, the bible, exemplars, on-stage characters, the last two beats verbatim, the menus already offered (as prohibitions), and this beat's ceiling and clock. The plan's other turns are never in it — the writer can't foreshadow what it has never seen.
- **Narrator** — A fresh subagent, one per beat, with no memory of the forty beats before it. Reads the brief completely, writes the draft to `scratchpad/`, and replies with a five-line receipt — never prose, never a chat message. The `PostToolUse` hook lints the file the instant it's written; a ceiling FAIL sends it back to cut, not restructure.
- **Prose Lint** — Ten deterministic Tier-A rules: five phrase patterns (editorializing gloss clauses, "not so much as" hedges, appositive verdicts, filter-word openers, negation-list recaps) plus a draft-only `meta-leak` check, `repeat-in-beat`, `sentence-run`, and two draft-only structural checks — a missing `<!-- beat: type=... -->` header, and a body over its type's ceiling. There is no length floor and there never will be one again: ceilings bound beats above, by type, nothing here ever calls a beat too short. Tier-B is advisory: "the way X" simile drift, a pre-narrated menu, a repeated menu shape, a dissolving clock.
- **Second Reader** — A separate `sonnet`, high-effort subagent that never drafted the beat, so it can't approve its own habits. Runs on every non-bridge beat and writes a verdict *file*: line 1 a machine-parsed `VERDICT: CLEAN | N FINDING(S)` (cap 4), then required `OBLIGATION:` / `CLOCK:` / `MENU:` lines, then the findings — over-polished dialogue read as a set, a passive protagonist, repeated closing shapes, explained-instead-of-shown meaning, reflection outrunning its trigger, and the tic wearing new clothes. Anything but a clean verdict on all three required lines forces a narrator revision, even if line 1 said CLEAN.
- **Guard** — A `PreToolUse` check on every write to a chapter log: denies it outright unless the draft is lint-clean, the reader has filed (or the beat is a waived bridge), and the text being written actually matches the cleared draft. Retyping the beat by hand fails this by design.
- **Meter** — A `Stop` hook that checks eight things from file truth before your turn is allowed to end: lint clean, reader present, the beat actually saved to the chapter log, `game_state.md` updated, the plan ticked, the chat reply matching the draft with no leaked machinery, and the chapter budget. Silence means every invariant held; a block names exactly one missing step.

</details>

### Beat sizes and the chapter plan

There is no minimum beat length, and there will not be one again — a padding floor
was the mechanical cause of the exact "stops reading like a novel" problem this kit
exists to fix. Beats are bounded **above only**, by type:

| type | when | ceiling (prose body; the menu doesn't count) |
|---|---|---|
| `bridge` | a requested skip, travel, a night's sleep — compressed, then a turn lands | 900 chars |
| `scene` | the default: one place, one exchange, one fact changed | 2,400 chars |
| `setpiece` | climax, duel, revelation | 3,200 chars |
| `close` | land the last open turn, then time-skip out of the chapter | 2,600 chars |

A `bridge` is what a skip request actually buys: at most one compressed paragraph,
then the next real beat lands in the same response — never a rendered day. `master_index.md`'s
`**Beat Sizes**` line overrides these per story; `beat.py` reads it directly.

Every chapter also carries a short **plan**: 2-4 turns (one sentence each — the fact
each one changes), a budget, and a named in-fiction clock with a real consequence for
missing it. It's written by `beat.py open-chapter` into a `<!-- plan:start … plan:end
-->` comment at the top of the chapter file, and it's **GM-only** — three separate
guarantees keep it that way: Obsidian's reading view doesn't render HTML comments, the
linter strips it from every corpus read and every brief, and no code path ever puts
more than the current beat's one obligation into anything the writer or the player
sees. The narrator writes each beat without knowing what any future turn is, so it
cannot foreshadow a plan it has never read. Off-plan play doesn't get overridden — the
GM re-scopes the nearest open turn to where the player actually went, on the record,
rather than steering back to a script.

Worth being precise about what's mechanized here and what still isn't: the chapter
budget is genuinely machine-read and enforced — `beat.py` counts against it and forces
a `close` beat at budget — but the source is the `--budget` flag you pass to
`beat.py open-chapter`, not `master_index.md`'s **Beats per Chapter** line, which is a
human-facing default only (nothing parses it). **Central Tension**, **How It Ends**, and
**Target Length** (the story-level shape from rule 2) are likewise not read by any
script; naming them well is still entirely on you and whoever's steering the story.

---

## Limitations

- **The craft canon is a personal research synthesis, not a systematic literature review.** Fifteen deep-research passes on published craft advice and worked examples — useful and falsifiable, but one author's shelf, not a citable academic source.
- **The before/after demo above proves the gates catch something, not that every beat you ship will read that well.** The "against" column is a fixture calibrated to pass cleanly; real first drafts don't clear all eight through-lines on the first try, which is the entire reason the gate stack exists downstream of drafting instead of relying on getting it right the first time.
- **The linter's baseline is calibrated against one corpus.** `BASELINE_CORPUS_FAILS` in `prose-lint.py` was set against ~48KB of one story's published prose. Recalibrate it against your own once you have chapters to lint — the comment above the constant explains how.
- **It assumes second-person, present-tense interactive fiction in English.** That's the register every card and report was written and tested against. The mechanics generalize; the specific prose rules (especially `voice-and-dialect` / `accent-via-syntax`) may not transfer as-is to first person, past tense, or other languages.
- **The gates catch tics, not taste.** A clean lint pass and a clean second-reader read are a floor, not a guarantee the beat is good. Rule 5 still applies: if it reads as forced or boring, stop and say so — no hook catches that.
- **A beat costs roughly two minutes, not twenty seconds.** Two sequential subagent calls (`narrator` on Opus, `second-reader` on Sonnet, both at high effort) plus several script calls run every non-bridge beat. That's slower than one model turn, and it's the trade this kit makes on purpose — quality over latency, never the reverse.
- **`BASELINE_CORPUS_FAILS` must be re-derived against your own corpus, not copied from this repo's.** `prose-lint.py --selftest` prints the number every time; the comment above the constant explains how to update it once you have chapters of your own to lint against.
- **`effort: high` in an agent's frontmatter may not be honored by every build.** If it's silently ignored, both subagents run at whatever the default is — with no error, and no visible signal. Check the subagent transcript on your first real beat; don't assume the setting took.

---

## Repo layout

```
CLAUDE.md                  the five rules + play hygiene + the beat loop — auto-loaded
ACTIVE_GAME.md              the single pointer the craft-gate hook follows every prompt
Welcome.md                  vault landing page: how to start, the template's shape
_template/                  per-story skeleton — master index, bible, outline, twists,
                              _exemplars.md, characters/, chapters/ (ships a GM-only plan
                              block), scratchpad/, world/
_craft_research/            15 filed reports, the CRAFT_SPINE.md distillation, per-mode
                              cards, and the prompts that produced them
.claude/hooks/              craft-gate.sh (inject) + beat.py (the story-level gate:
                              plan, chain of custody, guard, meter) + prose-lint.py
                              (the sentence-level lint beat.py calls), with fixtures
.claude/agents/             narrator.md (writes one beat, opus/high) + second-reader.md
                              (verdict file, sonnet/high) — the beat loop's two agents
.claude/skills/             new-story, finish-story, obsidian-cli
docs/                       the hero image
LICENSE · .gitignore
```

`_craft_research/CRAFT_SPINE.md` is the file to read first if you read one thing.

---

## Credits & license

- **Extracted from** an actively-played personal Adventure Games vault — the hooks, canon, and templates here are the exact ones a real story was drafted against, stripped of that story's own prose and characters.
- **Sibling projects** — [second-brain](https://github.com/christian93kg/second-brain), an Obsidian + Claude Code knowledge base, and [brain-gym](https://github.com/christian93kg/brain-gym), a calibration-scored tutor skill.
- **License** — MIT, see [`LICENSE`](LICENSE)

<div align="center">
<br>

**[Read the craft canon →](_craft_research/CRAFT_SPINE.md)** · **[See the five rules →](CLAUDE.md)**

</div>
