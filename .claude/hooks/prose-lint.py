#!/usr/bin/env python3
# prose-lint.py — pre-ship prose gate. Sibling to craft-gate.sh, opposite end of
# the turn: craft-gate injects doctrine BEFORE drafting (UserPromptSubmit);
# this checks the draft AFTER writing (PostToolUse) and can block on it.
#
# WHY THIS EXISTS: the craft canon was never missing — it is injected every
# prompt and was in context when bad drafts were written. The failure is that
# the pass which checks a draft is the pass that wrote it, and it rubber-stamps
# its own habits. 3 of 3 rewrites in one story's early revision history were player-
# triggered and every one found real violations a self-audit had just passed.
# A reminder cannot fix a reminder-application problem; a hook can.
#
# CONTRACT (inherited from craft-gate.sh):
#   - degrade LOUDLY, never silently: a missing input warns and keeps going
#   - a crash must never block writing — errors exit 0
#   - constants here are the single source of truth; CLAUDE.md points, never
#     restates. BEAT_SIZES below is the single source of truth for ceilings;
#     beat.py imports it (and beat_sizes/lint/menu_options/strip_meta/tier_c/
#     render) via importlib and never restates a number either.
#
# WHAT IT PROVABLY CANNOT DO — do not add rules for these, they belong to the
# second reader (.claude/agents/second-reader.md):
#   wit / "aphoristic" (a disfluency proxy was tested and did not separate the
#   over-polished beat from the good one), reliable speaker attribution (~35% in
#   this tag-light register), narrated subtext, interiority bloat, catalogue
#   description, free facts, underlined handbacks ("It's the first time they have"
#   fires nothing here, by design and on the record).
#
# Modes:
#   prose-lint.py <draft.md> [--type T] [--is-draft]   report to stdout, exit 0
#   prose-lint.py --hook                                manual/legacy; the live PostToolUse
#                                                        entry point is `beat.py --post`,
#                                                        which imports this file as a module
#   prose-lint.py --selftest                            fixtures + corpus regression
#
# Self-check:  python3 .claude/hooks/prose-lint.py --selftest

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

VAULT = os.environ.get("CLAUDE_PROJECT_DIR", ".")
ACTIVE = os.path.join(VAULT, "ACTIVE_GAME.md")
CARDS = os.path.join(VAULT, "_craft_research", "cards")
SPINE = os.path.join(VAULT, "_craft_research", "CRAFT_SPINE.md")
# Fixtures are a kit-development artifact shipped alongside THIS script, not
# story data — they must resolve against the script's own directory, never
# against CLAUDE_PROJECT_DIR/VAULT (same reasoning as beat.py's importlib
# contract: "from its own directory, never from VAULT"). Getting this wrong
# silently breaks `--selftest` the moment CLAUDE_PROJECT_DIR points at a
# story tree that doesn't carry a copy of the fixtures (e.g. running the
# repo's linter read-only against the vault for the corpus regression).
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# The gate's trigger. This is the ONLY thing standing between a draft and the
# chapter log, so it matches on the `_draft.md` suffix ALONE, in any directory.
# It used to also require a literal `scratchpad/` parent, which meant a draft
# written to `_scratch/` or `drafts/` sailed past unlinted and unannounced —
# the exact silent failure the "degrade LOUDLY" contract above forbids. The
# convention is still `<story>/scratchpad/…_draft.md`; a draft outside it is
# linted anyway and told where it should have been. It is also the default
# signal for `is_draft` in lint() below: a `_draft.md` path is a draft unless
# told otherwise; anything else is treated as published prose unless told
# otherwise.
DRAFT_PATH_RE = re.compile(r"_draft\.md$")
CONVENTIONAL_DIR = "scratchpad"

# THERE IS NO LENGTH FLOOR AND THERE WILL NOT BE ONE AGAIN.
# A +/-12% band around 3,000 chars produced 116 of 127 lint blocks in the one played
# session (91%), drove 8-15 rewrite cycles per beat, and its own remedy string told the
# model to pad with ambiance. Chapter 1 — the chapter cited twice in _exemplars.md —
# averages 1,747 body chars and would have failed all five beats. Beats are bounded
# ABOVE, by type, in BEAT_SIZES below. Nothing here is ever too short.
BEAT_SIZES = {"bridge": 900, "scene": 2400, "setpiece": 3200, "close": 2600}  # CEILINGS. NO FLOOR.

# Machine-only vocabulary. If any of this appears in a draft's prose body (Tier-A
# `meta-leak`) or in the chat message the GM ships (beat.py's `meta-leak-chat`),
# the machinery has leaked to the player. Shared verbatim with beat.py — both
# copies must match; this one is the copy of record.
#
# B6/B12: the bare nouns `ceiling`/`budget`/`lint`/`obligation` used to match
# ANY appearance of those ordinary English words — "The ceiling fan turned.",
# "under no obligation to explain", "cut my budget", "lint on his lapel" all
# FAILed as meta-leak, which is exactly the kind of dark-academia/noir prose
# this kit's own genre cards target. Every alternative below now requires the
# actual machine SHAPE the real strings have (a digit, "chars", "clean/ok",
# a compound like "chapter budget", or literal ALL-CAPS "OBLIGATION" — the
# label's one real shipped form), not just the word.
META_RE = re.compile(
    r"\bBeat \d|\bbeat type\b|chapter plan|VERDICT|chain \d/\d|\boption \d\)"
    r"|\bsize-ceiling\b|\b(?:bridge|scene|setpiece|close)\s+ceiling\b|\bceiling\b(?=[^\n]{0,40}\bchars?\b)"
    r"|\bbudget\s+(?:of\s+)?\d+\b|\bover[- ]budget\b|\b(?:chapter|beat|char)\s+budget\b|\bbudget:\s*\d+"
    r"|\bprose-lint(?:\.py)?\b|\blint-clean\b|\blint\s+(?:ok|clean)\b|\bnot\s+lint-clean\b"
    r"|(?-i:OBLIGATION)\b|\bthe\s+obligation\b(?=[^\n]{0,30}\bbeat\b)"
    r"|\bsecond-reader\b|\bbeat\.py\b",
    re.I,
)

