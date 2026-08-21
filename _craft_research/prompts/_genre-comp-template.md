# TEMPLATE — Genre & comp craft prompt (fill before running)

> ⚠ **NOT runnable as-is.** This file has `[SLOT]`s. A deep-research tool cannot research a
> genre it hasn't been told — every technique it returns hangs on the named comps. **Fill every
> `[SLOT]` first, or just ask Claude to fill it for a named genre and hand you a ready-to-paste
> prompt.** For a worked example, see the filed report [[reports/genre-cosmic-horror]] (cosmic
> horror) and the prompt shape that produced it.

**Slots to fill:**
- `[GENRE]` — e.g. "epic fantasy", "cosmic horror", "heist thriller", "literary romance".
- `[REGISTER]` — the tonal target in one phrase, e.g. "dread-forward, restraint over gore".
- `[NAMED COMPS]` — 3–6 specific, citable works/authors in this register. Vague comps → vague report.
- `[PROTAGONIST NOTE]` — one line on who the POV character is and how they behave under pressure.
- `[3–5 GENRE-SPECIFIC CRAFT AREAS]` — the devices unique to this genre you most need.
- `[ANTI-PATTERNS]` — the clichés/registers you specifically want to AVOID.
- `[FAILURE MODES]` — the failings in your own drafts the report should counter.

---
--- PROMPT (fill the slots) ---

You are a prose-craft analyst specializing in genre fiction at the sentence and scene level.
I write second-person literary interactive fiction in **[GENRE]**, in the register of
**[REGISTER]**. My protagonist: [PROTAGONIST NOTE].

Research and report on **how skilled writers in this register achieve [GENRE]'s core effects
through craft — at the level of sentence, beat, and scene — not through plot or worldbuilding**.
Draw on named, citable sources: [NAMED COMPS]. Include both fiction exemplars and any relevant
craft/screenwriting authorities on this register.

For each technique you surface, you MUST give: the named device; a short quoted or
closely-paraphrased example from a named source; and why it produces the intended effect.

Cover at minimum: [3–5 GENRE-SPECIFIC CRAFT AREAS].

ANTI-REQUIREMENTS:
- No generic "show don't tell" advice; no adjective/sensory-word lists.
- No plot summaries of the comps for their own sake.
- Do not recommend any of these, which I am deliberately avoiding: [ANTI-PATTERNS].
- Every technique must be falsifiable: testable against a specific draft paragraph, not a vibe.

OUTPUT CONTRACT — end with a section titled **"Falsifiable techniques"** of 8–12 entries, each:
- **Technique** → **Why it works** → **Before / After** (a flat draft sentence → the same beat
  rewritten with the technique) → **Checklist line** (a single pass/fail imperative).

Finally, a one-paragraph **"Tie-back"** noting which techniques most directly counter these
failure modes: [FAILURE MODES].

---
*Filled-example slot set that produced [[reports/genre-cosmic-horror]] (delete before running your own):*
`[GENRE]` = cosmic horror · `[REGISTER]` = dread built by withholding, the wrong detail not the
gory one, calm narration over a widening wrongness · `[NAMED COMPS]` = Caitlín R. Kiernan, Laird
Barron, T.E.D. Klein, Thomas Ligotti, John Langan (*The Fisherman*), Shirley Jackson, Ishiguro's
calm narration · `[ANTI-PATTERNS]` = jump-scares, monster-cataloguing, gore for shock,
eldritch-adjective soup, explaining the horror's rules.