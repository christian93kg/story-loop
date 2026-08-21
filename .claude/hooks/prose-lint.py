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
#   - constants here are the single source of truth; CLAUDE.md points, never restates
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
#   prose-lint.py <draft.md>      report to stdout, exit 0
#   prose-lint.py --hook          PostToolUse: hook JSON on stdin
#   prose-lint.py --brief <draft> emit the second-reader context bundle
#   prose-lint.py --selftest      fixtures + corpus regression
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
FIXTURES = os.path.join(VAULT, ".claude", "hooks", "fixtures")

# The gate's trigger. This is the ONLY thing standing between a draft and the
# chapter log, so it matches on the `_draft.md` suffix ALONE, in any directory.
# It used to also require a literal `scratchpad/` parent, which meant a draft
# written to `_scratch/` or `drafts/` sailed past unlinted and unannounced —
# the exact silent failure the "degrade LOUDLY" contract above forbids. The
# convention is still `<story>/scratchpad/…_draft.md`; a draft outside it is
# linted anyway and told where it should have been.
DRAFT_PATH_RE = re.compile(r"_draft\.md$")
CONVENTIONAL_DIR = "scratchpad"

# Length band: ±12% around the story's `**Response Length**` in master_index.md,
# enforced as a Tier-A FAIL. Widen it if your story's beats legitimately vary in
# length (a 0.20 band on a 3,000-char target passes 2,400–3,600); tighten it to
# hold a hard house length. Set the target itself in master_index.md, not here.
BAND_TOLERANCE = 0.12

# Output-hygiene caps on the rendered report, so a noisy beat cannot blow the
# hook-output budget. Unlike craft-gate.sh's MAX_BYTES these are not empirically
# derived against a threshold — they are just "enough to read at a glance."
MAX_REPORT_BYTES = 2048
MAX_REPORT_LINES = 25

# Corpus-regression baseline: total Tier-A FAILs across all published beats of
# the active story at calibration time. --selftest asserts we never exceed it.
# Raising this number is only ever correct when new prose was published, never
# to make a new PATTERNS entry pass.
#
# Calibrated 2026-07-26 over ~48KB of published prose: 10 hits, each inspected
# by hand, all 10 true positives — real tics that shipped anyway. That is ~1 per
# 4.8KB, and the two most recently audited beats (ch3 B2, B3) score zero, which
# is the gradient you want. Five candidate rules were tightened during this
# calibration because they fired on good prose: "which means" (deduction, not
# verdict), two-item negation lists ("no sound, no visible seam" — concrete
# description), 4-grams repeated twice (deliberate dialogue echo), a comparative
# after the em-dash ("presentable, not more"), and short staccato sentence runs.
# A rule that fires on the known-good fixture is wrong; the prose is not.
BASELINE_CORPUS_FAILS = 10

warnings = []


def warn(msg):
    warnings.append(msg)


# --------------------------------------------------------------------------
# Tier A — FAIL rules.
#
# Every rule mechanises doctrine that already exists in _craft_research/. This
# file invents no craft rules; `owner` names the card that owns each one.
#
# TRIPWIRE: if this list ever exceeds ~15 entries, that is the signal vault
# rule 3 is genuinely being violated — the story has become over-managed and
# the answer is a reset, not entry #16.
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


def strip_meta(text):
    """Reduce a beat block or draft file to prose body. Deterministic; the
    char count it yields is what the length-band check reports."""
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
    m = re.search(r"^active_path:[ \t]*(\S+)", open(ACTIVE).read(), re.M)
    if not m:
        # Matches craft-gate.sh: a blank active_path is a fresh clone, not a
        # fault. Story-specific checks (length band, cross-chapter echo) simply
        # have nothing to run against yet.
        return None
    story = m.group(1).strip().strip("/")
    if not os.path.isdir(os.path.join(VAULT, story)):
        warn(f"active_path '{story}' is not a directory — story-specific checks skipped.")
        return None
    return story


def char_band(story):
    mi = os.path.join(VAULT, story, "master_index.md")
    if not os.path.isfile(mi):
        warn(f"{story}/master_index.md not found — length-band check skipped.")
        return None
    m = re.search(r"\*\*Response Length\*\*:\s*~?\s*([\d,]+)\s*chars", open(mi).read())
    if not m:
        warn("no '**Response Length**: ~N chars' in master_index.md — length-band check skipped.")
        return None
    return int(m.group(1).replace(",", ""))


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


def tier_a(body, band, skip):
    fails = []
    narr = narration_only(body)
    for rule in PATTERNS:
        if rule["id"] in skip:
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

    # length band
    if band and "length-band" not in skip:
        n = len(body)
        lo, hi = int(band * (1 - BAND_TOLERANCE)), int(band * (1 + BAND_TOLERANCE))
        if not (lo <= n <= hi):
            how = "under" if n < lo else "over"
            fails.append(
                dict(
                    id="length-band",
                    line=0,
                    quote=f"{n:,} chars, band {band:,} ({lo:,}–{hi:,}) — {how}"
                    + ("; expand with ambiance/perception, never micro-events" if how == "under" else ""),
                    owner="master_index.md Response Length",
                )
            )

    # three consecutive sentences of near-identical length
    if "sentence-run" not in skip:
        sents = [s for s in sentences(narration_only(body)) if len(words(s)) >= 6]
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
    return fails