# Output-hygiene caps on the rendered report, so a noisy beat cannot blow the
# hook-output budget. Unlike craft-gate.sh's MAX_BYTES these are not empirically
# derived against a threshold — they are just "enough to read at a glance."
MAX_REPORT_BYTES = 2048
MAX_REPORT_LINES = 25

# Corpus-regression baseline: total Tier-A FAILs across all published beats of
# the active story at calibration time, with is_draft=False (the draft-only
# rules — beat-header/size-ceiling/meta-leak — never run on the corpus, which
# is what keeps this number meaningful at all). --selftest asserts we never
# exceed it. Raising this number is only ever correct when new prose was
# published, never to make a new PATTERNS entry pass.
#
# Re-derived 2026-09-02 over all 30 published beats, post-length-band: 11
# (gloss-clause 4, sentence-run 3, so-much-as 2, appositive-verdict 1,
# filter-word 1). Never tune a rule to hit the old number (10, calibrated
# 2026-07-26 pre-length-band-removal); the baseline follows the rules, not
# the reverse.
BASELINE_CORPUS_FAILS = 11

warnings = []


def warn(msg):
    warnings.append(msg)


# --------------------------------------------------------------------------
# Tier A — FAIL rules.
#
# Every rule mechanises doctrine that already exists in _craft_research/. This
# file invents no craft rules; `owner` names the card that owns each one, or —
# for the structural / draft-only checks below — the remedy text itself.
#
# TRIPWIRE: if the total number of Tier-A rule ids (this list, plus the four
# structural checks below it: repeat-in-beat, sentence-run, beat-header,
# size-ceiling) ever exceeds ~15, that is the signal vault rule 3 is genuinely
# being violated — the story has become over-managed and the answer is a
# reset, not entry #16. Currently 10.
#
# FROZEN at 6 regex entries. Killing a tic by regex does not kill the tic — it
# mutates (", which is" -> "the way X" similes -> interpretive trailing
# clauses -> summary closers). Regex chases the FORM; only a reader catches
# the FUNCTION. Every future catch goes into .claude/agents/second-reader.md
# as a judgement clause, never here.
# --------------------------------------------------------------------------
PATTERNS = [
    dict(
        id="gloss-clause",
        rx=re.compile(
            r",\s+(?:which|who)\s+(?:is|isn't|was|wasn't|are|aren't)\b"
            r"|\bwhich is to say\b",
            re.I,
        ),
        owner="narrator-stays-out / event-density KILL: editorial verdicts",
        note="the dominant tic — 20+ instances across the corpus this was calibrated on",
        narration_only=True,
    ),
    dict(
        id="so-much-as",
        rx=re.compile(
            r"\b(?:isn't|is not|wasn't|was not|not)\b[^.?!]{1,45}\bso much as\b", re.I
        ),
        owner="narrator-stays-out: the shown detail forces the conclusion",
        narration_only=True,
    ),
    dict(
        id="appositive-verdict",
        rx=re.compile(
            r"—\s*(?:a |an |the )?[a-z]{3,15},\s+not\s+(?:a |an |the )?"
            r"(?!more\b|less\b|much\b|many\b|often\b|always\b|never\b|yet\b|now\b|quite\b)"
            r"[a-z]{3,15}"
        ),
        owner="narrator-stays-out: no authorial scoring",
        note='the appositive verdict, e.g. "— a habit, not a verdict"',
        narration_only=True,
    ),
    dict(
        id="filter-word",
        rx=re.compile(
            r"\byou\s+(?:see|saw|feel|felt|notice|noticed|realize|realise|realized|realised"
            r"|sense|sensed|register|registered)\b",
            re.I,
        ),
        owner="event-density KILL: filter-word openers",
        narration_only=True,
    ),
    dict(
        id="negation-list",
        rx=re.compile(
            r"\bno\s+\w+,\s+no\s+\w+,\s+no\s+\w+|\bnot the \w+, not the \w+, not the \w+", re.I
        ),
        owner="curate-not-generate: negation-list recap",
        narration_only=False,
    ),
    dict(
        id="meta-leak",
        rx=META_RE,
        owner="the player never sees the machinery",
        note="draft-only — the machinery's own vocabulary (beat/budget/lint/VERDICT/…) "
        "leaking into prose the player will read",
        narration_only=False,
        draft_only=True,
    ),
]

STOPWORDS = set(
    """a an the and or but if of to in on at by for with from as is was are were be been being
    it its it's he she they them him her his hers their this that these those there here you your
    yours i me my we us our not no nor so than then too very can could will would shall should
    may might must do does did done have has had having what which who whom when where why how
    all any both each few more most other some such only own same s t just don now up down out
    off over under again further once about into through during before after above below between
    both against because while until him're what's don't didn't isn't wasn't"""
    .split()
)


# --------------------------------------------------------------------------
# Text extraction — one implementation, used by both the draft reader and the
# corpus reader so the two can never drift.
# --------------------------------------------------------------------------
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
QUOTE_RE = re.compile(r"[“\"]([^”\"]{1,400})[”\"]")

# The beat-block output contract's first line. COMMENT_RE strips this from
# the body, so it costs zero prose characters and trips no other rule.
BEAT_HEADER_RE = re.compile(
    r"<!--\s*beat:\s*type=(bridge|scene|setpiece|close)"
    r"(?:\s+obligation=\"([^\"]{1,240})\")?"
    r"(?:\s+onstage=([a-z0-9_,\-]*))?\s*-->",
    re.I,
)

# The menu marker. strip_meta() already drops these lines from the body
# (correctly — the char count that matters is the prose); menu_options() is
# its sibling that keeps the option text, for the checks and briefs that need
# to know what was offered.
MENU_RE = re.compile(r"^\*\*Choices offered:\*\*\s*\n((?:^\d+\.\s.*\n?)+)", re.M)


def strip_meta(text):
    """Reduce a beat block or draft file to prose body. Deterministic; the
    char count it yields is what size-ceiling measures against."""
    text = FRONTMATTER_RE.sub("", text)
    text = COMMENT_RE.sub("", text)
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("#"):
            continue
        if s.startswith(">"):
            continue
        if s.startswith("**Player input:**") or s.startswith("**Choices offered:**"):
            continue
        if re.match(r"^\d+\.\s", s):  # choice menu items
            continue
        if s in ("---", "***", "___"):
            continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def menu_options(raw):
    """The verbatim option text under '**Choices offered:**', or [] when
    there is no menu (a climax's 'None — <why>' included — by design, since
    that line never matches MENU_RE's numbered-list tail)."""
    m = MENU_RE.search(raw)
    if not m:
        return []
    opts = []
    for line in m.group(1).splitlines():
        om = re.match(r"^\d+\.\s*(.+?)\s*$", line)
        if om:
            opts.append(om.group(1))
    return opts


def beat_header_ok(raw):
    """True iff the first non-blank line after any frontmatter is a valid
    <!-- beat: type=... --> comment — the draft output contract's line 1."""
    text = FRONTMATTER_RE.sub("", raw, count=1)
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        return bool(BEAT_HEADER_RE.match(s))
    return False


def detect_beat_type(raw):
    """beat_type=None resolution for lint(): the <!-- beat: type=... -->
    header anywhere in the file, else 'scene' with a loud warning — a silent
    guess is exactly the kind of degrade this file's contract forbids."""
    m = BEAT_HEADER_RE.search(raw)
    if m:
        return m.group(1).lower()
    warn("no <!-- beat: type=... --> header found — defaulting to type=scene")
    return "scene"


def split_beats(chapter_text):
    """Return [(title, body)] for each '### Beat' block in a chapter file."""
    parts = re.split(r"^###\s+(Beat[^\n]*)$", chapter_text, flags=re.M)
    beats = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = strip_meta(parts[i + 1])
        if body:
            beats.append((title, body))
    return beats


def narration_only(body):
    """Blank out quoted dialogue, preserving offsets so line numbers stay true.
    Rules about the narrator must not fire on what a character says."""
    return QUOTE_RE.sub(lambda m: '"' + " " * len(m.group(1)) + '"', body)


def words(s):
    return re.findall(r"[a-z0-9']+", s.lower())


def sentences(s):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", s) if x.strip()]


def ngrams(toks, n):
    return [" ".join(toks[i : i + n]) for i in range(len(toks) - n + 1)]


# --------------------------------------------------------------------------
# Story context
# --------------------------------------------------------------------------
def active_story():
    if not os.path.isfile(ACTIVE):
        warn("ACTIVE_GAME.md not found — story-specific checks skipped.")
        return None
    m = re.search(r"^active_path:[ \t]*(?:[\"'])?(.+?)(?:[\"'])?[ \t]*$", open(ACTIVE).read(), re.M)
    if not m:
        # Matches craft-gate.sh: a blank active_path is a fresh clone, not a
        # fault. Story-specific checks (per-story beat sizes, cross-chapter
        # echo) simply have nothing to run against yet.
        return None
    story = m.group(1).strip().strip("/")
    if not os.path.isdir(os.path.join(VAULT, story)):
        warn(f"active_path '{story}' is not a directory — story-specific checks skipped.")
        return None
    return story


def beat_sizes(story):
    """Per-story override of BEAT_SIZES, read from master_index.md's
    '**Beat Sizes**' line (e.g. 'bridge ≤900 · scene ≤2,400 · setpiece
    ≤3,200 · close ≤2,600'). Falls back to the module defaults when the line
    is absent. A story still carrying the retired '**Response Length**' line
    gets a loud warning and the defaults — the old band is never
    reconstructed from it."""
    sizes = dict(BEAT_SIZES)
    if not story:
        return sizes
    mi = os.path.join(VAULT, story, "master_index.md")
    if not os.path.isfile(mi):
        return sizes
    text = open(mi).read()
    if re.search(r"\*\*Response Length\*\*", text):
        warn(
            f"{story}/master_index.md still carries '**Response Length**' — "
            "convert to '**Beat Sizes**'; the length floor is retired. Using ceiling defaults."
        )
        return sizes
    m = re.search(r"\*\*Beat Sizes\*\*:\s*(.+)", text)
    if not m:
        return sizes
    for part in re.split(r"[·•]", m.group(1)):
        pm = re.match(
            r"\s*(bridge|scene|setpiece|close)\s*[≤:]?\s*~?\s*([\d,]+)", part.strip(), re.I
        )
        if pm:
            sizes[pm.group(1).lower()] = int(pm.group(2).replace(",", ""))
    return sizes