def tier_b(body, story, corpus, names, skip):
    adv = []

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
def lint(path_or_text, is_text=False, want_c=True):
    raw = path_or_text if is_text else open(path_or_text).read()
    body = strip_meta(raw)
    skip = suppressed(raw)

    story = active_story()
    band = char_band(story) if story else None
    corpus = corpus_beats(story) if story else []
    names = proper_nouns(story, " ".join(b for _, _, b in corpus)) if story else set()

    fails = tier_a(body, band, skip)
    adv = tier_b(body, story, corpus, names, skip)
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
# Second-reader bundle
# --------------------------------------------------------------------------
def brief(path):
    body, fails, adv, cee, skip = lint(path, want_c=False)
    story = active_story()
    parts = ["=== DRAFT UNDER REVIEW ===", body]
    if story:
        corpus = corpus_beats(story)
        if corpus:
            parts += ["\n=== PREVIOUS BEATS (for cross-beat patterns) ==="]
            for _, t, b in corpus[-3:]:
                parts += [f"--- {t} ---", b]
        # Only the sections that bear on a structural read. The rest of
        # master_index.md is setup boilerplate and would triple the bundle.
        for rel, label, slices in [
            ("_exemplars.md", "STORY EXEMPLARS", None),
            ("STORY_BIBLE.md", "STORY BIBLE", [("Voice & tone", "Why this file exists")]),
            (
                "master_index.md",
                "DIALOGUE & INTERACTION RULES",
                [("### 2. Narrative Style", "### 3. Setting"), ("## Interaction Rules", "## Pre-Game")],
            ),
        ]:
            p = os.path.join(VAULT, story, rel)
            if not os.path.isfile(p):
                continue
            txt = open(p).read()
            if slices:
                cut = []
                for start, end in slices:
                    a = txt.find(start)
                    if a == -1:
                        continue
                    b = txt.find(end, a)
                    cut.append(txt[a : b if b > a else len(txt)])
                txt = "\n".join(cut) if cut else txt
            parts += [f"\n=== {label} ===", txt.strip()]
    if os.path.isfile(SPINE):
        # craft-gate.sh is UserPromptSubmit and does NOT fire for a subagent —
        # the spine must be handed over explicitly or the reader works blind.
        parts += ["\n=== CRAFT SPINE ===", open(SPINE).read()]
        if story:
            mi = os.path.join(VAULT, story, "master_index.md")
            reg = open(mi).read() if os.path.isfile(mi) else ""
            block = reg.split("## House Register")[-1].split("As-needed")[0] if reg else ""
            for slug in re.findall(r"`([a-z-]+)`", block):
                card = os.path.join(CARDS, f"{slug}.card.md")
                if os.path.isfile(card):
                    d = re.search(r"<!-- digest:start -->(.*?)<!-- digest:end -->", open(card).read(), re.S)
                    if d:
                        parts.append(d.group(1).strip())
    parts += ["\n=== LINTER ALREADY FOUND (do not re-report) ===", render(body, fails, adv, [], skip)]
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Selftest
# --------------------------------------------------------------------------
def selftest():
    ok = True
    good = os.path.join(FIXTURES, "ch3b3_good.md")
    bad = os.path.join(FIXTURES, "ch3b3_bad.md")
    if not (os.path.isfile(good) and os.path.isfile(bad)):
        print("SELFTEST: fixtures missing", file=sys.stderr)
        return False

    for label, path, want_fail in (("bad", bad, True), ("good", good, False)):
        warnings.clear()
        body, fails, adv, _, _ = lint(path, want_c=False)
        ids = Counter(f["id"] for f in fails)
        # the length band is a property of the fixture file, not of the tic set
        real = {k: v for k, v in ids.items() if k != "length-band"}
        n = sum(real.values())
        if want_fail:
            good_enough = real.get("gloss-clause", 0) >= 3 and real.get("so-much-as", 0) >= 1 and n >= 4
            print(f"SELFTEST bad : {n} FAIL {dict(real)} + {len(adv)} advisory "
                  f"-> {'PASS' if good_enough else 'FAIL'}")
            ok &= good_enough
        else:
            clean = n == 0
            print(f"SELFTEST good: {n} FAIL {dict(real)} + {len(adv)} advisory "
                  f"-> {'PASS' if clean else 'FAIL'}")
            ok &= clean

    warnings.clear()
    story = active_story()
    for w in warnings:
        print(f"!! SELFTEST WARNING: {w}")

    # A corpus regression over zero beats is not a pass — reporting it as one
    # tells the reader a check ran that did not. Say SKIP and stay exit 0, so a
    # fresh clone with no story yet is not a red install.
    beats = corpus_beats(story) if story else []
    if not beats:
        why = "no active story" if not story else f"no chapter beats in {story}/chapters/"
        print(f"SELFTEST corpus: SKIP ({why}) — no prose to regress against")
    else:
        total = 0
        for fn, title, b in beats:
            f = tier_a(b, None, set())
            total += len(f)
            for x in f:
                print(f"   corpus {fn} {title}: {x['id']}  {x['quote'][:70]}")
        verdict = total <= BASELINE_CORPUS_FAILS
        print(f"SELFTEST corpus: {total} FAIL across {len(beats)} beats vs baseline "
              f"{BASELINE_CORPUS_FAILS} -> {'PASS' if verdict else 'FAIL'}")
        ok &= verdict
    return ok


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("draft", nargs="?")
    ap.add_argument("--hook", action="store_true")
    ap.add_argument("--brief", action="store_true")
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

    if a.brief:
        print(brief(a.draft))
        sys.exit(0)

    body, fails, adv, cee, skip = lint(a.draft)
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