def corpus_beats(story):
    out = []
    for f in sorted(glob.glob(os.path.join(VAULT, story, "chapters", "*.md"))):
        if os.path.basename(f).startswith("_"):
            continue
        for title, body in split_beats(open(f).read()):
            out.append((os.path.basename(f), title, body))
    return out


def proper_nouns(story, corpus_text):
    names = set()
    for f in glob.glob(os.path.join(VAULT, story, "characters", "*.md")):
        if os.path.basename(f).startswith("_"):
            continue
        for line in open(f).read().split("\n")[:40]:
            if line.startswith("# ") or line.startswith("- **Name**"):
                names |= set(re.findall(r"\b[A-Z][a-z]{2,}\b", line))
    # any capitalised token used mid-sentence often enough to be a name/place
    mid = Counter(re.findall(r"(?<![.!?\"“]\s)(?<!^)\b([A-Z][a-z]{2,})\b", corpus_text))
    names |= {w for w, c in mid.items() if c >= 3}
    return {n.lower() for n in names}


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
def suppressed(raw):
    return {m.group(1) for m in re.finditer(r"<!--\s*lint-ok:\s*([a-z-]+)", raw)}


def snippet(body, start, end, pad=34):
    a, b = max(0, start - pad), min(len(body), end + pad)
    s = re.sub(r"\s+", " ", body[a:b]).strip()
    return ("…" if a else "") + s + ("…" if b < len(body) else "")


def lineno(body, idx):
    return body.count("\n", 0, idx) + 1


def tier_a(body, skip, is_draft=False, beat_type=None, ceiling=None, raw=None):
    """Tier-A: deterministic FAIL rules. The PATTERNS regexes (bar meta-leak)
    plus repeat-in-beat and sentence-run fire on every beat, published or
    drafted. beat-header / size-ceiling / meta-leak are gated on is_draft —
    they NEVER fire on the published corpus, which is what keeps
    BASELINE_CORPUS_FAILS meaningful."""
    fails = []
    narr = narration_only(body)
    for rule in PATTERNS:
        if rule["id"] in skip:
            continue
        if rule.get("draft_only") and not is_draft:
            continue
        hay = narr if rule["narration_only"] else body
        for m in rule["rx"].finditer(hay):
            fails.append(
                dict(
                    id=rule["id"],
                    line=lineno(body, m.start()),
                    quote=snippet(body, m.start(), m.end()),
                    owner=rule["owner"],
                )
            )

    # in-beat repetition: a 4-gram used twice, names excluded
    if "repeat-in-beat" not in skip:
        toks = words(body)
        counts = Counter(g for g in ngrams(toks, 4))
        for g, c in counts.items():
            if c < 3:
                continue
            gtok = g.split()
            if all(t in STOPWORDS for t in gtok):
                continue
            fails.append(
                dict(
                    id="repeat-in-beat",
                    line=0,
                    quote=f'"{g}" ×{c}',
                    owner="event-density: a beat alters, it does not elaborate",
                )
            )

    # three consecutive sentences of near-identical length
    if "sentence-run" not in skip:
        sents = [s for s in sentences(narr) if len(words(s)) >= 6]
        lens = [len(words(s)) for s in sents]
        for i in range(len(lens) - 2):
            w = lens[i : i + 3]
            if max(w) - min(w) <= 2 and min(w) >= 15:
                fails.append(
                    dict(
                        id="sentence-run",
                        line=0,
                        quote=f"3 sentences of {w} words — " + snippet(sents[i], 0, len(sents[i]), 0)[:60],
                        owner="spine ship test: vary one",
                    )
                )
                break  # one report is enough; the rule is about the reading ear

    if is_draft:
        if "beat-header" not in skip and not beat_header_ok(raw or ""):
            fails.append(
                dict(
                    id="beat-header",
                    line=0,
                    quote="declare the beat type — bridge/scene/setpiece/close — "
                    "the ceiling depends on it",
                    owner="draft output contract: line 1 must be <!-- beat: type=... -->",
                )
            )
        if "size-ceiling" not in skip and ceiling is not None and len(body) > ceiling:
            over = len(body) - ceiling
            fails.append(
                dict(
                    id="size-ceiling",
                    line=0,
                    quote=f"{over:,} over the {beat_type} ceiling ({len(body):,}/{ceiling:,} "
                    "chars) — cut, do not rewrite: find the sentence whose deletion leaves the "
                    "next still making complete sense, and delete it",
                    owner="BEAT_SIZES — a ceiling, never a target",
                )
            )
    return fails


# Tier-B advisories that watch for the KNOWN MUTATION of a killed Tier-A tic,
# or for a structural miss a regex cannot own outright (see the FROZEN
# comment above PATTERNS). Never promoted to FAIL — see §0.7/§0.8 of the
# design annex for why each one is calibrated advisory-only.
SIMILE_RE = re.compile(r"\bthe way (?:you|she|he|they|it|a |someone)\b", re.I)
CLOCK_DISSOLVE_RE = re.compile(
    r"plenty of time|no rush|nothing until|not until \w+day|days away|a whole day|the rest of \w+day",
    re.I,
)


def _option_signature(opt):
    """A menu option's cheap fingerprint for menu-echo: its capitalised
    tokens (named people/places) plus its first word (usually the verb)."""
    caps = set(re.findall(r"\b[A-Z][a-z]{2,}\b", opt))
    toks = words(opt)
    return caps | ({toks[0]} if toks else set())


def tier_b(body, story, corpus, names, skip, raw=None, prior_menus=None):
    adv = []

    # narrator-simile: the documented mutation of the killed gloss-clause tic.
    if "narrator-simile" not in skip:
        n = len(SIMILE_RE.findall(narration_only(body)))
        if n >= 3:
            adv.append(dict(id="narrator-simile", quote=f'{n} "the way X" similes in this beat'))

    # pre-narrated-menu: the closing line telegraphs the choices about to print.
    if raw is not None and "pre-narrated-menu" not in skip:
        opts = menu_options(raw)
        sents = sentences(body)
        if opts and sents:
            last = {w for w in words(sents[-1]) if w not in STOPWORDS}
            hit = sum(
                1 for opt in opts if len(last & {w for w in words(opt) if w not in STOPWORDS}) >= 2
            )
            if hit >= 2:
                adv.append(
                    dict(id="pre-narrated-menu", quote=f"final sentence echoes {hit} menu options")
                )

    # menu-echo: this beat's options resemble ones already offered. Advisory
    # only — measured to fire on adjacent Chapter 1 pairs too (see annex
    # §0.7); the real mechanism is the verbatim forbidden list in the brief.
    if raw is not None and prior_menus and "menu-echo" not in skip:
        prior_sigs = [(o, _option_signature(o)) for pm in prior_menus for o in pm]
        for opt in menu_options(raw):
            sig = _option_signature(opt)
            for prior_opt, prior_sig in prior_sigs:
                if sig & prior_sig:
                    adv.append(
                        dict(
                            id="menu-echo",
                            quote=f'"{opt[:60]}" overlaps prior "{prior_opt[:60]}"',
                        )
                    )
                    break

    # clock-dissolve: the Ch4 B3 failure — a line that softens or widens a
    # live deadline instead of holding it.
    if "clock-dissolve" not in skip:
        m = CLOCK_DISSOLVE_RE.search(body)
        if m:
            adv.append(dict(id="clock-dissolve", quote=snippet(body, m.start(), m.end())))

    # cross-chapter echo: rare 4-grams shared with prior published prose.
    # A beat re-linted after publication would otherwise match itself, so any
    # corpus beat that is substantially the draft is dropped first.
    if story and "echo" not in skip:
        dset = set(ngrams(words(body), 4))
        prior = " \n ".join(
            b
            for _, _, b in corpus
            if not dset
            or len(dset & set(ngrams(words(b), 4))) / max(1, len(dset)) < 0.5
        )
        ptoks = words(prior)
        pcount = Counter(ngrams(ptoks, 4))
        tokfreq = Counter(ptoks)
        dtoks = words(body)
        hits = []
        for g in set(ngrams(dtoks, 4)):
            if pcount.get(g, 0) == 0:
                continue
            gt = g.split()
            if any(t in names for t in gt):
                continue
            rare = [t for t in gt if t not in STOPWORDS and tokfreq.get(t, 0) <= 4]
            if rare:
                hits.append((min(tokfreq.get(t, 0) for t in rare), g))
        for _, g in sorted(hits)[:5]:
            adv.append(dict(id="echo", quote=f'"{g}" also in prior chapters'))

    # PC question floor. This register drops question marks ("For what."), so
    # detection accepts interrogative openers too.
    if "question-floor" not in skip:
        quoted = QUOTE_RE.findall(body)
        interro = [
            q
            for q in quoted
            if q.rstrip().endswith("?")
            or re.match(
                r"^(who|what|when|where|why|how|do|did|does|are|is|can|could|would|and the|and you)\b",
                q.strip(),
                re.I,
            )
        ]
        if len(quoted) >= 6 and len(interro) < 2:
            adv.append(
                dict(
                    id="question-floor",
                    quote=f"{len(quoted)} quoted lines, {len(interro)} interrogative "
                    "— dialogue-subtext: the PC advances by asking",
                )
            )

    # closer shape, only when the two previous beats closed the same way
    if story and corpus and "closer-shape" not in skip:
        def abstract_closer(b):
            last = sentences(b)[-1] if sentences(b) else ""
            if '"' in last or "“" in last:
                return False
            if re.search(r"\b[A-Z][a-z]{2,}\b", last):
                return False
            return not re.search(
                r"\b(goes|walks|sets|puts|stops|turns|looks|takes|holds|opens|closes|sits|stands|"
                r"reaches|writes|eats|moves|leaves)\b",
                last,
            )

        if abstract_closer(body) and all(abstract_closer(b) for _, _, b in corpus[-2:]):
            adv.append(dict(id="closer-shape", quote="third consecutive abstract beat-closer"))
    return adv


def tier_c(body, corpus, names):
    lines = []
    quoted = QUOTE_RE.findall(body)
    if quoted:
        lines.append(f"-- dialogue dossier ({len(quoted)} lines this beat) "
                     "-- no verdict; read each speaker's set together")
        for q in quoted:
            lines.append(f'   "{q[:88]}"')
        present = {n for n in names if re.search(rf"\b{re.escape(n)}\b", body, re.I)}
        for n in sorted(present):
            prior = []
            for _, _, b in corpus[-3:]:
                for para in b.split("\n\n"):
                    if re.search(rf"\b{re.escape(n)}\b", para, re.I):
                        prior += QUOTE_RE.findall(para)
            if prior:
                lines.append(f"   [{n.title()}, last 3 beats] " + " | ".join(f'"{p[:56]}"' for p in prior[:4]))
    return lines


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def lint(path_or_text, is_text=False, want_c=True, beat_type=None, is_draft=None, prior_menus=None):
    raw = path_or_text if is_text else open(path_or_text).read()
    body = strip_meta(raw)
    skip = suppressed(raw)

    if is_draft is None:
        # Auto only makes sense against a real path; is_text callers (an
        # inflated fixture, a hand-built string) must say what they mean.
        is_draft = (not is_text) and bool(DRAFT_PATH_RE.search(path_or_text))
    if beat_type is None:
        beat_type = detect_beat_type(raw)

    story = active_story()
    ceiling = beat_sizes(story).get(beat_type)
    corpus = corpus_beats(story) if story else []
    names = proper_nouns(story, " ".join(b for _, _, b in corpus)) if story else set()

    fails = tier_a(body, skip, is_draft=is_draft, beat_type=beat_type, ceiling=ceiling, raw=raw)
    adv = tier_b(body, story, corpus, names, skip, raw=raw, prior_menus=prior_menus)
    cee = tier_c(body, corpus, names) if want_c else []
    return body, fails, adv, cee, skip


def render(body, fails, adv, cee, skip):
    out = []
    for w in warnings:
        out.append(f"!! PROSE LINT WARNING: {w}")
    if not fails and not adv:
        q = len(QUOTE_RE.findall(body))
        out.append(f"PROSE LINT: clean — {len(body):,} chars, {q} quoted lines.")
    else:
        for f in fails:
            loc = f"L{f['line']}" if f["line"] else "  "
            out.append(f"{loc} FAIL {f['id']}  {f['quote']}")
            out.append(f"       [{f['owner']}]")
        for a in adv:
            out.append(f"   ?  {a['id']}  {a['quote']}")
    if skip:
        out.append(f"   {len(skip)} rule(s) suppressed by lint-ok: {', '.join(sorted(skip))}")
    out += cee

    if len(out) > MAX_REPORT_LINES or len("\n".join(out)) > MAX_REPORT_BYTES:
        head = out[: MAX_REPORT_LINES - 1]
        out = head + [f"   …report capped ({len(fails)} FAIL, {len(adv)} advisory total)"]
    return "\n".join(out)


# --------------------------------------------------------------------------
# Selftest
# --------------------------------------------------------------------------
# Clean, unique filler prose for the size-ceiling regression (test 4 below).
# Deliberately free of every Tier-A/B trigger pattern (no gloss-clause, no
# em-dash appositives, no filter-words, no "the way X", no clock-dissolve
# phrases, no repeated 4-grams) so the ONLY new fail it can introduce is
# size-ceiling itself.
_FILLER = (
    "He didn't answer the question the moment he meant to. Voss called time from the "
    "front of the room, and stations began breaking down in the same unhurried order "
    "every session ended in: flasks capped, burners cut, benches wiped clean. Sable "
    "closed her notebook without marking the page. \"Think about it before Thursday,\" "
    "she said, and left before he could ask why Thursday mattered to her at all. He "
    "stayed at the bench a moment longer, turning the stopper of his own flask between "
    "two fingers, listening to the room empty out one pair of footsteps at a time. "
    "Outside, the corridor smelled of solvent and rain that hadn't started yet. Two "
    "second-years argued over a locker combination near the stairs, and neither one "
    "noticed him pass. He took the long route back to his room, past the noticeboard "
    "where Marsh's list still hung, his own name absent from it, and stood there long "
    "enough to read every entry twice. Fourteen to one. He copied nothing down. At the "
    "desk in his room he opened his own ledger and wrote three lines about the morning, "
    "then crossed out two of them and left the third standing alone on the page."
)


def selftest():
    ok = True
    fixtures = {
        "good": os.path.join(FIXTURES, "ch3b3_good.md"),
        "bad": os.path.join(FIXTURES, "ch3b3_bad.md"),
        "bridge_ok": os.path.join(FIXTURES, "bridge_ok.md"),
        "meta_leak": os.path.join(FIXTURES, "meta_leak.md"),
    }
    missing = [name for name, path in fixtures.items() if not os.path.isfile(path)]
    if missing:
        print(f"SELFTEST: fixtures missing: {', '.join(missing)}", file=sys.stderr)
        return False

    # 1. The known-bad fixture, read as published prose (is_draft=False) —
    #    the Tier-A regex rules must still catch it.
    warnings.clear()
    _, fails, adv, _, _ = lint(fixtures["bad"], want_c=False, beat_type="scene", is_draft=False)
    ids = Counter(f["id"] for f in fails)
    n = sum(ids.values())
    good_enough = ids.get("gloss-clause", 0) >= 3 and ids.get("so-much-as", 0) >= 1 and n >= 4
    print(f"SELFTEST bad : {n} FAIL {dict(ids)} + {len(adv)} advisory "
          f"-> {'PASS' if good_enough else 'FAIL'}")
    ok &= good_enough

    # 2. The known-good fixture, same terms — a rule that fires on it is
    #    wrong; the prose is not.
    warnings.clear()
    _, fails, adv, _, _ = lint(fixtures["good"], want_c=False, beat_type="scene", is_draft=False)
    n = len(fails)
    print(f"SELFTEST good: {n} FAIL {dict(Counter(f['id'] for f in fails))} + {len(adv)} advisory "
          f"-> {'PASS' if n == 0 else 'FAIL'}")
    ok &= n == 0

    # 3. bridge_ok.md at type bridge: 0 FAIL. This is the regression that
    #    proves the length floor is dead — at the old +/-12% band around
    #    ~3,000 chars this ~620-char bridge would have FAILed as "under".
    warnings.clear()
    body, fails, adv, _, _ = lint(fixtures["bridge_ok"], want_c=False, beat_type="bridge", is_draft=True)
    passed = len(fails) == 0
    print(f"SELFTEST bridge_ok: {len(fails)} FAIL {dict(Counter(f['id'] for f in fails))} "
          f"({len(body):,} chars) -> {'PASS' if passed else 'FAIL'}")
    if passed:
        print("   (the retired 2,640-char floor would have blocked this)")
    ok &= passed

    # 4. The good fixture inflated past the scene ceiling: exactly one
    #    size-ceiling FAIL, remedy text says cut.
    warnings.clear()
    inflated = open(fixtures["good"]).read() + "\n\n" + _FILLER
    body, fails, adv, _, _ = lint(inflated, is_text=True, want_c=False, beat_type="scene", is_draft=True)
    ceiling_fails = [f for f in fails if f["id"] == "size-ceiling"]
    passed = len(ceiling_fails) == 1 and "cut" in ceiling_fails[0]["quote"]
    print(f"SELFTEST inflated: {len(body):,} chars, {len(ceiling_fails)} size-ceiling "
          f"({len(fails)} total FAIL) -> {'PASS' if passed else 'FAIL'}")
    ok &= passed

    # 5. meta_leak.md: exactly one meta-leak FAIL.
    warnings.clear()
    _, fails, adv, _, _ = lint(fixtures["meta_leak"], want_c=False, beat_type="scene", is_draft=True)
    leak_fails = [f for f in fails if f["id"] == "meta-leak"]
    passed = len(leak_fails) == 1
    print(f"SELFTEST meta_leak: {len(leak_fails)} meta-leak ({len(fails)} total FAIL) "
          f"-> {'PASS' if passed else 'FAIL'}")
    ok &= passed

    # 5b. B6/B12 regression: META_RE must not fire on the bare English words
    # it used to match unconditionally — "ceiling", "budget", "lint",
    # "obligation" are all ordinary nouns this kit's own dark-academia/noir
    # genre cards actively invite (a ceiling fan, a cut budget, lint on a
    # lapel, "no obligation to explain"). Checked directly against the
    # compiled regex — the false positive was in the CONSTANT, not in lint()'s
    # plumbing around it, so that's the most direct thing to pin down.
    meta_re_false_positives = [
        "There was lint on his lapel.",
        "\"I'm under no obligation to explain,\" she said.",
        "The ceiling fan turned.",
        "\"The department cut my budget,\" she says.",
    ]
    fp_hits = [(t, META_RE.search(t)) for t in meta_re_false_positives]
    passed = all(m is None for _, m in fp_hits)
    print(f"SELFTEST META_RE false-positives (ceiling/budget/lint/obligation as ordinary "
          f"words): {sum(1 for _, m in fp_hits if m)}/4 wrongly matched -> "
          f"{'PASS' if passed else 'FAIL'}")
    if not passed:
        for t, m in fp_hits:
            if m:
                print(f"   wrongly matched {m.group(0)!r} in {t!r}")
    ok &= passed

    # And the real machine strings must still be caught — a regex tightened
    # into silence is as broken as one that over-fires.
    meta_re_true_positives = [
        "Beat 3", "beat type", "chapter plan", "VERDICT: CLEAN", "Chain 2/4", "option 3)",
        "495 over the scene ceiling (2,895/2,400 chars) — cut, do not rewrite",
        "TYPE scene CEILING 2,400 chars of body", "Plan written: budget 4, clock",
        "1 over the budget of 6", "LINT OK — 1,202/2,400 chars", "draft is not lint-clean",
        "OBLIGATION delivered", "OBLIGATION: delivered",
    ]
    tp_hits = [(t, META_RE.search(t)) for t in meta_re_true_positives]
    passed = all(m is not None for _, m in tp_hits)
    print(f"SELFTEST META_RE true-positives (real machine strings still caught): "
          f"{sum(1 for _, m in tp_hits if m)}/{len(tp_hits)} matched -> {'PASS' if passed else 'FAIL'}")
    if not passed:
        for t, m in tp_hits:
            if not m:
                print(f"   failed to match {t!r}")
    ok &= passed

    # 6. A draft missing its <!-- beat: type=... --> header: exactly one
    #    beat-header FAIL.
    warnings.clear()
    headerless = "Silas opened the door. Nothing waited on the other side.\n"
    _, fails, adv, _, _ = lint(headerless, is_text=True, want_c=False, beat_type="scene", is_draft=True)
    header_fails = [f for f in fails if f["id"] == "beat-header"]
    passed = len(header_fails) == 1
    print(f"SELFTEST headerless: {len(header_fails)} beat-header ({len(fails)} total FAIL) "
          f"-> {'PASS' if passed else 'FAIL'}")
    ok &= passed

    # 7/8. Corpus regression, only when a story is active. A corpus regression
    # over zero beats is not a pass — reporting it as one tells the reader a
    # check ran that did not. Say SKIP and stay exit 0, so a fresh clone with
    # no story yet is not a red install.
    warnings.clear()
    story = active_story()
    for w in warnings:
        print(f"!! SELFTEST WARNING: {w}")
    beats = corpus_beats(story) if story else []
    if not beats:
        why = "no active story" if not story else f"no chapter beats in {story}/chapters/"
        print(f"SELFTEST corpus: SKIP ({why}) — no prose to regress against")
        print("SELFTEST ch1-regression: SKIP (no active story)")
    else:
        total = 0
        for fn, title, b in beats:
            f = tier_a(b, set(), is_draft=False)
            total += len(f)
            for x in f:
                print(f"   corpus {fn} {title}: {x['id']}  {x['quote'][:70]}")
        verdict = total <= BASELINE_CORPUS_FAILS
        print(f"SELFTEST corpus: {total} FAIL across {len(beats)} beats vs baseline "
              f"{BASELINE_CORPUS_FAILS} -> {'PASS' if verdict else 'FAIL'}")
        ok &= verdict

        # There is no length floor any more, so re-linting the same corpus as
        # scene drafts must produce zero fails whose id is the retired
        # 'length-band' (it cannot exist — this is a regression guard against
        # it ever coming back) and, informationally, however many beats
        # would now trip the scene size-ceiling (a real, separate check).
        scene_ceiling = beat_sizes(story).get("scene", BEAT_SIZES["scene"])
        over_ceiling = 0
        saw_length_band = False
        for fn, title, b in beats:
            df = tier_a(b, {"beat-header"}, is_draft=True, beat_type="scene", ceiling=scene_ceiling)
            ids = {x["id"] for x in df}
            if "length-band" in ids:
                saw_length_band = True
            if "size-ceiling" in ids:
                over_ceiling += 1
        print(f"SELFTEST corpus-as-draft: 'length-band' id present: {saw_length_band} "
              f"(must be False) · {over_ceiling}/{len(beats)} beats would exceed the "
              f"scene ceiling ({scene_ceiling:,} chars) — informational only, not a FAIL "
              f"-> {'PASS' if not saw_length_band else 'FAIL'}")
        ok &= not saw_length_band

        # The Ch1 regression that matters: the exemplar chapter, cited twice
        # in _exemplars.md, averages 1,747 body chars and would fail every
        # beat under the old floor. Ship nothing if this does not pass.
        ch1 = [(fn, t, b) for fn, t, b in beats if fn == "chapter_1.md"]
        if not ch1:
            print("SELFTEST ch1-regression: SKIP (no chapter_1.md in this story)")
        else:
            bad = []
            for fn, title, b in ch1:
                df = tier_a(
                    b, {"beat-header"}, is_draft=True, beat_type="scene", ceiling=scene_ceiling
                )
                length_related = [x for x in df if x["id"] in ("length-band", "size-ceiling")]
                if length_related:
                    bad.append((title, len(b), [x["id"] for x in length_related]))
            passed = not bad
            print(f"SELFTEST ch1-regression: {len(ch1)} beats, "
                  f"{len(bad)} with a length-related FAIL -> {'PASS' if passed else 'FAIL'}")
            for title, n_chars, rule_ids in bad:
                print(f"   {title}: {n_chars:,} chars, {rule_ids}")
            ok &= passed
    return ok


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("draft", nargs="?")
    ap.add_argument("--hook", action="store_true")
    ap.add_argument(
        "--type", choices=sorted(BEAT_SIZES), default=None,
        help="override beat-type detection (the draft-only checks need a type; "
        "default is the file's own <!-- beat: type=... --> header, else scene)",
    )
    ap.add_argument(
        "--is-draft", action="store_true", dest="force_draft",
        help="force the draft-only checks (beat-header/size-ceiling/meta-leak) "
        "even when the path doesn't end in _draft.md",
    )
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        sys.exit(0 if selftest() else 1)

    if a.hook:
        try:
            payload = json.load(sys.stdin)
        except Exception:
            sys.exit(0)
        p = (payload.get("tool_input") or {}).get("file_path", "")
        if not p or not DRAFT_PATH_RE.search(p) or not os.path.isfile(p):
            sys.exit(0)
        body, fails, adv, cee, skip = lint(p)
        report = render(body, fails, adv, cee, skip)
        # Linted either way, but say so when the draft is off-convention —
        # otherwise the next one lands somewhere this hook may not see.
        if os.path.basename(os.path.dirname(p)) != CONVENTIONAL_DIR:
            report = (
                f"   ?  draft-location  outside {CONVENTIONAL_DIR}/ — "
                f"drafts belong at <story>/{CONVENTIONAL_DIR}/ch<N>_beat<M>_draft.md\n"
            ) + report
        if fails:
            print(report, file=sys.stderr)
            sys.exit(2)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse", "additionalContext": report}}))
        sys.exit(0)

    if not a.draft:
        ap.print_usage(sys.stderr)
        sys.exit(0)

    body, fails, adv, cee, skip = lint(
        a.draft, beat_type=a.type, is_draft=(True if a.force_draft else None)
    )
    print(render(body, fails, adv, cee, skip))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # a broken linter must never block writing
        print(f"!! PROSE LINT ERROR: {type(e).__name__}: {e}", file=sys.stdout)
        sys.exit(0)
