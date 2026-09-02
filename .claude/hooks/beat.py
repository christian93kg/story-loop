#!/usr/bin/env python3
# beat.py — the story-level half of the gate stack.
#
# prose-lint.py owns the SENTENCE. This file owns the STORY.
#
# WHY THIS EXISTS: forensics on 15 played beats found sentence-level craft
# enforced by a blocking hook and story-level craft enforced by nobody. Beats
# per chapter went 5->6->8->10 against a ~6 target; Ch4 offered the same four
# cardinal points on beats 8, 9 and 10; game_state.md said "Beat 10 of ~6 (well
# over target)" and nothing could act on it. Every stage that depended on the
# model remembering was eventually skipped (second-reader: 7 of 15 beats, none
# after turn 12; per-beat craft log: 0 of 10 in Ch4). So every stage here leaves
# an artifact on disk and the next stage checks for it.
#
# CONTRACT (inherited from craft-gate.sh):
#   - degrade LOUDLY: a missing plan block prints how to write one
#   - a crash must never block play — every error path exits 0 with a visible
#     "!! BEAT.PY ERROR:" line. There are two exceptions: --post's FAIL path,
#     which is exit 2 by design (that is the feedback channel to whoever wrote
#     the file); and --selftest, which must never report green on a crash and
#     so exits 1 on one (see main()'s --selftest branch).
#   - constants here are the single source of truth; CLAUDE.md points, never restates
#
# THRESHOLD NOTE: Claude Code v2.1.257 persists hook stdout to a file above
# 10,000 chars (dQn=1e4), leaving only a 2,000-char preview inline. craft-gate.sh
# used to claim ~24KB. MAX_BYTES=8200 therefore has ~1,800 chars of headroom,
# not ~16KB. Do not raise it on the old reasoning.
#
# SINGLE SESSION ASSUMPTION: the ledger is one JSON file with no locking. Two
# concurrent Claude Code sessions in the same story tree will corrupt the chain.
#
# WHAT IT DELIBERATELY DOES NOT DO: judge prose. Obligation-met, clock-intact,
# menu-distinctness and tic mutation are judgment calls and belong to
# .claude/agents/second-reader.md.
#
# STATUS OF THIS FILE (2026-09-02, story-loop v2 build, track T3): all four hook
# entry points (--gate/--guard/--post/--meter) are implemented against the
# ledger/plan/brief machinery T2 built. Every GM subcommand (open, reader-brief,
# revise-brief, append, close, rescope, open-chapter, close-chapter, status,
# abort, lint) is real and selftested; --selftest --hooks now drives every row
# of annex §9.3 plus §9.2 items 2/3/5/9 against a scaffolded /tmp story.
#
# NOTE on `closed` vs the Stop meter (read before touching --meter): the GM
# subcommand `beat.py close` (cmd_close, T2) sets ledger["closed"]=True as its
# last act, and the runbook calls it BEFORE the Stop hook fires (step 10, then
# 11). The annex's --meter pseudocode reads "if L is None or L.get('closed'):
# anti-bypass only" and separately has the meter itself "mark closed:true" on
# its own pass — i.e. it was written assuming the METER is the sole setter of
# `closed`. Taken completely literally, the two would fight: a normally
# completed beat would already be closed=True by the time Stop fires, so the
# meter would only ever run the anti-bypass check — which fires whenever the
# shipped message looks like beat prose with a menu, i.e. on every ordinary
# beat. That would deadlock play, which is the one outcome every guard in this
# file exists to prevent. `--meter` below resolves it with one extra signal
# that is already file-truth and costs nothing: when the ledger is `closed`,
# it also checks whether the shipped message actually contains a slice of
# THIS ledger's tracked draft. If it does, this ledger is what was just
# shipped and the full checks run (they should all pass, since the loop was
# followed) before the meter re-stamps `closed` and autologs. If it does not,
# the ledger is stale (a leftover from an earlier turn — e.g. an out-of-band
# "status?" turn where no `beat.py open` ran) and only the anti-bypass check
# applies. See the docstring on `cmd_meter` for the full decision tree.

import argparse
import datetime
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time

# --------------------------------------------------------------------------
# Load prose-lint.py from THIS file's own directory (never the vault, never a
# hardcoded path — the two scripts always ship side by side).
# --------------------------------------------------------------------------
_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_PL_PATH = os.path.join(_HOOKS_DIR, "prose-lint.py")


def _load_prose_lint():
    spec = importlib.util.spec_from_file_location("prose_lint", _PL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    pl = _load_prose_lint()
    _PL_LOAD_ERROR = None
except Exception as e:  # pragma: no cover - degrade loudly, never block
    pl = None
    _PL_LOAD_ERROR = f"{type(e).__name__}: {e}"

# --------------------------------------------------------------------------
# Constants. Single source of truth — CLAUDE.md and docs point here, never
# restate a number.
# --------------------------------------------------------------------------
VAULT = os.environ.get("CLAUDE_PROJECT_DIR", ".")
ACTIVE = os.path.join(VAULT, "ACTIVE_GAME.md")
SPINE = os.path.join(VAULT, "_craft_research", "CRAFT_SPINE.md")
CARDS = os.path.join(VAULT, "_craft_research", "cards")
LINT = _PL_PATH

MAX_BYTES = 8200            # gate budget. craft-gate.sh points here.
METER_MAX_BYTES = 560       # the CHAPTER METER's share of it
BEAT_SIZES = {"bridge": 900, "scene": 2400, "setpiece": 3200, "close": 2600}  # CEILINGS. NO FLOOR.
TAIL_BEATS = 2               # previous beats packed verbatim into the narrator brief
READER_TAIL = 3              # previous beats in the reader bundle (cross-beat patterns)
FORBIDDEN_MENUS = 2          # last N beats' menus pasted into the brief as prohibitions
WATCHLIST_MAX = 8            # lines of _craft_log.md '## Standing watchlist'. A CAP, not a target.
CHARFILE_CHARS = 2200        # per on-stage character sheet (top of file = identity + voice)
READER_FINDING_CAP = 4       # enforced by the parser, not by the prompt
MAX_REVISIONS = 2            # narrator revision cycles before a rule-5 stop
MAX_BLOCKS = 2                # consecutive Stop blocks before everything downgrades to advisory
LEDGER_NAME = ".beat_ledger.json"

# B6/B12 — kept byte-for-byte in sync with prose-lint.py's copy of record
# (this one is only ever used as a fallback, via `_check_meta_leak_chat`'s
# `getattr(pl, "META_RE", None) or META_RE`, when prose-lint.py failed to
# load at all). See prose-lint.py's comment for what changed and why.
META_RE = re.compile(
    r"\bBeat \d|\bbeat type\b|chapter plan|VERDICT|chain \d/\d|\boption \d\)"
    r"|\bsize-ceiling\b|\b(?:bridge|scene|setpiece|close)\s+ceiling\b|\bceiling\b(?=[^\n]{0,40}\bchars?\b)"
    r"|\bbudget\s+(?:of\s+)?\d+\b|\bover[- ]budget\b|\b(?:chapter|beat|char)\s+budget\b|\bbudget:\s*\d+"
    r"|\bprose-lint(?:\.py)?\b|\blint-clean\b|\blint\s+(?:ok|clean)\b|\bnot\s+lint-clean\b"
    r"|(?-i:OBLIGATION)\b|\bthe\s+obligation\b(?=[^\n]{0,30}\bbeat\b)"
    r"|\bsecond-reader\b|\bbeat\.py\b", re.I
)
HEADING_OK_RE = re.compile(r"^\*\*\d+\s*[·—-]\s*.{1,50}\*\*$")
CLOSER_OK_RE = re.compile(r"^\*Chapter \d+ [—-] .{1,60} [—-] ends here\.\*$")

REPEAT_MARKER = "<!-- Repeat the Beat block above for each response. -->"
RECAP_HEADING = "## Chapter recap"

PLAN_RE = re.compile(r"<!--\s*plan:start\b(.*?)\bplan:end\s*-->", re.S)
TURN_RE = re.compile(
    r"^\s*(T\d+)\s*\|\s*(.+?)\s*\|\s*status:\s*(open|delivered|dropped)"
    r"\s*\|\s*earliest:\s*(\d+)\s*\|\s*latest:\s*(\d+)\s*$", re.M
)
_PLAN_FIELDS = {"chapter", "title", "budget", "clock", "turns", "close", "forbidden", "rescope"}

# Fallback copies of the interface prose-lint.py is expected to grow (T1 is
# rewriting it concurrently). Used only via the pl_* wrappers below, and only
# when the live prose-lint.py does not yet expose the real thing.
_FALLBACK_BEAT_HEADER_RE = re.compile(
    r"<!--\s*beat:\s*type=(bridge|scene|setpiece|close)"
    r"(?:\s+obligation=\"([^\"]{1,240})\")?"
    r"(?:\s+onstage=([a-z0-9_,\-]*))?\s*-->", re.I
)
_FALLBACK_MENU_RE = re.compile(r"^\*\*Choices offered:\*\*\s*\n((?:^\d+\.\s.*\n?)+)", re.M)


def _fallback_menu_options(raw):
    m = _FALLBACK_MENU_RE.search(raw)
    if not m:
        return []
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]


warnings = []

# Set True for the duration of --guard/--post/--meter (their stdout contract is
# EXACTLY one JSON blob, or nothing — the harness parses it as JSON). warn()
# below routes to stderr instead of stdout while this is set, so a degraded
# path inside one of those three can never prepend a plain-text line that
# breaks the JSON parse and silently drops a deny/block decision. --gate and
# every GM subcommand leave this False: their stdout IS the human-facing
# report (or, for --gate, text injected verbatim into the model's context),
# and a warning belongs inline in it, exactly as before.
_STDOUT_IS_JSON = False


def warn(msg):
    """Loud, never silent. Every degraded path calls this."""
    warnings.append(msg)
    out = sys.stderr if _STDOUT_IS_JSON else sys.stdout
    print(f"!! BEAT.PY WARNING: {msg}", file=out)


# --------------------------------------------------------------------------
# pl_* wrappers — the shared interface with prose-lint.py, coded defensively
# against the OLD signature (T1 is rewriting it concurrently). Falls back to
# a local equivalent and records the gap rather than crashing.
# --------------------------------------------------------------------------
_PL_FALLBACKS_USED = set()


def _note_fallback(name):
    if name not in _PL_FALLBACKS_USED:
        _PL_FALLBACKS_USED.add(name)


def pl_beat_sizes(story):
    fn = getattr(pl, "beat_sizes", None) if pl else None
    if fn:
        try:
            return fn(story)
        except Exception as e:
            warn(f"pl.beat_sizes({story!r}) raised {e!r} — using local BEAT_SIZES defaults.")
    _note_fallback("beat_sizes")
    return dict(BEAT_SIZES)


def pl_lint(path_or_text, is_text=False, want_c=True, beat_type=None, is_draft=None, prior_menus=None):
    if pl is None:
        return ("", [], [], [], set())
    fn = pl.lint
    try:
        return fn(path_or_text, is_text=is_text, want_c=want_c, beat_type=beat_type,
                   is_draft=is_draft, prior_menus=prior_menus)
    except TypeError:
        pass
    try:
        return fn(path_or_text, is_text=is_text, want_c=want_c, beat_type=beat_type, is_draft=is_draft)
    except TypeError:
        _note_fallback("lint(beat_type/is_draft/prior_menus kwargs)")
        return fn(path_or_text, is_text=is_text, want_c=want_c)


def pl_menu_options(raw):
    fn = getattr(pl, "menu_options", None) if pl else None
    if fn:
        try:
            return fn(raw)
        except Exception:
            pass
    _note_fallback("menu_options")
    return _fallback_menu_options(raw)


def pl_beat_header_re():
    rx = getattr(pl, "BEAT_HEADER_RE", None) if pl else None
    if rx is not None:
        return rx
    _note_fallback("BEAT_HEADER_RE")
    return _FALLBACK_BEAT_HEADER_RE


def pl_strip_meta(text):
    if pl is not None:
        return pl.strip_meta(text)
    _note_fallback("strip_meta")
    return text.strip()


def pl_tier_c(body, corpus, names):
    fn = getattr(pl, "tier_c", None) if pl else None
    if fn:
        try:
            return fn(body, corpus, names)
        except Exception:
            pass
    return []


def pl_render(body, fails, adv, cee, skip):
    fn = getattr(pl, "render", None) if pl else None
    if fn:
        try:
            return fn(body, fails, adv, cee, skip)
        except Exception:
            pass
    lines = [f"FAIL {f.get('id')}  {f.get('quote', '')}" for f in fails]
    return "\n".join(lines) if lines else "PROSE LINT: clean."


def pl_active_story():
    fn = getattr(pl, "active_story", None) if pl else None
    if fn:
        try:
            return fn()
        except Exception:
            pass
    return _local_active_story()


def _local_active_story():
    if not os.path.isfile(ACTIVE):
        warn("ACTIVE_GAME.md not found — cannot resolve the active story.")
        return None
    m = re.search(r"^active_path:[ \t]*(?:[\"'])?(.+?)(?:[\"'])?[ \t]*$", open(ACTIVE).read(), re.M)
    if not m:
        return None
    story = m.group(1).strip().strip("/")
    if not story or not os.path.isdir(os.path.join(VAULT, story)):
        return None
    return story


# --------------------------------------------------------------------------
# Resolution helpers — story / chapter / beat / scratchpad
# --------------------------------------------------------------------------
def resolve_story():
    return pl_active_story()


def story_dir(story):
    return os.path.join(VAULT, story)


def chapter_file(story, n):
    return os.path.join(story_dir(story), "chapters", f"chapter_{n}.md")


def resolve_chapter(story):
    gs = os.path.join(story_dir(story), "game_state.md")
    if not os.path.isfile(gs):
        warn(f"{story}/game_state.md not found — cannot resolve the current chapter.")
        return None
    m = re.search(r"^current_chapter:\s*(\d+)", open(gs).read(), re.M)
    if not m:
        warn(f"{story}/game_state.md has no 'current_chapter:' in its frontmatter.")
        return None
    return int(m.group(1))


def resolve_beat(story, chapter):
    """Beat M = count of '^### Beat' in chapters/chapter_N.md + 1."""
    cf = chapter_file(story, chapter)
    if not os.path.isfile(cf):
        return 1
    return len(re.findall(r"^### Beat", open(cf).read(), re.M)) + 1


def scratchpad_dir(story):
    d = os.path.join(story_dir(story), "scratchpad")
    os.makedirs(d, exist_ok=True)
    return d


def ledger_path(story):
    return os.path.join(scratchpad_dir(story), LEDGER_NAME)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today():
    return datetime.date.today().isoformat()


def sha_norm(text):
    body = pl_strip_meta(text)
    normed = re.sub(r"\s+", " ", body).strip()
    return hashlib.sha256(normed.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------
def new_ledger(story, chapter, beat, beat_type, ceiling, route, player_input,
               obligation, turn_id, npc, brief_path, draft_path):
    return {
        "schema": 1,
        "story": story,
        "session_id": os.environ.get("CLAUDE_SESSION_ID", ""),
        "opened_at": now_iso(),
        "chapter": chapter,
        "beat": beat,
        "beat_type": beat_type,
        "ceiling": ceiling,
        "route": route,
        "player_input": player_input,
        "obligation": obligation,
        "turn_id": turn_id,
        "npc": npc,
        "brief": brief_path,
        "draft": draft_path,
        "reader_brief": None,
        "reader_out": None,
        "draft_sha": None,
        "draft_chars": 0,
        "lint": None,
        "lint_at": None,
        "reader": None,
        "reader_findings": None,
        "reader_flags": {},
        "reader_waived": False,
        "reader_at": None,
        "revisions": 0,
        "revisions_max": MAX_REVISIONS,
        "blocks": 0,
        "last_block": None,
        "closed": False,
        "last_session_id": os.environ.get("CLAUDE_SESSION_ID", ""),
    }


def load_ledger(story):
    p = ledger_path(story)
    if not os.path.isfile(p):
        return None
    try:
        return json.load(open(p))
    except Exception as e:
        warn(f"ledger at {p} is corrupt ({e}) — treating as absent. Run `beat.py abort` to clear it.")
        return None


def save_ledger(story, L):
    p = ledger_path(story)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(L, f, indent=2)
    os.replace(tmp, p)


# --------------------------------------------------------------------------
# Standing digests — the ONE implementation of
#   ACTIVE_GAME.md -> active_path -> master_index.md '## House Register' -> digest
# Must reproduce craft-gate.sh's old shell pipeline byte-for-byte.
# --------------------------------------------------------------------------
def house_register_text(story):
    """Lines strictly between '## House Register' and (the next '## ' heading
    OR a line containing 'as-needed', case-insensitive), exclusive of both
    boundary lines. Mirrors craft-gate.sh's awk state machine exactly."""
    mi = os.path.join(story_dir(story), "master_index.md")
    if not os.path.isfile(mi):
        warn(f"{story}/master_index.md not found — no House Register to parse.")
        return ""
    lines = open(mi).read().split("\n")
    out = []
    inreg = False
    for line in lines:
        low = line.lower()
        if not inreg and low.startswith("## house register"):
            inreg = True
            continue
        if inreg and low.startswith("## "):
            break
        if inreg and "as-needed" in low:
            break
        if inreg:
            out.append(line)
    return "\n".join(out)


def _card_slugs():
    if not os.path.isdir(CARDS):
        return []
    return sorted(
        (f[: -len(".card.md")] for f in os.listdir(CARDS) if f.endswith(".card.md")),
        key=len, reverse=True,  # longest-first so no slug can shadow a longer one it prefixes
    )


def _extract_digest(card_text):
    """Equivalent of `sed -n '/start/,/end/p' | sed '1d;$d'` — the lines
    strictly between the two marker lines, markers matched by substring like
    sed's address form."""
    lines = card_text.split("\n")
    start = end = None
    for i, ln in enumerate(lines):
        if start is None and "<!-- digest:start -->" in ln:
            start = i
            continue
        if start is not None and "<!-- digest:end -->" in ln:
            end = i
            break
    if start is None or end is None:
        return None
    return "\n".join(lines[start + 1:end])


def digests(story):
    """-> list[(slug, digest_text)] in first-occurrence order, matching the
    old craft-gate.sh's `grep -oE "$slugs" | awk '!seen[$0]++'` pipeline."""
    if not story:
        return []
    register = house_register_text(story)
    if not register.strip():
        warn(f"could not parse a standing register from {story}/master_index.md "
             "'## House Register' — nothing to inject.")
        return []
    slugs = _card_slugs()
    if not slugs:
        warn(f"no card files in {CARDS} — no digests available.")
        return []
    pattern = re.compile("|".join(re.escape(s) for s in slugs))
    seen = []
    for line in register.split("\n"):
        for m in pattern.finditer(line):
            if m.group(0) not in seen:
                seen.append(m.group(0))
    out = []
    for slug in seen:
        card = os.path.join(CARDS, f"{slug}.card.md")
        if not os.path.isfile(card):
            warn(f"no card file for standing mode '{slug}' — expected {card}.")
            continue
        d = _extract_digest(open(card).read())
        if d is None:
            warn(f"no digest block in {slug}.card.md — Read _craft_research/cards/{slug}.card.md before prose this turn.")
            continue
        out.append((slug, d))
    return out


# --------------------------------------------------------------------------
# Plan block — parser (§3.5) and writer, GM-only, chapter-file-resident
# --------------------------------------------------------------------------
def sanitize_plan_text(s):
    s = re.sub(r"-{2,}", "-", s)
    s = s.replace(">", ")")
    return s


def _extract_list_block(inner, name, split_pipe):
    lines = inner.split("\n")
    header_re = re.compile(r"^\s*([a-z]+):\s*(.*)$")
    items = []
    in_block = False
    for line in lines:
        hm = header_re.match(line)
        if hm and hm.group(1) in _PLAN_FIELDS:
            if hm.group(1) == name:
                in_block = True
                trailing = hm.group(2).strip()
                if trailing:
                    items.extend(_split_field(trailing, split_pipe))
                continue
            else:
                in_block = False
                continue
        if in_block:
            s = line.strip()
            if not s:
                continue
            items.extend(_split_field(s, split_pipe))
    return items


def _split_field(s, split_pipe):
    if split_pipe:
        return [x.strip() for x in s.split("|") if x.strip()]
    return [s]


def parse_plan(chapter_text):
    """-> dict {chapter,title,budget,clock,turns,close,forbidden,rescope} or
    None with a loud warning. Never raises."""
    m = PLAN_RE.search(chapter_text)
    if not m:
        return None
    inner = m.group(1)
    if "-->" in inner:
        warn("plan block contains a stray '-->' inside it — refusing to parse. "
             "Fix chapters/chapter_N.md's plan block by hand, or rewrite it with "
             "`beat.py open-chapter` / `rescope`.")
        return None
    try:
        def scalar(name, cast=str, required=True):
            mm = re.search(rf"^\s*{name}:\s*(.+?)\s*$", inner, re.M)
            if not mm:
                if required:
                    raise ValueError(f"missing '{name}:' field")
                return None
            return cast(mm.group(1))

        d = {
            "chapter": scalar("chapter", int),
            "title": scalar("title"),
            "budget": scalar("budget", int),
            "clock": scalar("clock"),
            "close": scalar("close"),
        }
        turns = []
        for tm in TURN_RE.finditer(inner):
            turns.append({
                "id": tm.group(1),
                "text": tm.group(2).strip(),
                "status": tm.group(3),
                "earliest": int(tm.group(4)),
                "latest": int(tm.group(5)),
            })
        if not turns:
            raise ValueError("no well-formed 'turns:' lines")
        d["turns"] = turns
        d["forbidden"] = _extract_list_block(inner, "forbidden", split_pipe=True)
        d["rescope"] = _extract_list_block(inner, "rescope", split_pipe=False)
        return d
    except Exception as e:
        warn(f"plan block malformed ({e}) — treating as absent. Never guessed at.")
        return None


def render_plan(d):
    """The writer. Sanitises every free-text field; refuses (returns None,
    warns) if a stray '-->' would survive into the comment."""
    lines = [
        "<!-- plan:start  GM-ONLY. Never quoted, paraphrased, summarised or hinted at in chat.",
        "     Written by beat.py — do not hand-edit.",
        f"chapter: {d['chapter']}",
        f"title: {sanitize_plan_text(d['title'])}",
        f"budget: {d['budget']}",
        f"clock: {sanitize_plan_text(d['clock'])}",
        "turns:",
    ]
    for t in d["turns"]:
        lines.append(
            f"  {t['id']} | {sanitize_plan_text(t['text'])} | status: {t['status']} "
            f"| earliest: {t['earliest']} | latest: {t['latest']}"
        )
    lines.append(f"close: {sanitize_plan_text(d['close'])}")
    lines.append("forbidden:")
    if d.get("forbidden"):
        lines.append("  " + " | ".join(sanitize_plan_text(x) for x in d["forbidden"]))
    lines.append("rescope:")
    for r in d.get("rescope", []):
        lines.append(f"  {sanitize_plan_text(r)}")
    lines.append("plan:end -->")
    block = "\n".join(lines)
    body = block[: -len("plan:end -->")]
    if "-->" in body:
        warn("sanitisation failed to remove a stray '-->' from the plan block — refusing to write it.")
        return None
    return block


def write_plan(story, chapter_n, d):
    """Insert or replace the plan block in chapters/chapter_N.md. Returns the
    rendered block on success, None on refusal (already warned)."""
    block = render_plan(d)
    if block is None:
        return None
    cf = chapter_file(story, chapter_n)
    text = open(cf).read() if os.path.isfile(cf) else ""
    if PLAN_RE.search(text):
        new_text = PLAN_RE.sub(lambda m: block, text, count=1)
    else:
        fm = re.match(r"\A---\n.*?\n---\n", text, re.S)
        if fm:
            insert_at = fm.end()
            new_text = text[:insert_at] + "\n" + block + "\n" + text[insert_at:]
        else:
            new_text = block + "\n\n" + text
    vault_write(story, cf, new_text, mode="overwrite")
    return block


# --------------------------------------------------------------------------
# Vault write transport — obsidian CLI when the tree is an Obsidian vault and
# the CLI is on PATH, else a direct file write. Same switch for append,
# open-chapter, close-chapter, plan rewrites and autolog.
# --------------------------------------------------------------------------
def _obsidian_available():
    return os.path.isdir(os.path.join(VAULT, ".obsidian")) and shutil.which("obsidian") is not None


def _vault_name():
    return os.path.basename(os.path.normpath(VAULT))


def _obsidian_env():
    env = dict(os.environ)
    if not env.get("XDG_RUNTIME_DIR"):
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    return env


# F4: measured against the real vault (a throwaway file in a real story
# folder, real Obsidian app as the CLI's IPC target — see the plan). The
# original transport used the CLI's `create`/`append` subcommands and then
# read the file back ONCE, immediately; the observed failure was that the
# Obsidian app applies a CLI write asynchronously, so that single read can
# see stale content and treat a real success as a failure (8+ loud
# "post-write verification failed" warnings per beat in the live dry run,
# each falling back to a direct write). Two fixes, applied together:
#   1. `_obsidian_write` now goes through `obsidian eval` +
#      `app.vault.adapter.write`/`.append`, both AWAITED — this returns only
#      after the adapter's own write promise resolves, which measured
#      synchronous over 50 trials against the real vault (create/overwrite,
#      append, and back-to-back rapid appends — 0 races). This is the
#      "alternative" the plan names, chosen because it is synchronous BY
#      CONSTRUCTION rather than by observed timing.
#   2. `vault_write`'s own verification no longer trusts a single read: it
#      polls for up to `_POLL_TIMEOUT_S`, so a slower disk or a busier
#      Obsidian instance than this measurement still resolves correctly
#      instead of false-failing into an unnecessary fallback. A genuine
#      timeout still falls back to a direct write (loud), then checks once
#      more after `_POLL_SECOND_CHECK_DELAY_S` in case the CLI's write
#      landed LATE, after the fallback already wrote the same content —
#      and de-duplicates rather than leaving the block doubled.
_POLL_INTERVAL_S = 0.1
_POLL_TIMEOUT_S = 3.0
_POLL_SECOND_CHECK_DELAY_S = 1.5


def _write_matches(path, content, mode):
    """True iff `path` already carries `content` — the tail (append) or the
    whole file (overwrite)."""
    if not os.path.isfile(path):
        return not content.strip() and mode == "overwrite"
    cur = open(path).read()
    if mode == "append":
        probe = content.strip()[:120]
        return bool(probe) and probe in cur
    return cur.strip() == content.strip()


def _poll_for_write(path, content, mode, timeout=_POLL_TIMEOUT_S, interval=_POLL_INTERVAL_S):
    """Poll `path` every `interval` seconds until `content` has landed (by
    `_write_matches`) or `timeout` elapses. -> bool. Pure and offline-
    testable: callers control the file's contents, not this function."""
    deadline = time.time() + timeout
    while True:
        if _write_matches(path, content, mode):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(interval)


def _dedupe_if_doubled(path, content, mode, label=""):
    """After a fallback direct write, the CLI's own (async) write can still
    land LATE and double the block. Append-only: an overwrite can't "double"
    the same way (the second write simply replaces the first). Removes the
    SECOND occurrence and warns loudly; a no-op if there is only one."""
    if mode != "append" or not os.path.isfile(path):
        return
    needle = content.strip()
    if not needle:
        return
    cur = open(path).read()
    idx1 = cur.find(needle)
    if idx1 == -1:
        return
    idx2 = cur.find(needle, idx1 + len(needle))
    if idx2 == -1:
        return
    deduped = cur[:idx2] + cur[idx2 + len(needle):]
    with open(path, "w") as f:
        f.write(deduped)
    warn(f"{label or os.path.relpath(path, VAULT)}: the Obsidian CLI write landed late, after "
         "the fallback direct write had already written the same block — removed the duplicate.")


def vault_write(story, path, content, mode="overwrite"):
    """mode: 'overwrite' (full replace) or 'append' (add to end)."""
    rel = os.path.relpath(path, VAULT)
    if _obsidian_available():
        try:
            _obsidian_write(rel, content, mode)
        except Exception as e:
            warn(f"obsidian CLI write to {rel} failed ({e}) — falling back to a direct file write.")
            _direct_write(path, content, mode)
            return
        if _poll_for_write(path, content, mode):
            return
        warn(f"obsidian CLI write to {rel} reported success but did not verify within "
             f"{_POLL_TIMEOUT_S}s — falling back to a direct file write.")
        _direct_write(path, content, mode)
        time.sleep(_POLL_SECOND_CHECK_DELAY_S)
        _dedupe_if_doubled(path, content, mode, label=rel)
        return
    _direct_write(path, content, mode)


def _direct_write(path, content, mode):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if mode == "append":
        with open(path, "a") as f:
            f.write(content)
    else:
        with open(path, "w") as f:
            f.write(content)


def _obsidian_write(rel_path, content, mode):
    env = _obsidian_env()
    vault_name = _vault_name()
    # chunk anything over 30KB — the CLI's own transport limit
    chunks = [content[i:i + 30000] for i in range(0, len(content), 30000)] or [""]
    for i, chunk in enumerate(chunks):
        js_path = json.dumps(rel_path)
        js_chunk = json.dumps(chunk)
        if mode == "overwrite" and i == 0:
            call = f"app.vault.adapter.write({js_path}, {js_chunk})"
        else:
            call = f"app.vault.adapter.append({js_path}, {js_chunk})"
        # AWAITED — this is what makes the call return only after the write
        # has actually landed, instead of after the CLI merely queues it.
        code = f"(async()=>{{await {call}; return (await app.vault.adapter.stat({js_path})).size}})()"
        argv = ["obsidian", f"vault={vault_name}", "eval", f"code={code}"]
        r = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError(f"obsidian CLI exit {r.returncode}: {r.stderr.strip()[:200]}")


# --------------------------------------------------------------------------
# Chapter meter — annex shape, GM-only, ≤ METER_MAX_BYTES
# --------------------------------------------------------------------------
def _elide(s, n=52):
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def chain_summary(ledger):
    if not ledger or ledger.get("closed"):
        return "no open beat."
    step = "beat.py open"
    if ledger.get("draft_sha") is None:
        step = "Agent(narrator) on the brief"
        n = 1
    elif ledger.get("lint") != "ok":
        step = "fix the draft (lint not clean)"
        n = 1
    elif ledger.get("reader") is None and not ledger.get("reader_waived"):
        step = "beat.py reader-brief, then Agent(second-reader)"
        n = 2
    else:
        step = "ship, then beat.py append"
        n = 3
    return (f"{n}/4 · ch{ledger.get('chapter')} b{ledger.get('beat')} "
            f"{ledger.get('beat_type')} · next: {step}")


def chapter_meter(story, N, M, plan, ledger):
    if plan is None:
        text = (
            f"=== CHAPTER METER — no plan block in {story}/chapters/chapter_{N}.md.\n"
            "Open the chapter before writing a beat:\n"
            f"  beat.py open-chapter --n {N} --title \"…\" --budget 6 --clock \"<a real in-fiction deadline\n"
            "  with a consequence>\"   (it refuses without a clock — that is deliberate)\n"
            "Then write 2-4 turns into the plan block. GM-only; the player never sees it. ===\n"
        )
        return text
    budget = plan["budget"]
    open_turns = [t for t in plan["turns"] if t["status"] == "open"]
    open_str = " · ".join(
        f"{t['id']} {_elide(t['text'])} (due b{t['latest']})" for t in open_turns
    ) or "none"
    lines = [
        "=== CHAPTER METER — GM-ONLY. Never quote, paraphrase or surface any of this. ===",
        f"{story} · Ch{N} \"{plan['title']}\" · next beat {M} of budget {budget}",
        f"Clock: {plan['clock']}",
        f"Open: {open_str}",
        f"Chain: {chain_summary(ledger)}",
    ]
    if M > budget:
        lines.append(
            "AT BUDGET — the next beat is type=close: land the remaining turn, then "
            "time-skip out. Do not ask the player whether to close."
        )
    lines.append("You are the GM. You do not write beat prose. Runbook: CLAUDE.md § The beat loop.")
    lines.append("=== END METER ===")
    text = "\n".join(lines) + "\n"
    if len(text.encode("utf-8")) > METER_MAX_BYTES:
        warn(f"chapter meter is {len(text.encode('utf-8'))} B, over METER_MAX_BYTES={METER_MAX_BYTES} "
             "— trimming the Open: line.")
        lines[3] = "Open: " + _elide(open_str, 40)
        text = "\n".join(lines) + "\n"
    if len(text.encode("utf-8")) > METER_MAX_BYTES:
        # Trimming Open: alone doesn't help when the OVERAGE is in a long
        # `--clock` (nothing caps its length at open-chapter) — elide it too
        # rather than shipping an over-budget meter as-is.
        warn(f"chapter meter is still {len(text.encode('utf-8'))} B after trimming Open: "
             f"(over METER_MAX_BYTES={METER_MAX_BYTES}) — trimming the Clock: line too.")
        lines[2] = "Clock: " + _elide(plan["clock"], 200)
        text = "\n".join(lines) + "\n"
    return text


# --------------------------------------------------------------------------
# Obligation selection — deterministic, per annex §2.1 "open"
# --------------------------------------------------------------------------
def select_obligation(plan, M):
    """-> (turn_or_None, forced_close: bool, implicit_rescope_note_or_None)"""
    if plan is None:
        return None, False, None
    if M > plan["budget"]:
        return None, True, None
    open_turns = [t for t in plan["turns"] if t["status"] == "open"]
    if not open_turns:
        return None, True, None
    candidates = [t for t in open_turns if t["earliest"] <= M]
    if candidates:
        chosen = min(candidates, key=lambda t: (t["latest"], t["id"]))
        return chosen, False, None
    chosen = min(open_turns, key=lambda t: t["earliest"])
    note = f"{today()} | beat {M} pulled {chosen['id']} forward from earliest {chosen['earliest']}."
    return chosen, False, note


# --------------------------------------------------------------------------
# Narrator brief / reader bundle builders
# --------------------------------------------------------------------------
def _read_or_note(path, label):
    if os.path.isfile(path):
        return open(path).read().strip()
    return f"({label} not found at {path})"


def _slice_between(text, start_marker, end_marker):
    a = text.find(start_marker)
    if a == -1:
        return ""
    b = text.find(end_marker, a + len(start_marker)) if end_marker else -1
    return text[a: b if b != -1 else len(text)].strip()


def standing_watchlist(story):
    path = os.path.join(story_dir(story), "_craft_log.md")
    if not os.path.isfile(path):
        return "(no _craft_log.md yet — no watchlist)"
    text = open(path).read()
    m = re.search(r"^## Standing watchlist\s*$", text, re.M)
    if not m:
        return "(no '## Standing watchlist' section yet)"
    rest = text[m.end():]
    nm = re.search(r"^## ", rest, re.M)
    section = rest[: nm.start() if nm else len(rest)]
    lines = [ln for ln in section.split("\n") if ln.strip().startswith("-")]
    if len(lines) > WATCHLIST_MAX:
        lines = lines[:WATCHLIST_MAX]
    return "\n".join(lines) if lines else "(watchlist section is empty — nothing caught twice yet)"


def voice_and_interaction_rules(story):
    mi = os.path.join(story_dir(story), "master_index.md")
    if not os.path.isfile(mi):
        return "(master_index.md not found)"
    txt = open(mi).read()
    parts = []
    a = _slice_between(txt, "### 2. Narrative Style", "### 3. Setting")
    if a:
        parts.append(a)
    b = _slice_between(txt, "## Interaction Rules", "## Pre-Game")
    if b:
        parts.append(b)
    return "\n\n".join(parts) if parts else txt.strip()


_RESUME_MACHINE_LINE_RE = re.compile(r"^\s*-\s*\*\*(Position|Plan):?\*\*.*$\n?", re.M)


def resume_block(story):
    """The '## Resume' section, for the NARRATOR's own cold-start read only.
    `**Position:**` and `**Plan:**` are dropped: Position is the runbook's own
    Stop-meter-read line (pure GM/machine bookkeeping, not narrator context) and
    Plan echoes the turn roster's ids/status/budget — machinery the plan block
    itself is never allowed into any writer-facing text. `**Clock:**` stays; the
    narrator is supposed to see the live deadline."""
    gs = os.path.join(story_dir(story), "game_state.md")
    if not os.path.isfile(gs):
        return "(game_state.md not found)"
    section = _slice_between(open(gs).read(), "## Resume", "## Setup Decisions")
    return _RESUME_MACHINE_LINE_RE.sub("", section)


def raw_beats(story, chapter, n):
    """Last n '### Beat' blocks, RAW (prose + menu, header comment intact)."""
    cf = chapter_file(story, chapter)
    if not os.path.isfile(cf):
        return []
    text = open(cf).read()
    parts = re.split(r"(?m)^(### Beat[^\n]*)$", text)
    blocks = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1]
        # trim at the next '---' template separator or EOF
        cut = re.search(r"\n---\n", body)
        body = body[: cut.start()] if cut else body
        blocks.append((title, body.strip()))
    return blocks[-n:] if n else blocks


# F3: on-stage derivation used to be a bare `\b[A-Z][a-z]{2,}\b` scan over the
# last two beats' raw text (derive_npc, retired) — it matched "Bell" (from
# "Bell Street"), "Buy" (from "Buy a stick"), "Choices" (from the menu
# marker), "Court" (from "Merchant Court"), fired a loud "--npc 'X' matched no
# file" warning for each, and STILL never put the player character's own
# sheet in the brief (nothing derived it; it was only ever added via an
# explicit --npc). The roster below is built from the story's actual
# characters/*.md files — never from capitalised tokens in prose — and the
# player character is unconditionally on stage, first, every beat.
_NAME_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
PLAYER_CHARACTER_SLUG = "player_character"


def _character_roster(story):
    """-> list of {slug, path, names(set, lowercase)} for every
    characters/*.md file NOT starting with '_' (that prefix is the sheet
    template / non-canon scratch convention used elsewhere in this kit).
    `names` holds match candidates: the '# Title' heading, any '**Name**:'
    or 'name:' field (frontmatter or body), and the individual words of
    each — so "Mair Tully" matches on either "Mair Tully" or bare "Mair"."""
    cdir = os.path.join(story_dir(story), "characters")
    roster = []
    if not os.path.isdir(cdir):
        return roster
    for fn in sorted(os.listdir(cdir)):
        if not fn.endswith(".md") or fn.startswith("_"):
            continue
        slug = fn[:-len(".md")]
        path = os.path.join(cdir, fn)
        try:
            text = open(path).read()
        except Exception:
            continue
        names = set()

        def _add(full):
            full = full.strip().strip("\"'")
            if not full:
                return
            names.add(full.lower())
            for tok in _NAME_TOKEN_RE.findall(full):
                if len(tok) > 2:
                    names.add(tok.lower())

        hm = re.search(r"^#\s+(.+)$", text, re.M)
        if hm:
            _add(hm.group(1))
        for m in re.finditer(r"^\*\*Name\*\*:\s*(.+)$", text, re.M | re.I):
            _add(m.group(1))
        for m in re.finditer(r"^name:\s*(.+)$", text, re.M | re.I):
            _add(m.group(1))
        roster.append({"slug": slug, "path": path, "names": names})
    return roster


def _names_on_stage(roster, text):
    """-> list of slugs whose title/Name/name (or a first-token of any of
    those) appears, case-insensitive and word-boundary, in `text`."""
    text_l = text.lower()
    hits = []
    for c in roster:
        for name in c["names"]:
            if name and re.search(r"\b" + re.escape(name) + r"\b", text_l):
                hits.append(c["slug"])
                break
    return hits


def characters_on_stage(story, explicit_npc, player_input="", tail_text=""):
    """-> (brief_text, resolved_slugs). `player_character.md` is ALWAYS
    included first if it exists — never derived, never "off stage".
    Everything else on the roster is matched by name against the player's
    input plus the last TAIL_BEATS beats of prose (never a bare capitalised-
    token scan — see the retired `derive_npc` note above). `explicit_npc`
    (from `--npc`) is added regardless of whether the text matched, and
    still warns loudly — this file's own "degrade loudly" contract — when a
    requested slug matches no character file at all."""
    roster = _character_roster(story)
    by_slug = {c["slug"]: c for c in roster}
    resolved = []

    pc_path = os.path.join(story_dir(story), "characters", f"{PLAYER_CHARACTER_SLUG}.md")
    if os.path.isfile(pc_path):
        resolved.append(PLAYER_CHARACTER_SLUG)

    scan_text = f"{player_input}\n{tail_text}"
    for slug in _names_on_stage(roster, scan_text):
        if slug not in resolved:
            resolved.append(slug)

    for raw_name in explicit_npc:
        name = raw_name.strip()
        if not name:
            continue
        slug = name if name in by_slug else (name.lower() if name.lower() in by_slug else None)
        if slug is None:
            # Degrade LOUDLY (the file's own contract) — a silently-skipped
            # --npc used to mean the narrator wrote that character's dialogue
            # with no sheet in the brief at all, and nothing said so.
            warn(f"--npc '{raw_name}' matched no file in {story}/characters/ — that "
                 "character's sheet is NOT in the brief this beat.")
            continue
        if slug not in resolved:
            resolved.append(slug)

    parts = []
    for slug in resolved:
        c = by_slug.get(slug)
        path = c["path"] if c else os.path.join(story_dir(story), "characters", f"{slug}.md")
        if os.path.isfile(path):
            txt = open(path).read()[:CHARFILE_CHARS]
            parts.append(f"--- {slug} ---\n{txt}")
    text_out = "\n\n".join(parts) if parts else "(no named on-stage characters this beat)"
    return text_out, resolved


def forbidden_menus(story, chapter, plan):
    blocks = raw_beats(story, chapter, FORBIDDEN_MENUS)
    opts = []
    for _, raw in blocks:
        opts += pl_menu_options(raw)
    if plan and plan.get("forbidden"):
        opts += plan["forbidden"]
    seen, out = set(), []
    for o in opts:
        if o not in seen:
            seen.add(o)
            out.append(o)
    return out


def build_brief(story, N, M, beat_type, ceiling, clock, obligation_text, player_input,
                 explicit_npc, route, brief_path):
    """-> (brief_text, resolved_npc_slugs). `explicit_npc` is the raw
    --npc list only (never a capitalised-token derivation — see F3 note at
    `characters_on_stage`); the resolved slugs it returns are what actually
    went into the brief and are what the caller should record on the
    ledger and print as ONSTAGE."""
    digest_blocks = digests(story)
    digest_text = "\n\n".join(d for _, d in digest_blocks) if digest_blocks else "(no standing digests found)"
    last_beats = raw_beats(story, N, TAIL_BEATS)
    last_beats_text = "\n\n".join(f"--- {t} ---\n{b}" for t, b in last_beats) or "(chapter has no prior beats)"
    forbidden = forbidden_menus(story, N, None)
    forbidden_text = "\n".join(f"- {o}" for o in forbidden) or "(none offered yet)"
    char_text, npc = characters_on_stage(story, explicit_npc, player_input, last_beats_text)

    parts = []
    parts.append("=== CRAFT SPINE ===\n" + _read_or_note(SPINE, "CRAFT_SPINE.md"))
    parts.append("=== STANDING CRAFT DIGESTS ===\n" + digest_text)
    parts.append(
        "=== STANDING WATCHLIST — tics this story has already been caught doing, AND the "
        "shape each one came back wearing after it was fixed. These mutate. Read your own "
        "draft against the MOVE, not the phrasing. ===\n" + standing_watchlist(story)
    )
    parts.append("=== STORY BIBLE ===\n" + _read_or_note(
        os.path.join(story_dir(story), "STORY_BIBLE.md"), "STORY_BIBLE.md"))
    parts.append("=== EXEMPLARS — what \"right\" sounds like here ===\n" + _read_or_note(
        os.path.join(story_dir(story), "_exemplars.md"), "_exemplars.md"))
    parts.append("=== VOICE & INTERACTION RULES ===\n" + voice_and_interaction_rules(story))
    parts.append("=== CHARACTERS ON STAGE ===\n" + char_text)
    parts.append("=== WHERE WE ARE ===\n" + resume_block(story))
    parts.append("=== THE LAST 2 BEATS, VERBATIM ===\n" + last_beats_text)
    parts.append(
        "=== MENUS ALREADY OFFERED — yours must not be these cardinal points again ===\n"
        + forbidden_text
    )
    clock_note = (
        f"  The clock: {clock}\n"
        "    Never widen this, soften it, or write a line that dissolves it (\"plenty of time\",\n"
        "    \"no rush\", \"days away\"). If the player's action would consume more time than\n"
        "    remains, the deadline arrives.\n"
        if clock else "  No live clock is recorded for this chapter.\n"
    )
    this_beat = (
        f"=== THIS BEAT ===\n"
        f"  Beat type: {beat_type}        HARD CEILING: {ceiling:,} chars of prose body.\n"
        "    A CEILING, NOT A TARGET. There is no minimum and there never will be again.\n"
        f"{clock_note}"
        f"  What this beat must deliver: {obligation_text}\n"
        "    When this beat ends that fact must be different. If it is not, you failed.\n"
        f"  The player did: \"{player_input}\"\n"
        f"  Routing note: {route}.\n"
    )
    parts.append(this_beat.strip())
    onstage = ",".join(npc)
    parts.append(
        "=== OUTPUT CONTRACT — the file skeleton is mandatory, exactly this shape ===\n"
        f"  <!-- beat: type={beat_type} obligation=\"{obligation_text[:200]}\" onstage={onstage} -->\n"
        "  <prose>\n"
        "  **Choices offered:**\n"
        "  1. …\n"
        "  2. …\n"
        "  3. …\n"
        "  Line 1 must be that HTML comment, exactly. The menu must be introduced by the "
        "literal\n  line `**Choices offered:**` — the machinery reads that marker and cannot "
        "see a menu\n  without it. No headings, no labels, no commentary, no character counts.\n"
        "  At a climax, revelation or ambush: write `**Choices offered:** None — <one clause "
        "why>`\n  and no numbered list.\n"
        f"  Write to: {brief_path.replace('_brief.md', '_draft.md')}"
    )
    parts.append("=== END BRIEF — write the beat now. ===")
    return "\n\n".join(parts), npc


def build_reader_bundle(story, N, M, beat_type, ceiling, clock, obligation_text, draft_path):
    draft_raw = open(draft_path).read()
    body = pl_strip_meta(draft_raw)
    menu = "\n".join(pl_menu_options(draft_raw)) or "(none)"
    last_beats = raw_beats(story, N, READER_TAIL)
    last_beats_text = "\n\n".join(f"--- {t} ---\n{b}" for t, b in last_beats) or "(no prior beats)"
    prior_menu_lists = [pl_menu_options(raw) for _, raw in raw_beats(story, N, FORBIDDEN_MENUS)]
    prev_menus = [o for lst in prior_menu_lists for o in lst]
    prev_menus_text = "\n".join(f"- {o}" for o in prev_menus) or "(none)"
    _, fails, adv, cee, skip = pl_lint(draft_path, beat_type=beat_type, is_draft=True,
                                        prior_menus=prior_menu_lists)
    linter_text = pl_render(body, fails, adv, [], skip)
    dossier = pl_tier_c(body, [], set())

    reader_out = draft_path.replace("_draft.md", "_reader.md")
    parts = [
        f"=== BEAT UNDER REVIEW — Chapter {N}, beat {M}, type {beat_type}, "
        f"{len(body):,}/{ceiling:,} chars ===",
        f"OBLIGATION  {obligation_text}",
        f"CLOCK       {clock or '(none recorded)'}",
        "=== DRAFT ===\n" + draft_raw.strip(),
        "=== MENU IN THIS DRAFT ===\n" + menu,
        "=== MENUS OF THE LAST 2 BEATS ===\n" + prev_menus_text,
        "=== PREVIOUS BEATS (cross-beat patterns) ===\n" + last_beats_text,
        "=== DIALOGUE DOSSIER ===\n" + ("\n".join(dossier) if dossier else "(no quoted dialogue this beat)"),
        "=== LINTER ALREADY FOUND (do not re-report) ===\n" + linter_text,
        f"=== YOUR OUTPUT FILE === {reader_out}",
    ]
    return "\n\n".join(parts), reader_out


# --------------------------------------------------------------------------
# parse_verdict — machine-parsed second-reader output
#
# A3: these used to be `$`-anchored with zero tolerance for a trailing space,
# a trailing period, a bold (`**LABEL:**`) marker, or CRLF line endings — all
# four are things a model plausibly does to output that is otherwise exactly
# right, and each one used to reject the whole file with "missing required
# line(s)" even though the line was RIGHT THERE, just not byte-for-byte in
# the one shape the regex accepted. `\**LABEL:?\**` tolerates the bold
# wrapping; the lazy `[^\n]*?` + optional `\.?` before `$` tolerates a
# trailing period or spaces; parse_verdict() itself normalises CRLF before
# any of these run.
# --------------------------------------------------------------------------
_VERDICT_RE = re.compile(r"^\s*\**VERDICT:?\**\s*(CLEAN|(\d+)\s*FINDING)", re.M)
_OBLIGATION_RE = re.compile(r"^\s*\**OBLIGATION:?\**\s*(delivered|not delivered\b[^\n]*?)\.?\s*$", re.M | re.I)
_CLOCK_RE = re.compile(r"^\s*\**CLOCK:?\**\s*(intact|widened\b[^\n]*?|dissolved\b[^\n]*?)\.?\s*$", re.M | re.I)
_MENU_RE = re.compile(r"^\s*\**MENU:?\**\s*(\d+\s*distinct|none\b[^\n]*?|repeat\b[^\n]*?)\.?\s*$", re.M | re.I)
_FINDING_RE = re.compile(r"^\[F(\d+)\]", re.M)

# Loose "is a line for this label present at all" probes, used ONLY to tell a
# genuinely MISSING line apart from one that IS present but failed to parse
# (e.g. the agent pasted the brief's aligned `label: A | label: B` alternation
# shape verbatim instead of picking one) — so the error names the right fix.
_LOOSE_LABEL_RE = {
    "OBLIGATION": re.compile(r"^\s*\**OBLIGATION:?\**.*$", re.M | re.I),
    "CLOCK": re.compile(r"^\s*\**CLOCK:?\**.*$", re.M | re.I),
    "MENU": re.compile(r"^\s*\**MENU:?\**.*$", re.M | re.I),
}
_EXPECTED_SHAPE = {
    "OBLIGATION": "'OBLIGATION: delivered' or 'OBLIGATION: not delivered — <one clause>' (pick ONE, "
                  "not the brief's aligned alternation shape)",
    "CLOCK": "'CLOCK: intact', 'CLOCK: widened — <clause>', or 'CLOCK: dissolved — <clause>' (pick ONE)",
    "MENU": "'MENU: N distinct', 'MENU: none (climax)', or 'MENU: repeat — <which>' (pick ONE)",
}


def parse_verdict(text):
    """-> (ok: bool, parsed: dict, err: str)"""
    text = text.replace("\r\n", "\n")
    vm = _VERDICT_RE.search(text)
    if not vm:
        return False, {}, "!! BEAT.PY: verdict file has no 'VERDICT: CLEAN|N FINDING(S)' line 1."
    clean = vm.group(1) == "CLEAN"
    declared_n = int(vm.group(2)) if vm.group(2) else 0
    om = _OBLIGATION_RE.search(text)
    cm = _CLOCK_RE.search(text)
    mm = _MENU_RE.search(text)
    if not (om and cm and mm):
        missing, unparseable = [], []
        for name, m in (("OBLIGATION", om), ("CLOCK", cm), ("MENU", mm)):
            if m:
                continue
            loose = _LOOSE_LABEL_RE[name].search(text)
            if loose:
                unparseable.append(f"{name} line present but unparseable: {loose.group(0).strip()!r} "
                                    f"— expected {_EXPECTED_SHAPE[name]}.")
            else:
                missing.append(name)
        parts = []
        if missing:
            parts.append(f"missing required line(s): {', '.join(missing)}.")
        parts.extend(unparseable)
        return False, {}, "!! BEAT.PY: verdict " + " ".join(parts)
    finding_ids = _FINDING_RE.findall(text)
    n_found = len(finding_ids)
    if n_found > READER_FINDING_CAP:
        return False, {}, (f"!! BEAT.PY: verdict declares {n_found} findings, cap is "
                            f"{READER_FINDING_CAP}. Cut to the ones you'd defend to the author's face.")
    if not clean and n_found != declared_n:
        return False, {}, (f"!! BEAT.PY: verdict line 1 says {declared_n} finding(s) but "
                            f"{n_found} [Fn] block(s) are present.")
    flags = {
        "obligation": om.group(1).strip().lower(),
        "clock": cm.group(1).strip().lower(),
        "menu": mm.group(1).strip().lower(),
    }
    auto_promoted = not (
        flags["obligation"].startswith("delivered")
        and flags["clock"].startswith("intact")
        and not flags["menu"].startswith("repeat")
    )
    parsed = {
        "clean": clean and not auto_promoted,
        "n": n_found,
        "flags": flags,
        "auto_promoted": auto_promoted,
    }
    return True, parsed, ""


# --------------------------------------------------------------------------
# GM subcommands
# --------------------------------------------------------------------------
def _require_story():
    story = resolve_story()
    if not story:
        print("!! BEAT.PY: no active story (ACTIVE_GAME.md active_path unset or unresolved).")
        sys.exit(0)
    return story


def _require_chapter(story):
    n = resolve_chapter(story)
    if n is None:
        print(f"!! BEAT.PY: cannot resolve current_chapter for {story}.")
        sys.exit(0)
    return n


def cmd_open(args):
    story = _require_story()
    N = _require_chapter(story)
    M = resolve_beat(story, N)
    cf = chapter_file(story, N)
    plan = parse_plan(open(cf).read()) if os.path.isfile(cf) else None

    turn, forced_close, implicit_note = select_obligation(plan, M)
    if plan and implicit_note:
        plan["rescope"] = plan.get("rescope", []) + [implicit_note]
        write_plan(story, N, plan)

    beat_type = args.type or "scene"
    obligation_text = args.obligation
    turn_id = None
    if turn is not None:
        turn_id = turn["id"]
        if obligation_text is None:
            obligation_text = turn["text"]
    if args.obligation:
        # explicit override — recorded as an implicit rescope note
        if plan:
            note = f"{today()} | beat {M} obligation overridden by --obligation: {args.obligation}"
            plan["rescope"] = plan.get("rescope", []) + [note]
            write_plan(story, N, plan)
    if forced_close:
        beat_type = "close"
    if obligation_text is None:
        obligation_text = "(no plan block — GM has not run `open-chapter` yet; write an ordinary scene)"

    # F3: only the EXPLICIT --npc list goes in; characters_on_stage (inside
    # build_brief) resolves the actual on-stage roster from characters/*.md
    # by name-match against the player's input and the last beats' text —
    # never a bare capitalised-token scan over raw prose. It also always
    # puts player_character.md first, unconditionally.
    explicit_npc = [x.strip() for x in args.npc.split(",") if x.strip()] if args.npc else []
    ceiling = pl_beat_sizes(story).get(beat_type, BEAT_SIZES[beat_type])
    route = args.route or ("menu-pick" if turn else "free text")
    clock = plan["clock"] if plan else None

    sp = scratchpad_dir(story)
    brief_path = os.path.join(sp, f"ch{N}_beat{M}_brief.md")
    draft_path = os.path.join(sp, f"ch{N}_beat{M}_draft.md")

    brief_text, npc = build_brief(story, N, M, beat_type, ceiling, clock, obligation_text,
                                   args.input or "", explicit_npc, route, brief_path)
    with open(brief_path, "w") as f:
        f.write(brief_text)

    L = new_ledger(story, N, M, beat_type, ceiling, route, args.input or "",
                    obligation_text, turn_id, npc, brief_path, draft_path)
    # F1: session ownership. `--guard` writes .beat_owner with the calling
    # session's id the moment it sees THIS Bash call (the GM's own `beat.py
    # open`) go by; read it once and delete it, so this ledger is scoped to
    # the session that actually opened it — the fallback is CLAUDE_SESSION_ID
    # (new_ledger's own default), which is rarely set, and then "" (a
    # session-oblivious ledger: --guard/--post/--meter never enforce
    # ownership against an empty session_id).
    owner_path = os.path.join(scratchpad_dir(story), ".beat_owner")
    if os.path.isfile(owner_path):
        try:
            L["session_id"] = open(owner_path).read().strip()
        except Exception as e:
            warn(f"could not read {owner_path} for session scoping ({e}).")
        try:
            os.remove(owner_path)
        except Exception:
            pass
    save_ledger(story, L)

    print(f"BRIEF        {os.path.relpath(brief_path, VAULT)}   ({len(brief_text):,} B)")
    print(f"DRAFT        {os.path.relpath(draft_path, VAULT)}   <- narrator writes here")
    print("READER-BRIEF (run `beat.py reader-brief` after the draft exists)")
    print(f"READER-OUT   {os.path.relpath(draft_path, VAULT).replace('_draft.md', '_reader.md')}")
    print(f"TYPE         {beat_type}    CEILING {ceiling:,} chars of body (menu excluded)")
    print(f"ONSTAGE      {', '.join(npc) if npc else '(none)'}")
    print(f"OBLIGATION   {obligation_text}")
    if forced_close:
        print("CHAPTER CLOSE DUE — this beat is forced to type=close.")


def cmd_reader_brief(args):
    story = _require_story()
    L = load_ledger(story)
    if not L:
        print("!! BEAT.PY: no open ledger — run `beat.py open` first.")
        return
    if not os.path.isfile(L["draft"]):
        print(f"!! BEAT.PY: no draft at {L['draft']} yet.")
        return
    body, fails, adv, cee, skip = pl_lint(L["draft"], beat_type=L["beat_type"], is_draft=True)
    if fails:
        report = pl_render(body, fails, adv, cee, skip)
        print("DRAFT NOT LINT-CLEAN")
        print(report)
        return
    L["lint"] = "ok"
    L["lint_at"] = now_iso()
    L["draft_sha"] = sha_norm(open(L["draft"]).read())
    L["draft_chars"] = len(body)

    if L["beat_type"] == "bridge":
        L["reader_waived"] = True
        save_ledger(story, L)
        print("READER WAIVED — bridge beat, second-reader skipped by design.")
        return

    bundle, reader_out = build_reader_bundle(
        story, L["chapter"], L["beat"], L["beat_type"], L["ceiling"], None,
        L["obligation"], L["draft"]
    )
    readerbrief_path = L["draft"].replace("_draft.md", "_readerbrief.md")
    with open(readerbrief_path, "w") as f:
        f.write(bundle)
    L["reader_brief"] = readerbrief_path
    L["reader_out"] = reader_out
    save_ledger(story, L)
    print(f"READER-BRIEF: {os.path.relpath(readerbrief_path, VAULT)}")


def cmd_revise_brief(args):
    story = _require_story()
    L = load_ledger(story)
    if not L:
        print("!! BEAT.PY: no open ledger.")
        return
    if L["revisions"] >= L.get("revisions_max", MAX_REVISIONS):
        print(
            "RULE 5 — two revision cycles done. Ship the current draft now (`beat.py append`); "
            "the residual findings are logged automatically. Do not grind, and do not tell the "
            f"player. (revisions={L['revisions']}, max={L.get('revisions_max', MAX_REVISIONS)})"
        )
        return
    L["revisions"] += 1
    sp = scratchpad_dir(story)
    revise_path = os.path.join(sp, f"ch{L['chapter']}_beat{L['beat']}_revise{L['revisions']}.md")
    verdict_text = _read_or_note(L.get("reader_out") or "", "reader verdict")
    draft_text = _read_or_note(L["draft"], "draft")
    text = (
        f"=== REVISION {L['revisions']}/{L.get('revisions_max', MAX_REVISIONS)} ===\n\n"
        "=== SECOND-READER VERDICT ===\n" + verdict_text + "\n\n"
        "=== CURRENT DRAFT ===\n" + draft_text + "\n\n"
        "=== INSTRUCTION ===\n"
        f"Read {L.get('reader_out')}, then {L['draft']}. Revise the draft in place. Fix only "
        "what the findings name. Do not rewrite anything unflagged and do not add length — a "
        "revision that grows the draft is a failed revision. Return the receipt."
    )
    with open(revise_path, "w") as f:
        f.write(text)
    save_ledger(story, L)
    print(f"BRIEF: {os.path.relpath(revise_path, VAULT)}")


def _insert_beat_block(chapter_text, block):
    sep = "\n\n---\n\n"
    pattern = re.compile(r"\n---\n\n" + re.escape(REPEAT_MARKER))
    m = pattern.search(chapter_text)
    if m:
        return chapter_text[:m.start()] + "\n\n" + block + sep + REPEAT_MARKER + chapter_text[m.end():]
    if REPEAT_MARKER in chapter_text:
        idx = chapter_text.index(REPEAT_MARKER)
        return chapter_text[:idx] + block + sep + chapter_text[idx:]
    if RECAP_HEADING in chapter_text:
        idx = chapter_text.index(RECAP_HEADING)
        return chapter_text[:idx] + block + sep + chapter_text[idx:]
    return chapter_text.rstrip("\n") + sep + block + "\n"


def cmd_append(args):
    story = _require_story()
    L = load_ledger(story)
    if not L:
        print("!! BEAT.PY: no open ledger — nothing to append.")
        return
    if L.get("lint") != "ok":
        print("!! BEAT.PY: draft is not lint-clean — run `beat.py reader-brief` (it re-lints) first.")
        return
    reader_reason = reader_gate_reason(L)
    if reader_reason:
        print(f"!! BEAT.PY: {reader_reason}")
        return

    draft_raw = open(L["draft"]).read()
    header_re = pl_beat_header_re()
    hm = header_re.match(draft_raw.strip())
    if hm:
        header_line = draft_raw.strip().split("\n", 1)[0]
        rest = draft_raw.strip().split("\n", 1)[1] if "\n" in draft_raw.strip() else ""
    else:
        warn(f"draft at {L['draft']} has no valid beat-header first line — appending without one.")
        header_line = f"<!-- beat: type={L['beat_type']} obligation=\"{L['obligation'][:200]}\" onstage={','.join(L['npc'])} -->"
        rest = draft_raw.strip()

    label = args.label or " ".join((L["obligation"] or "Beat").split()[:4])
    block = (
        f"### Beat {L['beat']} — {label} ({today()})\n"
        f"{header_line}\n\n"
        f"**Player input:** {L['player_input']}\n\n"
        f"{rest.strip()}\n"
    )

    cf = chapter_file(story, L["chapter"])
    text = open(cf).read() if os.path.isfile(cf) else ""
    new_text = _insert_beat_block(text, block)
    vault_write(story, cf, new_text, mode="overwrite")

    # verify the slice landed
    landed = open(cf).read()
    probe = re.sub(r"\s+", " ", rest.strip())[:120]
    if probe and probe not in re.sub(r"\s+", " ", landed):
        warn(f"post-append verification failed for {cf} — the draft slice was not found after writing.")

    L["appended_at"] = now_iso()
    save_ledger(story, L)
    print(f"APPENDED: {os.path.relpath(cf, VAULT)} (+{len(block):,} B)")


def cmd_close(args):
    story = _require_story()
    L = load_ledger(story)
    if not L:
        print("!! BEAT.PY: no open ledger.")
        return
    body, fails, adv, cee, skip = pl_lint(L["draft"], beat_type=L["beat_type"], is_draft=True) \
        if os.path.isfile(L["draft"]) else ("", [], [], [], set())
    if fails:
        print("DRAFT NOT LINT-CLEAN — cannot close.")
        print(pl_render(body, fails, adv, cee, skip))
        return

    N, M = L["chapter"], L["beat"]
    cf = chapter_file(story, N)
    plan = parse_plan(open(cf).read()) if os.path.isfile(cf) else None
    chapter_close_due = False
    if plan:
        turn_id = L.get("turn_id")
        for t in plan["turns"]:
            if t["id"] == turn_id:
                if args.not_delivered:
                    plan["rescope"] = plan.get("rescope", []) + [
                        f"{today()} | beat {M} did not deliver {turn_id}; still open."
                    ]
                else:
                    t["status"] = "delivered"
        write_plan(story, N, plan)
        remaining = [t for t in plan["turns"] if t["status"] == "open"]
        chapter_close_due = (not remaining) or (M >= plan["budget"])

    L["closed"] = True
    L["beats_used"] = M
    L["delivered"] = not args.not_delivered
    save_ledger(story, L)

    status = "NOT DELIVERED" if args.not_delivered else "delivered"
    print(f"BEAT CLOSED — ch{N} b{M} {L['beat_type']} · {status}")
    if chapter_close_due:
        print("CHAPTER CLOSE DUE — the next beat should be type=close, then `close-chapter`.")

    # F7 point 3: a hint, not an auto-apply — the last verdict on file is
    # informative, not authoritative over what the GM knows actually
    # happened on stage, so this never flips --not-delivered on its own.
    obligation_flag = (L.get("reader_flags") or {}).get("obligation", "")
    if not args.not_delivered and obligation_flag and not obligation_flag.startswith("delivered"):
        print(
            f"NOTE: the last second-reader verdict said OBLIGATION: {obligation_flag} — if "
            "that's right, this beat should have been closed with `beat.py close "
            "--not-delivered` instead."
        )


def cmd_rescope(args):
    story = _require_story()
    N = _require_chapter(story)
    cf = chapter_file(story, N)
    if not os.path.isfile(cf):
        print(f"!! BEAT.PY: no chapter file at {cf}.")
        return
    plan = parse_plan(open(cf).read())
    if plan is None:
        print("!! BEAT.PY: no parseable plan block to rescope.")
        return
    target = next((t for t in plan["turns"] if t["id"] == args.turn), None)
    if target is None:
        print(f"!! BEAT.PY: no turn '{args.turn}' in the plan.")
        return
    prior = sum(1 for r in plan.get("rescope", []) if args.turn in r)
    target["latest"] = args.latest
    plan["rescope"] = plan.get("rescope", []) + [f"{today()} | {args.turn} | {args.why}"]
    write_plan(story, N, plan)
    print(f"RESCOPED {args.turn} -> latest {args.latest}")
    if prior >= 1:
        print(f"THE TURN IS WRONG — {args.turn} has now been rescoped twice; rewrite it with "
              "open-chapter/--obligation and log that, rather than rescoping a third time.")


def _clock_is_real(clock):
    if not clock or not clock.strip():
        return False
    return bool(re.search(
        r"\d|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\bday\b|\bhour\b"
        r"|\bbefore\b|\bby\b|\buntil\b",
        clock, re.I
    ))


def cmd_open_chapter(args):
    story = _require_story()
    if not _clock_is_real(args.clock):
        print(
            "!! BEAT.PY: open-chapter refuses without a real clock. Every 0%-tissue chapter "
            "in this vault's forensics has a live in-fiction deadline with a consequence; "
            "every high-tissue chapter has none. Pass --clock \"<a named deadline, dated or "
            "counted down, with a consequence for missing it>\"."
        )
        return
    tmpl_path = os.path.join(VAULT, "_template", "chapters", "_chapter_template.md")
    if not os.path.isfile(tmpl_path):
        print(f"!! BEAT.PY: template missing at {tmpl_path}.")
        return
    tmpl = open(tmpl_path).read()
    adventure_name = args.adventure_name or story
    text = (
        tmpl.replace("{{XX}}", str(args.n))
            .replace("{{TITLE}}", args.title)
            .replace('"{{active|complete}}"', '"active"')
            .replace("{{ADVENTURE_NAME}}", adventure_name)
            .replace("{{DATE}}", today())
    )
    # Strip the template's illustrative "### Beat {{N}} — ..." placeholder
    # block — it is a shape example for a human, not a real beat, and a fresh
    # chapter must start at zero beats (resolve_beat counts '^### Beat'
    # headings; leaving the placeholder in would make beat 1 count as beat 2).
    placeholder_re = re.compile(r"\n---\n\n### Beat\b.*?(?=\n---\n\n<!-- Repeat the Beat block)", re.S)
    text = placeholder_re.sub("", text, count=1)
    cf = chapter_file(story, args.n)
    vault_write(story, cf, text, mode="overwrite")

    turns = []
    if args.turns:
        for i, t in enumerate(args.turns.split(";"), start=1):
            t = t.strip()
            if not t:
                continue
            turns.append({"id": f"T{i}", "text": t, "status": "open", "earliest": 1, "latest": args.budget})
    if not turns:
        turns = [{"id": "T1", "text": "(fill in — the chapter's non-negotiable content)",
                   "status": "open", "earliest": 1, "latest": args.budget}]
    plan = {
        "chapter": args.n, "title": args.title, "budget": args.budget, "clock": args.clock,
        "turns": turns,
        "close": "land the last open turn, then time-skip out. Do not ask the player.",
        "forbidden": [], "rescope": [],
    }
    written = write_plan(story, args.n, plan)
    if written is None:
        print("!! BEAT.PY: plan block could not be written (sanitisation failure).")
        return

    gs = os.path.join(story_dir(story), "game_state.md")
    if os.path.isfile(gs):
        gtext = open(gs).read()
        gtext = re.sub(r"^current_chapter:\s*\d+", f"current_chapter: {args.n}", gtext, flags=re.M)
        vault_write(story, gs, gtext, mode="overwrite")

    print(f"Chapter {args.n} opened: {os.path.relpath(cf, VAULT)}")
    print(f"Plan written: budget {args.budget}, clock \"{args.clock}\", {len(turns)} turn(s).")


def cmd_close_chapter(args):
    story = _require_story()
    N = _require_chapter(story)
    cf = chapter_file(story, N)
    if not os.path.isfile(cf):
        print(f"!! BEAT.PY: no chapter file at {cf}.")
        return
    text = open(cf).read()
    plan = parse_plan(text)
    beats_used = resolve_beat(story, N) - 1
    budget = plan["budget"] if plan else None

    new_text = re.sub(r'status:\s*"[^"]*"', 'status: "complete"', text, count=1)
    vault_write(story, cf, new_text, mode="overwrite")

    outline = os.path.join(story_dir(story), "story_outline.md")
    if os.path.isfile(outline) and plan:
        otext = open(outline).read()
        row_re = re.compile(rf"^\|\s*{N}\s*\|.*\|$", re.M)
        m = row_re.search(otext)
        if m:
            row = m.group(0)
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            while len(cells) < 4:
                cells.append("")
            cells[-1] = "Complete"
            if len(cells) >= 4:
                cells[3] = f"{beats_used}/{budget}" if budget else cells[3]
            new_row = "| " + " | ".join(cells) + " |"
            otext = otext[:m.start()] + new_row + otext[m.end():]
            vault_write(story, outline, otext, mode="overwrite")
        else:
            warn(f"story_outline.md has no breakdown row for chapter {N} — Status/Beats not updated.")

    print(f"Chapter {N} closed: {beats_used}/{budget if budget else '?'} beats used.")
    print(
        "EXEMPLAR-SWAP PROMPT: if a beat this chapter beats one of the five in _exemplars.md, "
        "swap it in — never append. Cap is five. (Taste call, not enforced.)"
    )


def cmd_status(args):
    story = resolve_story()
    if not story:
        print("STATUS: no active story.")
        return
    N = resolve_chapter(story)
    if N is None:
        print(f"STATUS: story {story}, no resolvable current_chapter.")
        return
    M = resolve_beat(story, N)
    L = load_ledger(story)
    cf = chapter_file(story, N)
    plan = parse_plan(open(cf).read()) if os.path.isfile(cf) else None
    print(f"story: {story}")
    print(f"chapter: {N}   next beat: {M}")
    print(f"ledger: {'none' if not L else ('closed' if L.get('closed') else 'open, ' + L.get('beat_type', '?'))}")
    if plan is None:
        print("plan: none yet")
    else:
        open_turns = [t for t in plan["turns"] if t["status"] == "open"]
        print(f"plan: budget {plan['budget']}, {len(open_turns)} open turn(s), clock: {plan['clock']}")
    if L:
        print(json.dumps(L, indent=2))


def cmd_abort(args):
    story = _require_story()
    L = load_ledger(story)
    p = ledger_path(story)
    removed = []
    if L:
        for key in ("brief", "draft", "reader_brief", "reader_out"):
            fp = L.get(key)
            if fp and os.path.isfile(fp):
                os.remove(fp)
                removed.append(fp)
        sp = scratchpad_dir(story)
        for k in range(1, MAX_REVISIONS + 1):
            rp = os.path.join(sp, f"ch{L['chapter']}_beat{L['beat']}_revise{k}.md")
            if os.path.isfile(rp):
                os.remove(rp)
                removed.append(rp)
    if os.path.isfile(p):
        os.remove(p)
        removed.append(p)
    if removed:
        print("ABORTED. Removed:")
        for r in removed:
            print(f"  {os.path.relpath(r, VAULT)}")
    else:
        print("ABORTED. Nothing to remove (no ledger).")


def cmd_lint(args):
    body, fails, adv, cee, skip = pl_lint(args.path, beat_type=args.type, is_draft=True)
    print(pl_render(body, fails, adv, cee, skip))


# --------------------------------------------------------------------------
# --gate (UserPromptSubmit, via craft-gate.sh) — the ONE implementation of
# ACTIVE_GAME.md -> active_path -> CHAPTER METER + ACTIVE REGISTER digests.
# --------------------------------------------------------------------------
def gate_warn(msg):
    """--gate's own loud-degradation channel. Distinct prefix from warn()'s
    '!! BEAT.PY WARNING:' — matches the annex's '!! GATE WARNING:' wording for
    the checks that are specific to gate assembly (a missing folder, a stale
    Response Length line, a stale-open ledger, the size-budget drop)."""
    print(f"!! GATE WARNING: {msg}")


_gate_warned_missing = False  # set by gate_resolve_story() so cmd_gate can skip the
                              # generic "no active story yet" line when a louder,
                              # more specific WARNING already printed for this turn.


def gate_resolve_story():
    """Story resolution for --gate specifically, with LOUD warnings — unlike
    resolve_story()/pl_active_story(), which can resolve via prose-lint.py's
    active_story() and its warnings only ever land in that module's own
    (unprinted) `warnings` list. A blank/missing active_path is the documented
    state of a fresh clone (informational, not a fault, handled by the caller);
    a non-empty active_path naming a missing folder IS a fault and warns here."""
    global _gate_warned_missing
    if not os.path.isfile(ACTIVE):
        return None
    m = re.search(r"^active_path:[ \t]*(?:[\"'])?(.+?)(?:[\"'])?[ \t]*$", open(ACTIVE).read(), re.M)
    if not m:
        return None
    story = m.group(1).strip().strip("/")
    if not story:
        return None
    if not os.path.isdir(os.path.join(VAULT, story)):
        gate_warn(f"active_path names '{story}' but {story}/ is missing — no story digests "
                  "injected. Fix active_path in ACTIVE_GAME.md or restore the story folder.")
        _gate_warned_missing = True
        return None
    return story


def _ledger_stale(ledger):
    """True iff an OPEN ledger's opened_at is more than 6 hours old."""
    if not ledger or ledger.get("closed"):
        return False
    opened = ledger.get("opened_at")
    if not opened:
        return False
    try:
        dt = datetime.datetime.strptime(opened, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc)
    except Exception:
        return False
    return (datetime.datetime.now(datetime.timezone.utc) - dt) > datetime.timedelta(hours=6)


def cmd_gate(used):
    story = gate_resolve_story()
    if not story:
        # A blank active_path is a fresh clone, not a fault (matches the old
        # craft-gate.sh's own informational branch — a WARNING here every
        # prompt before the first story exists would read as a broken install).
        # But if gate_resolve_story() already printed a specific WARNING (a
        # non-empty active_path naming a missing folder), that line stands
        # alone — repeating the generic one under it would read as a second,
        # unrelated fault on a fresh clone.
        if not _gate_warned_missing:
            print("-- CRAFT GATE: no active story yet — spine injected, no story digests.")
            print("   Say \"let's start an adventure\" to scaffold one (the new-story skill).")
        return

    mi = os.path.join(story_dir(story), "master_index.md")
    if os.path.isfile(mi) and "**Response Length**" in open(mi).read():
        gate_warn(f"{story}/master_index.md still carries '**Response Length**' — convert to "
                  "'**Beat Sizes**'; the length floor is retired. Using ceiling defaults.")

    N = resolve_chapter(story)
    if N is None:
        # resolve_chapter() already called warn() (a visible !! BEAT.PY WARNING:
        # line) — nothing more can be printed without a chapter number.
        return
    M = resolve_beat(story, N)
    cf = chapter_file(story, N)
    plan = parse_plan(open(cf).read()) if os.path.isfile(cf) else None
    L = load_ledger(story)
    if _ledger_stale(L):
        gate_warn(f"the ledger for {story} ch{L.get('chapter')} b{L.get('beat')} has been open "
                  f"since {L.get('opened_at')} (>6h) — run `beat.py status`.")

    meter_text = chapter_meter(story, N, M, plan, L)
    used_total = used + len(meter_text.encode("utf-8"))
    sys.stdout.write(meter_text)

    blocks = digests(story)
    if not blocks:
        return
    header = f"\n=== ACTIVE REGISTER ({story}) — standing-mode digests ===\n"
    used_total += len(header.encode("utf-8"))
    print(header, end="")
    for slug, text in blocks:
        chunk = f"\n{text}\n"
        chunk_bytes = len(chunk.encode("utf-8"))
        if used_total + chunk_bytes > MAX_BYTES:
            print(f"!! GATE WARNING: size budget reached — digest '{slug}' NOT injected; "
                  f"Read _craft_research/cards/{slug}.card.md before prose this turn.")
            continue
        print(chunk, end="")
        used_total += chunk_bytes


# --------------------------------------------------------------------------
# --guard (PreToolUse) — deny a chapter-file write unless the chain is
# complete: draft exists, lint clean, reader present-or-waived, and (when
# extractable) the text being written matches the cleared draft's sha.
# --------------------------------------------------------------------------
# A Bash command "targets" a chapter file only when a write verb is applied
# TO that path — not when the path merely appears somewhere on the line
# alongside an unrelated `>`/`2>&1`/write-flavoured word. Each alternative
# below requires the chapter path to be the OPERAND of the write: the
# redirect/tee target, the sed -i / perl -pi in-place file, the dd `of=`,
# the cp/mv/install/truncate/rm argument, the open(...) path with a 'w'/'a'
# mode, or the obsidian CLI's `path=` after a write verb. A lazy `.*?`
# between the verb and the path lets other arguments (a sed script, a `-a`
# flag, `vault=...`) sit in between without letting the match wander onto an
# unrelated file further down the command.
_CH_PATH = r"\S*chapters/chapter\S*?\.md"
_BASH_WRITE_ON_CHAPTER_RE = re.compile(
    r"(?:"
    r"(?:>>?|\|\s*tee(?:\s+-a)?)\s*[\"']?" + _CH_PATH +           # > / >> / | tee [-a]  TARGET
    r"|\btee\b(?:\s+-a)?\s+[\"']?" + _CH_PATH +                    # tee [-a] TARGET
    r"|\bsed\s+-i\S*\s+.*?[\"']?" + _CH_PATH +                     # sed -i ... TARGET
    r"|\bperl\s+-\w*p\w*i\S*\s+.*?[\"']?" + _CH_PATH +             # perl -pi ... TARGET
    r"|\bdd\s+.*?\bof=" + _CH_PATH +                               # dd ... of=TARGET
    r"|\b(?:cp|mv|install)\s+.*?[\"']?" + _CH_PATH +               # cp/mv/install ... TARGET
    r"|\btruncate\s+.*?[\"']?" + _CH_PATH +                        # truncate ... TARGET
    r"|\brm\s+.*?[\"']?" + _CH_PATH +                              # rm ... TARGET
    r"|\bopen\(\s*[\"']?" + _CH_PATH + r"[\"']?\s*,\s*[\"'][wa]" + # python open(TARGET, 'w'|'a'
    r"|\bobsidian\b.*?\b(?:append|create|modify|delete|move|rename)\b.*?\bpath=" + _CH_PATH +
    r")",
    re.I | re.S,
)


def targets_chapter(tool_name, ti, story):
    if tool_name in ("Write", "Edit", "MultiEdit"):
        p = ti.get("file_path", "") or ""
        return f"/{story}/chapters/" in p.replace("\\", "/") and not os.path.basename(p).startswith("_")
    if tool_name == "Bash":
        c = ti.get("command", "") or ""
        # C1 regression: the previous check matched the chapter-path regex and
        # the write-verb alternation INDEPENDENTLY, anywhere in the command —
        # so a read-only command that merely MENTIONED a chapter path (`grep`,
        # `tail`, `cat | wc`, `diff a.md chapter.md > /tmp/x.diff`) was denied
        # as soon as the command also contained an unrelated `>` (`2>&1`,
        # a redirect to some other file) or the substring "write"/"create" in
        # an unrelated place. `_BASH_WRITE_ON_CHAPTER_RE` instead requires the
        # write verb be APPLIED TO the chapter path itself — the path must
        # appear as the operand of the redirect/tee/sed-i/perl-pi/dd/cp/mv/
        # install/truncate/rm/open(...,'w'|'a')/obsidian-write, not just
        # co-occur with one somewhere else on the line.
        return bool(_BASH_WRITE_ON_CHAPTER_RE.search(c))
    return False


_HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?\n(.*?)\n\1\b", re.S)

# F1: the GM opening a beat, as a Bash command — matched so --guard can
# capture WHICH session is about to own the resulting ledger (see
# .beat_owner below, and cmd_open's read-once-and-delete of it). Anchored so
# it only fires on the GM's own literal runbook-step-2 invocation, not on
# something that merely mentions "beat.py open" in a comment or a string.
_BEAT_OPEN_CMD_RE = re.compile(
    r"(^|&&|;)\s*(?:cd\s+\S+\s*&&\s*)?python3\s+\S*beat\.py\s+open\b"
)


def _extract_inline_prose(tool_name, ti):
    """Best-effort text of what is ABOUT to be written, for the sha-mismatch
    check. None means 'could not tell' (verbatim check skipped, chain checks
    still applied) — never crashes, never treated as a match."""
    if tool_name == "Write":
        c = ti.get("content")
        return c if isinstance(c, str) else None
    if tool_name == "Edit":
        c = ti.get("new_string")
        return c if isinstance(c, str) else None
    if tool_name == "MultiEdit":
        edits = ti.get("edits") or []
        parts = [e.get("new_string", "") for e in edits if isinstance(e, dict) and e.get("new_string")]
        return "\n".join(parts) if parts else None
    if tool_name == "Bash":
        cmd = ti.get("command", "") or ""
        m = _HEREDOC_RE.search(cmd)
        return m.group(2) if m else None
    return None


def cmd_guard():
    global _STDOUT_IS_JSON
    _STDOUT_IS_JSON = True
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}

    # Delta (plan): a Bash call that is itself `beat.py append` verifies the
    # whole chain on its own (cmd_append refuses without lint+reader) — no
    # need to also gate the subprocess call, and gating it would double-deny
    # legitimate appends since the fast-path text lives in the command string,
    # not in any inline prose this hook could sha-check.
    # Anchored to the WHOLE command (start-anchored, no `;`/`&`/`|` chaining
    # allowed after it) — the old check was `"beat.py" in cmd and " append" in
    # cmd`, which matched those two substrings anywhere at all, including
    # inside a heredoc body or a trailing comment appended to an unrelated
    # write (`cat >> chapter_1.md <<EOF ... EOF  # beat.py append`).
    if tool_name == "Bash":
        cmd = ti.get("command", "") or ""
        if re.match(r"^\s*(python3?\s+)?\S*beat\.py\s+append\b[^;&|\n]*$", cmd):
            sys.exit(0)
        # F1: the GM's own `beat.py open` going by — capture which session
        # this is, so a LATER --meter/--post/--guard call can tell this
        # session's own beat apart from one opened by a different Claude
        # Code session in the same story tree (the observed failure: a
        # second session's Stop hook was BLOCKED — and its block counted
        # against the ledger — for a beat a different session had opened).
        # `.beat_owner` is overwritten every `beat.py open` Bash call and
        # read-once-and-deleted by cmd_open; never denies, never touches
        # stdout — this call always returns silently either way.
        if _BEAT_OPEN_CMD_RE.search(cmd):
            story = resolve_story()
            if story:
                try:
                    with open(os.path.join(scratchpad_dir(story), ".beat_owner"), "w") as f:
                        f.write(payload.get("session_id") or "")
                except Exception as e:
                    warn(f"--guard: could not write .beat_owner for session scoping ({e}).")
            sys.exit(0)

    story = resolve_story()
    if not story or not targets_chapter(tool_name, ti, story):
        sys.exit(0)  # cheap bail-out: not a chapter-log write, nothing to guard

    N = resolve_chapter(story)
    M = resolve_beat(story, N) if N is not None else None
    L = load_ledger(story)

    # F1: a foreign session must never be allowed to write the chapter file
    # while another session's beat is still open — even though this write
    # might otherwise look complete (e.g. a stale ledger of the FOREIGN
    # session's own, from an earlier, unrelated beat). `agent_id` marks a
    # subagent call (the narrator/second-reader never write the chapter file
    # directly, but this mirrors --post's same allowance for consistency);
    # its parent session is assumed to be the owner.
    if L is not None and not L.get("closed"):
        owner = (L.get("session_id") or "").strip()
        payload_sid = (payload.get("session_id") or "").strip()
        if owner and payload_sid and owner != payload_sid and not payload.get("agent_id"):
            reason = (
                f"another session owns the open beat ch{L.get('chapter')} b{L.get('beat')} — "
                "do not write this chapter file from here."
            )
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }}))
            sys.exit(0)

    missing = []

    if L is None or L.get("closed"):
        missing.append("no open beat — run `beat.py open --type <bridge|scene|setpiece|close>`")
    else:
        N, M = L.get("chapter", N), L.get("beat", M)
        if not L.get("draft_sha"):
            missing.append("no draft — run Agent(narrator) on the brief")
        if L.get("lint") != "ok":
            missing.append("draft is not lint-clean — the narrator must cut, not expand")
        reader_reason = reader_gate_reason(L)
        if reader_reason:
            missing.append(reader_reason)
        inline = _extract_inline_prose(tool_name, ti)
        if inline is None:
            warn("--guard: could not extract inline prose from this tool call — verbatim "
                 "sha check skipped, chain checks still applied.")
        elif len(inline) > 200 and L.get("draft_sha") and sha_norm(inline) != L["draft_sha"]:
            missing.append(
                "the text being appended is not the draft the reader cleared (sha mismatch). "
                "Append by READING the draft file, never by retyping the prose."
            )

    if missing:
        reason = f"CHAIN INCOMPLETE for ch{N} beat{M}:\n- " + "\n- ".join(missing)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))
    # On pass: print NOTHING. Never emit permissionDecision:"allow" — that
    # would override the user's own permission settings.
    sys.exit(0)


# --------------------------------------------------------------------------
# --post (PostToolUse) — routes by file suffix: `_draft.md` re-lints and
# stamps the ledger; `_reader.md` parses the verdict and stamps it. Anything
# else is not this hook's business.
# --------------------------------------------------------------------------
def beat_type_of(path, L):
    """1st: the <!-- beat: type=... --> header IN THE FILE. 2nd: the ledger.
    3rd: 'scene', loudly."""
    try:
        raw = open(path).read()
    except Exception:
        raw = ""
    m = pl_beat_header_re().search(raw)
    if m:
        return m.group(1).lower()
    if L and L.get("beat_type"):
        return L["beat_type"]
    warn(f"no <!-- beat: type=... --> header found in {path} and no ledger beat_type on "
         "record — defaulting to type=scene.")
    return "scene"


def _prior_menu_lists(story, chapter):
    if not story or not chapter:
        return []
    return [pl_menu_options(raw) for _, raw in raw_beats(story, chapter, FORBIDDEN_MENUS)]


def chain_line(L):
    """'Chain 2/4 · ch5 b3 scene · next: beat.py reader-brief' — prepended to
    every --post additionalContext so a mid-turn compaction or continuation
    re-learns its position from the next tool result (annex §0.2)."""
    return "Chain " + chain_summary(L)


def _owns_and_may_stamp(p, L, tracked_key, payload):
    """-> (is_tracked, may_stamp). `is_tracked` mirrors the pre-F1 ownership
    check (is `p` the exact file THIS ledger is waiting on, by path — B3/the
    verdict-file mirror of it). `may_stamp` adds F1's session gate on top:
    a tracked file may still not be stamped if it was produced by a
    DIFFERENT Claude Code session than the one that opened the beat.

    `payload` is the real hook payload for `--post`, or None for the `stamp`
    GM-command fallback (F2) — `stamp` is invoked directly by the GM with no
    session context at all, so per the plan it stamps whenever the file is
    tracked, full stop ("the caller can't be identified"). A subagent's
    PostToolUse payload carries `agent_id`; its parent session is assumed to
    be the owner, so it may always stamp a tracked file too."""
    is_tracked = bool(L) and L.get(tracked_key) and \
        os.path.abspath(p) == os.path.abspath(L[tracked_key])
    if not is_tracked:
        return False, False
    if payload is None or payload.get("agent_id"):
        return True, True
    owner = (L.get("session_id") or "").strip()
    if not owner:
        return True, True
    payload_sid = (payload.get("session_id") or "").strip()
    if payload_sid and owner != payload_sid:
        return True, False
    return True, True


def _draft_stamp_report(p, story, payload):
    """-> (exit_code, report_text, stamp_L_or_None). Shared core of --post's
    `_draft.md` branch and the `stamp` GM fallback (F2) — they differ only in
    owner policy (real payload vs None) and in how the caller packages this
    (JSON additionalContext vs plain stdout), both handled by the caller."""
    label = "--post" if payload is not None else "stamp"
    L = load_ledger(story) if story else None
    is_tracked, may_stamp = _owns_and_may_stamp(p, L, "draft", payload)
    stamp_L = L if may_stamp else None
    if L is not None and not is_tracked:
        # B3: L["draft"] is pre-populated with this beat's exact expected
        # path at `beat.py open` time, before the narrator ever writes it —
        # so on the real path this compares equal every time. Any OTHER
        # `_draft.md` anywhere on disk (a scratch file in /tmp, a foreign
        # story's draft, a stray file that merely matches the suffix) used
        # to unconditionally overwrite the open ledger's
        # draft/draft_sha/lint/beat_type/ceiling — hijacking the chain of
        # custody so `beat.py append` would go on to land THAT file in the
        # chapter log. Lint and report either way (the feedback is still
        # useful); stamp the ledger only when the path is the one this
        # ledger is actually tracking.
        warn(f"{label}: {p} is not the open ledger's tracked draft "
             f"({L.get('draft')}) — linting only; the ledger is NOT being stamped from it.")
    elif L is not None and is_tracked and not may_stamp:
        warn(f"{label}: {p} is the open beat's tracked draft, but this session does not own "
             f"it (owner={L.get('session_id')!r}) and carries no agent_id — linting only; the "
             "ledger is NOT being stamped from a foreign session.")
    btype = beat_type_of(p, stamp_L)
    prior_menus = _prior_menu_lists(
        (stamp_L or {}).get("story") or story, (stamp_L or {}).get("chapter")
    )
    ceiling = pl_beat_sizes(story).get(btype, BEAT_SIZES[btype])
    body, fails, adv, cee, skip = pl_lint(
        p, want_c=False, is_draft=True, beat_type=btype, prior_menus=prior_menus
    )
    report = pl_render(body, fails, adv, cee, skip)
    if fails:
        return 2, report, None
    if stamp_L is not None:
        stamp_L["draft_sha"] = sha_norm(open(p).read())
        stamp_L["draft_chars"] = len(body)
        stamp_L["lint"] = "ok"
        stamp_L["lint_at"] = now_iso()
        stamp_L["beat_type"] = btype
        stamp_L["ceiling"] = ceiling
        save_ledger(stamp_L.get("story") or story, stamp_L)
    report = report + f"\nLINT OK — {len(body):,}/{ceiling:,} chars, type {btype}."
    return 0, report, stamp_L


def _reader_stamp_report(p, story, payload):
    """-> (exit_code, report_text, stamp_L_or_None). Reader-verdict mirror of
    `_draft_stamp_report` — same shared-core split for the same reason."""
    label = "--post" if payload is not None else "stamp"
    text = open(p).read()
    ok, parsed, err = parse_verdict(text)
    if not ok:
        return 2, err, None

    L = load_ledger(story) if story else None
    is_tracked, may_stamp = _owns_and_may_stamp(p, L, "reader_out", payload)
    stamp_L = L if may_stamp else None
    if L is not None and not is_tracked:
        warn(f"{label}: {p} is not the open ledger's tracked verdict file "
             f"({L.get('reader_out')}) — parsing only; the ledger is NOT being stamped from it.")
    elif L is not None and is_tracked and not may_stamp:
        warn(f"{label}: {p} is the open beat's tracked verdict file, but this session does not "
             f"own it (owner={L.get('session_id')!r}) and carries no agent_id — parsing only; "
             "the ledger is NOT being stamped from a foreign session.")
    if stamp_L is not None:
        stamp_L["reader"] = "clean" if parsed["clean"] else "findings"
        stamp_L["reader_findings"] = parsed["n"]
        stamp_L["reader_flags"] = parsed["flags"]
        stamp_L["reader_at"] = now_iso()
        save_ledger(stamp_L.get("story") or story, stamp_L)

    report = text[:1500]
    if parsed.get("auto_promoted"):
        flags = parsed["flags"]
        which = []
        if not flags["obligation"].startswith("delivered"):
            which.append(f"OBLIGATION: {flags['obligation']}")
        if not flags["clock"].startswith("intact"):
            which.append(f"CLOCK: {flags['clock']}")
        if flags["menu"].startswith("repeat"):
            which.append(f"MENU: {flags['menu']}")
        report = f"A revision cycle is required: {'; '.join(which) or 'see verdict'}.\n\n" + report
    return 0, report, stamp_L


def cmd_post():
    global _STDOUT_IS_JSON
    _STDOUT_IS_JSON = True
    payload = json.load(sys.stdin)
    p = (payload.get("tool_input") or {}).get("file_path", "") or ""
    story = resolve_story()

    if p.endswith("_draft.md"):
        if not os.path.isfile(p):
            sys.exit(0)
        code, report, stamp_L = _draft_stamp_report(p, story, payload)
        if code == 2:
            print(report, file=sys.stderr)
            sys.exit(2)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": chain_line(stamp_L) + "\n" + report,
        }}))
        sys.exit(0)

    if p.endswith("_reader.md"):
        if not os.path.isfile(p):
            sys.exit(0)
        code, report, stamp_L = _reader_stamp_report(p, story, payload)
        if code == 2:
            print(report, file=sys.stderr)
            sys.exit(2)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": chain_line(stamp_L) + "\n" + report,
        }}))
        sys.exit(0)

    sys.exit(0)


# F2: PostToolUse hooks do not fire on Write/Edit tool calls made INSIDE a
# subagent unless that agent's OWN frontmatter declares them (verified in the
# v2.1.257 binary) — narrator.md and second-reader.md now do, but as a GM-side
# backstop for any harness/build where that per-agent hook is silently
# ignored, `beat.py stamp <path>` runs the exact --post routing on demand,
# with no stdin/payload at all. Per the plan: `stamp` is a GM command, so
# (per `_owns_and_may_stamp` above, called here with payload=None) it stamps
# whenever the path is the ledger's own tracked file — "the caller can't be
# identified" is not a reason to withhold a GM-invoked stamp.
def cmd_stamp(args):
    story = _require_story()
    p = args.path
    if p.endswith("_draft.md"):
        if not os.path.isfile(p):
            sys.exit(0)
        code, report, _stamp_L = _draft_stamp_report(p, story, None)
        print(report)
        sys.exit(code)
    if p.endswith("_reader.md"):
        if not os.path.isfile(p):
            sys.exit(0)
        code, report, _stamp_L = _reader_stamp_report(p, story, None)
        print(report)
        sys.exit(code)
    sys.exit(0)


# --------------------------------------------------------------------------
# --meter (Stop) — verifies from file truth that the beat just shipped is the
# beat the loop produced, before letting the turn end. See the module-level
# NOTE above for how it reconciles with cmd_close's `closed` flag.
# --------------------------------------------------------------------------
def looks_like_beat_prose(msg):
    """Anti-bypass heuristic: could this shipped chat message be a beat's
    prose, sent to the player outside the loop? True when it carries the
    OUTPUT CONTRACT's own menu marker (`**Choices offered:**`), or looks like
    a short (2-4 item) numbered list of options with NONE of the structural
    markup — a heading, a table `|`, a `- `/`* ` bullet, a code fence — an
    ordinary non-beat answer uses for the same list shape (a design write-up,
    a status report, a chapter recap all commonly end in a numbered list too).

    The old heuristic vetoed on the LINE-count ratio of listy lines >= 0.25.
    That fired backwards in both directions: a genuine 6-8 paragraph beat plus
    a 3-line `**Choices offered:**` menu easily clears 25% of an otherwise
    short message (never flagged as beat-shaped, so a hand-typed beat sailed
    through), while a long ordinary reply that happened to end in an unrelated
    numbered list (no menu, no markup diversity) tripped it just as easily
    (false-blocked). Checking the actual OUTPUT CONTRACT marker fixes the
    first; vetoing on markup diversity instead of list density fixes the
    second — a numbered list is only suspicious when it is the ONLY structure
    in an otherwise plain-prose message."""
    if len(msg) <= 900:
        return False
    if re.search(r"^\*\*Choices offered:\*\*", msg, re.M):
        return True
    if len(re.findall(r"[.!?]", msg)) < 4:
        return False
    lines = [ln for ln in msg.split("\n") if ln.strip()]
    if not lines:
        return False
    if any(re.match(r"^\s*(#|\||[-*]\s|```)", ln) for ln in lines):
        return False
    numbered = sum(1 for ln in lines if re.match(r"^\s*\d+\.\s", ln))
    return 2 <= numbered <= 4


def has_menu_signature(msg):
    """A '**Choices offered:**' line, or a run of 2-4 lines matching ^\\d+\\.
    preceded by >=900 chars of non-list prose (a close beat legitimately has
    NO menu at all and so carries no signature — see the module NOTE)."""
    if re.search(r"^\*\*Choices offered:\*\*", msg, re.M):
        return True
    lines = msg.split("\n")
    i, n = 0, len(lines)
    while i < n:
        if re.match(r"^\d+\.\s", lines[i]):
            j = i
            while j < n and re.match(r"^\d+\.\s", lines[j]):
                j += 1
            if 2 <= (j - i) <= 4 and len("\n".join(lines[:i])) >= 900:
                return True
            i = j
        else:
            i += 1
    return False


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _middle_slice(draft_path, n=120):
    """A 120-char whitespace-normalised slice from the MIDDLE of the draft's
    prose body — used to prove containment (not-saved, not-delivered) without
    being thrown by a leading/trailing edit."""
    if not draft_path or not os.path.isfile(draft_path):
        return ""
    body_n = _norm(pl_strip_meta(open(draft_path).read()))
    if len(body_n) <= n:
        return body_n
    start = (len(body_n) - n) // 2
    return body_n[start:start + n]


def _check_not_lint_clean(L, msg):
    return L.get("lint") == "ok", (
        "the draft is not lint-clean. Run `beat.py reader-brief` (it re-lints) or fix the "
        "draft against the report, then re-ship."
    )


def reader_gate_reason(L):
    """None if the reader gate is satisfied; otherwise the reason it is not.
    Shared by cmd_guard, cmd_append and the meter's _check_no_reader so the
    three enforcement points can never drift out of sync on what "the reader
    gate is satisfied" actually means.

    F7: the gate is satisfied once the reader has RUN — `L["reader"] in
    ("clean", "findings")` — or `reader_waived` is true. Only the reader's
    *existence* is enforced (design annex, "Explicitly rejected": enforcing
    that the verdict be CLEAN "would recreate the padding loop in a new
    dimension — the model would learn to satisfy the reader instead of
    writing well"). A verdict with findings (including auto-promoted
    OBLIGATION/CLOCK/MENU flags — `parse_verdict()` folds annex §2.3's
    auto-promotion rule into `L["reader"] != "clean"`) is a reason to REVISE
    only while `L["revisions"] < revisions_max` (rule 5's two cycles). Once
    `L["revisions"] >= revisions_max`, the chain is complete and this returns
    None even with `reader == "findings"` — `cmd_revise_brief` has already
    told the GM to ship at that point (RULE 5), and re-blocking the append
    would deadlock the Stop meter with nowhere to go, exactly the failure
    mode rule 5 exists to prevent. `reader is None and not waived` remains a
    hard block — the reader must run on every non-bridge beat."""
    if L.get("reader_waived"):
        return None
    reader = L.get("reader")
    if reader is None:
        return ("the second-reader has not run — `beat.py reader-brief`, then "
                 "Agent(second-reader), then re-ship.")
    revisions = L.get("revisions", 0) or 0
    revisions_max = L.get("revisions_max", MAX_REVISIONS)
    if reader != "clean" and revisions < revisions_max:
        flags = L.get("reader_flags") or {}
        bad = []
        if not flags.get("obligation", "").startswith("delivered"):
            bad.append(f"OBLIGATION: {flags.get('obligation', '?')}")
        if not flags.get("clock", "").startswith("intact"):
            bad.append(f"CLOCK: {flags.get('clock', '?')}")
        if flags.get("menu", "").startswith("repeat"):
            bad.append(f"MENU: {flags.get('menu', '?')}")
        detail = f" ({'; '.join(bad)})" if bad else ""
        cycle = revisions + 1
        return (f"the second-reader returned findings{detail} — revise (cycle {cycle} of "
                f"{revisions_max}) — `beat.py revise-brief` then Agent(narrator), then re-run "
                "reader-brief and Agent(second-reader), then re-ship.")
    return None


def _check_no_reader(L, msg):
    reason = reader_gate_reason(L)
    return reason is None, (reason or "")


def _check_not_saved(L, msg):
    story = L.get("story")
    cf = chapter_file(story, L["chapter"])
    sl = _middle_slice(L.get("draft"))
    if not sl:
        return False, f"the draft at {L.get('draft')} could not be read to verify it was saved."
    landed = _norm(open(cf).read()) if os.path.isfile(cf) else ""
    ok = sl in landed
    return ok, f"the draft has not been appended to {os.path.relpath(cf, VAULT)}. Run `beat.py append`."


def _check_stale_resume(L, msg):
    gs = os.path.join(story_dir(L["story"]), "game_state.md")
    want = f"**Position:** ch {L['chapter']} · beat {L['beat']}"
    text = open(gs).read() if os.path.isfile(gs) else ""
    ok = want in text
    return ok, (
        f"game_state.md's ## Resume block does not say '{want}'. Rewrite it (runbook step 9) "
        "before stopping."
    )


def _check_plan_untouched(L, msg):
    # Proof that `beat.py close` ran — the annex's own wording is "plan turn
    # status / beats_used differ from plan_before", an OR of two signals, not
    # a requirement that the turn end up delivered. `cmd_close --not-delivered`
    # (the documented path for an honestly-missed obligation) leaves the turn
    # `status: open` by design and only appends a rescope note, so checking
    # turn status alone would permanently block every not-delivered beat even
    # though close already ran. `L["beats_used"]` is set unconditionally by
    # cmd_close on both the delivered and not-delivered branches, so it is
    # the reliable "close ran" signal in either case.
    if L.get("beats_used") == L.get("beat"):
        return True, ""
    cf = chapter_file(L["story"], L["chapter"])
    plan = parse_plan(open(cf).read()) if os.path.isfile(cf) else None
    turn_id = L.get("turn_id")
    if not plan or not turn_id:
        # Nothing to verify — no plan block, or this beat had no plan turn
        # tied to it (--obligation override). Not a reason to block.
        return True, ""
    turn = next((t for t in plan["turns"] if t["id"] == turn_id), None)
    ok = bool(turn) and turn["status"] != "open"
    return ok, f"plan turn {turn_id} is still 'open'. Run `beat.py close` to tick it."


def _check_not_delivered(L, msg):
    sl = _middle_slice(L.get("draft"))
    ok = bool(sl) and sl in _norm(msg)
    return ok, (
        f"the reply you are about to send does not contain the draft at {L.get('draft')}. "
        "Re-send the beat body and menu, verbatim from that file, and nothing else."
    )


def _check_meta_tax(L, msg):
    draft_raw = open(L["draft"]).read() if L.get("draft") and os.path.isfile(L["draft"]) else ""
    body = pl_strip_meta(draft_raw)
    menu = "\n".join(pl_menu_options(draft_raw))
    msg_n, body_n, menu_n = _norm(msg), _norm(body), _norm(menu)
    residue = len(msg_n) - len(body_n) - len(menu_n)
    allow = max(300, int(0.10 * len(body_n)))
    first = msg.strip().split("\n", 1)[0].strip()
    if HEADING_OK_RE.match(first) or CLOSER_OK_RE.match(first):
        allow += len(_norm(first))
    ok = residue <= allow
    return ok, (
        f"meta-tax: {residue} chars of your reply were not the beat (allowance {allow}). "
        "The beat is what the player reads; nothing else goes in the chat. Re-send the beat "
        f"body and menu, verbatim from {L.get('draft')}, and nothing else."
    )


def _check_meta_leak_chat(L, msg):
    rx = getattr(pl, "META_RE", None) if pl else None
    rx = rx or META_RE
    m = rx.search(msg)
    ok = m is None
    quote = m.group(0) if m else ""
    return ok, (
        f"meta-leak-chat: your reply contains machine vocabulary ('{quote}'). The player "
        "never sees the machinery — re-send the beat body and menu only, nothing else."
    )


_METER_CHECKS = [
    ("not-lint-clean", _check_not_lint_clean),
    ("no-reader", _check_no_reader),
    ("not-saved", _check_not_saved),
    ("stale-resume", _check_stale_resume),
    ("plan-untouched", _check_plan_untouched),
    ("not-delivered", _check_not_delivered),
    ("meta-tax", _check_meta_tax),
    ("meta-leak-chat", _check_meta_leak_chat),
]


def _over_budget_status(L):
    """-> ("ok"|"advisory"|"block", text_or_None). Advisory (additionalContext,
    not a block) at beat > budget; escalates to an actual block only at
    beat > budget + 1."""
    cf = chapter_file(L["story"], L["chapter"])
    plan = parse_plan(open(cf).read()) if os.path.isfile(cf) else None
    if not plan:
        return "ok", None
    budget, beat = plan["budget"], L["beat"]
    if beat > budget + 1:
        return "block", (
            f"ch{L['chapter']} beat {beat} is {beat - budget} over the budget of {budget}. "
            f"Close the chapter now: `beat.py close-chapter`, then `beat.py open-chapter --n "
            f"{L['chapter'] + 1} --title ... --budget ... --clock ...`."
        )
    if beat > budget:
        return "advisory", (
            f"ch{L['chapter']} beat {beat} is 1 over the budget of {budget} — the NEXT beat "
            "must be type=close."
        )
    return "ok", None


def autolog(L):
    story = L["story"]
    path = os.path.join(story_dir(story), "_craft_log.md")
    text = open(path).read() if os.path.isfile(path) else "# Craft Log\n\n## Standing watchlist\n\n## Log\n"
    if not re.search(r"^## Log\s*$", text, re.M):
        text = text.rstrip("\n") + "\n\n## Log\n"
    draft_chars = L.get("draft_chars", 0) or 0
    ceiling = L.get("ceiling", 0) or 0
    turn_id = L.get("turn_id") or "-"
    reader_raw = L.get("reader")
    revisions = L.get("revisions", 0) or 0
    menu_state = "none (close)" if L.get("beat_type") == "close" else "offered"
    # L["delivered"] is set by `cmd_close`; absent only on ledgers closed
    # before this field existed, where "delivered" (the old, only behaviour)
    # remains the correct default.
    delivered_word = "delivered" if L.get("delivered", True) else "NOT delivered"
    # F7: by the time autolog runs, reader_gate_reason() has already passed —
    # so `reader == "findings"` here only ever means the beat shipped AT the
    # revision limit with residual findings still on file (rule 5). Log that
    # honestly instead of collapsing it to the same "FINDINGS" word a
    # mid-revision beat would have shown before the gate caught it.
    if reader_raw == "findings":
        n = L.get("reader_findings") or 0
        plural = "revision" if revisions == 1 else "revisions"
        reader_desc = f"{n} finding(s), shipped after {revisions} {plural}"
    else:
        reader_desc = (reader_raw or "none").upper()
    line = (
        f"- {today()} ch{L['chapter']} b{L['beat']} {L.get('beat_type', '?')} "
        f"{draft_chars:,}/{ceiling:,} · {turn_id} {delivered_word} · lint clean"
        + (f" ({revisions} retry)" if revisions and reader_raw != "findings" else "")
        + f" · reader {reader_desc} · menu {menu_state}"
    )
    new_text = re.sub(r"(^## Log\s*\n)", r"\1" + line + "\n", text, count=1, flags=re.M)
    if new_text == text:
        new_text = text.rstrip("\n") + "\n" + line + "\n"
    vault_write(story, path, new_text, mode="overwrite")


def do_block(L, reason, cid=None, retry=False):
    """`cid` identifies WHICH check failed (a `_METER_CHECKS` id, or
    'anti-bypass'/'over-budget' for the two callers outside that loop).
    `MAX_BLOCKS` counts CONSECUTIVE blocks on the SAME check, not blocks in
    total — the old `L["blocks"] = L.get("blocks", 0) + 1` incremented on
    every call regardless of which check failed, so a beat that failed check A
    once and then check B once had already "used up" both of MAX_BLOCKS's two
    slots and released to advisory-only on B — meaning the meter could enforce
    at most one of its eight checks per beat, whichever failed twice in a row
    by coincidence. Real progress (a DIFFERENT check now failing) resets the
    streak; only the SAME check failing MAX_BLOCKS+1 times running downgrades.

    F5: `retry` is True when this Stop invocation carries `stop_hook_active`
    (the harness already blocked once THIS turn and is re-running it). Every
    guard in this file exists to prevent a Stop-hook deadlock, and blocking
    AGAIN on a retry is exactly that risk — so on a retry a failing check
    never becomes `decision:block`. It is reported, at most, as an
    `additionalContext` advisory, the ledger's blocks/last_block counters
    are left untouched (they track the CONSECUTIVE-same-check downgrade
    above, which does not apply here), and the turn is allowed to end. This
    is also what fixed the observed bug: a beat blocked once (a real
    finding), the GM corrected it and re-shipped, and the retry — under the
    OLD unconditional `stop_hook_active -> exit 0` — never re-ran the eight
    checks at all, so a now-clean beat's autolog line never landed. See
    cmd_meter: it runs the full eight-check pass on a retry exactly as on a
    fresh Stop, and only reaches `_meter_pass` (autolog + closed:true) when
    every one of them is clean."""
    if retry:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": f"METER (not re-blocking a stop_hook_active retry): {reason}",
        }}))
        sys.exit(0)
    if L is not None:
        if cid is not None and L.get("last_block") == cid:
            L["blocks"] = L.get("blocks", 0) + 1
        else:
            L["blocks"] = 1
        L["last_block"] = cid
        save_ledger(L["story"], L)
        if L["blocks"] > MAX_BLOCKS:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": (
                    f"METER (advisory, released after {MAX_BLOCKS + 1} consecutive blocks "
                    f"on the same check): {reason}"
                ),
            }}))
            sys.exit(0)
    print(json.dumps({"decision": "block", "reason": f"BEAT NOT COMPLETE — do this, then stop:\n{reason}"}))
    sys.exit(0)


def _meter_pass(L, advisory_text=None):
    autolog(L)
    L["closed"] = True
    save_ledger(L["story"], L)
    if advisory_text:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": f"METER: {advisory_text}",
        }}))
    sys.exit(0)


def cmd_meter():
    """Decision tree (see the module NOTE for why 'closed' alone isn't enough):
      0. F1 session scoping: a ledger owned by a DIFFERENT Claude Code
         session (its `session_id` set and unequal to this payload's) is not
         judged at all — no block, no advisory, no ledger write, completely
         silent on stdout (only a stderr note). This is checked before
         everything else, including retry — a foreign session's beat is
         never this session's business either way.
      1. F5: `stop_hook_active` (this is a RETRY after an earlier block THIS
         turn) no longer exits immediately — it sets `retry=True` and falls
         through to the same checks below. `do_block` never re-blocks on a
         retry (see its own docstring), so the only observable difference is
         that a retry can never emit `decision:block` — a still-failing
         check becomes an advisory, and a now-clean beat still autologs.
      2. No ledger -> anti-bypass only (block iff beat-shaped prose AND a
         menu signature — the plan delta; a short or non-prose reply is never
         second-guessed).
      3. Ledger closed AND the message does not contain a slice of ITS draft
         -> the ledger is stale (an out-of-band turn, or worse); anti-bypass
         only, same rule as #2.
      4. Otherwise (ledger open, or closed-and-this-IS-the-beat-it-tracked)
         -> the eight ordered checks, first failure blocks (or, on retry,
         advises); then the over-budget advisory/block; then autolog + close
         on a clean pass.
    """
    global _STDOUT_IS_JSON
    _STDOUT_IS_JSON = True
    payload = json.load(sys.stdin)
    retry = bool(payload.get("stop_hook_active"))
    msg = payload.get("last_assistant_message") or ""

    def anti_bypass(ledger):
        if looks_like_beat_prose(msg) and has_menu_signature(msg):
            do_block(ledger, (
                "PROSE SHIPPED OUTSIDE THE BEAT LOOP. Beats are written by the narrator agent, "
                "not by you. Run `beat.py open --type <T>` and follow the runbook, then re-ship "
                "this beat."
            ), cid="anti-bypass", retry=retry)
        sys.exit(0)

    story = resolve_story()
    L = load_ledger(story) if story else None

    # F1: session-scoped ledger. Silent to stdout either way (Stop's JSON
    # contract) — the only trace of a skipped foreign-session turn is this
    # stderr line, and neither `blocks` nor `closed` nor the autolog is
    # touched.
    if L is not None:
        owner = (L.get("session_id") or "").strip()
        payload_sid = (payload.get("session_id") or "").strip()
        if owner and payload_sid and owner != payload_sid:
            print(
                f"!! BEAT.PY: Stop meter skipped for ch{L.get('chapter')} b{L.get('beat')} — "
                f"the open beat is owned by session {owner}, this Stop is session {payload_sid}. "
                "Not blocking or advising a foreign session.",
                file=sys.stderr,
            )
            sys.exit(0)

    if L is None:
        anti_bypass(None)

    sl = _middle_slice(L.get("draft"))
    matches_this_ledger = bool(sl) and sl in _norm(msg)
    if L.get("closed") and not matches_this_ledger:
        anti_bypass(L)

    for cid, fn in _METER_CHECKS:
        ok, reason = fn(L, msg)
        if not ok:
            do_block(L, reason, cid=cid, retry=retry)

    status, text = _over_budget_status(L)
    if status == "block":
        do_block(L, text, cid="over-budget", retry=retry)
    _meter_pass(L, advisory_text=text if status == "advisory" else None)


# --------------------------------------------------------------------------
# Selftest
# --------------------------------------------------------------------------
def _selftest_plan_roundtrip(fixtures_dir):
    ok = True
    plan_ok = os.path.join(fixtures_dir, "plan_ok.md")
    plan_bad = os.path.join(fixtures_dir, "plan_malformed.md")
    if os.path.isfile(plan_ok):
        d = parse_plan(open(plan_ok).read())
        good = d is not None and d.get("turns") and d.get("clock")
        print(f"SELFTEST plan_ok round-trip -> {'PASS' if good else 'FAIL'}")
        ok &= bool(good)
        if d is not None:
            rendered = render_plan(d)
            d2 = parse_plan(rendered)
            rt = d2 is not None and d2["turns"] == d["turns"]
            print(f"SELFTEST plan_ok re-render+re-parse stable -> {'PASS' if rt else 'FAIL'}")
            ok &= rt
    else:
        print("SELFTEST plan_ok.md: SKIP (fixture missing)")
    if os.path.isfile(plan_bad):
        warnings.clear()
        d = parse_plan(open(plan_bad).read())
        good = d is None and len(warnings) > 0
        print(f"SELFTEST plan_malformed -> None + loud warning -> {'PASS' if good else 'FAIL'}")
        ok &= good
    else:
        print("SELFTEST plan_malformed.md: SKIP (fixture missing)")
    return ok


def _selftest_obligation_selection():
    plan = {
        "budget": 6,
        "turns": [
            {"id": "T1", "text": "t1", "status": "delivered", "earliest": 1, "latest": 2},
            {"id": "T2", "text": "t2", "status": "open", "earliest": 2, "latest": 4},
            {"id": "T3", "text": "t3", "status": "open", "earliest": 3, "latest": 6},
        ],
    }
    t, forced, _ = select_obligation(plan, 3)
    ok1 = t is not None and t["id"] == "T2" and not forced
    print(f"SELFTEST obligation@beat3 picks T2 -> {'PASS' if ok1 else 'FAIL'} (got {t and t['id']})")
    plan2 = {
        "budget": 6,
        "turns": [
            {"id": "T1", "text": "t1", "status": "delivered", "earliest": 1, "latest": 2},
            {"id": "T2", "text": "t2", "status": "delivered", "earliest": 2, "latest": 4},
            {"id": "T3", "text": "t3", "status": "delivered", "earliest": 3, "latest": 6},
        ],
    }
    t2, forced2, _ = select_obligation(plan2, 7)
    ok2 = forced2 is True
    print(f"SELFTEST obligation@beat7 (all delivered, over budget) forces close -> {'PASS' if ok2 else 'FAIL'}")
    return ok1 and ok2


def _selftest_open_chapter_refuses_empty_clock(tmp_story):
    old_argv_story = os.environ.get("CLAUDE_PROJECT_DIR")
    ok = not _clock_is_real("")
    ok &= not _clock_is_real("soon, probably")
    ok &= _clock_is_real("Saturday 10:00")
    print(f"SELFTEST open-chapter clock validation -> {'PASS' if ok else 'FAIL'}")
    return ok


def _selftest_plan_sanitisation():
    plan = {
        "chapter": 5, "title": "Restricted", "budget": 6,
        "clock": "budget 6 --> 12 escalation", "close": "close it",
        "turns": [{"id": "T1", "text": "fact > changes -- twice", "status": "open", "earliest": 1, "latest": 2}],
        "forbidden": [], "rescope": [],
    }
    rendered = render_plan(plan)
    ok = rendered is not None and "-->" not in rendered[:-len("plan:end -->")]
    parsed = parse_plan(rendered) if rendered else None
    ok &= parsed is not None
    print(f"SELFTEST plan sanitisation strips '-->' and still parses -> {'PASS' if ok else 'FAIL'}")
    return ok


def _selftest_vault_write_transport():
    """F4 regression: `vault_write`'s post-write verification used to be a
    SINGLE immediate read-after-write, which the real dry run showed can see
    stale content from the Obsidian app's own async write and treat a real
    success as a failure. These are offline, pure-function tests of the
    poll/dedupe machinery (`_poll_for_write`, `_dedupe_if_doubled`) — no
    Obsidian CLI involved, so they run in any CI checkout; the CLI transport
    itself (the `eval` + AWAITED `app.vault.adapter.write/append` switch)
    was measured directly against the real vault (0 races / 50 trials,
    create/overwrite + append + rapid back-to-back appends) as the plan's
    own verification step, not something this offline suite can re-run."""
    import tempfile
    import threading

    ok = True
    tmpdir = tempfile.mkdtemp(prefix="beatpy_vaultwrite_")
    try:
        # --- _poll_for_write: already-landed content -> True immediately ---
        p1 = os.path.join(tmpdir, "already.md")
        open(p1, "w").write("hello world\n")
        t0 = time.time()
        got = _poll_for_write(p1, "hello world\n", "overwrite", timeout=1.0, interval=0.05)
        dt = time.time() - t0
        ok &= _assert(got and dt < 0.5,
                      f"F4: _poll_for_write returns True immediately when content already matches "
                      f"(got={got}, dt={dt:.3f}s)")

        # --- _poll_for_write: append-mode match on the tail ---
        p1b = os.path.join(tmpdir, "already_append.md")
        open(p1b, "w").write("### Beat 1\nSome prose here.\n")
        got_a = _poll_for_write(p1b, "Some prose here.\n", "append", timeout=1.0, interval=0.05)
        ok &= _assert(got_a, "F4: _poll_for_write (append mode) matches on the tail slice")

        # --- _poll_for_write: a write that lands LATE, within the timeout ---
        p2 = os.path.join(tmpdir, "delayed.md")
        open(p2, "w").write("")

        def _delayed_write():
            time.sleep(0.15)
            open(p2, "w").write("landed late\n")

        th = threading.Thread(target=_delayed_write)
        th.start()
        t0 = time.time()
        got2 = _poll_for_write(p2, "landed late\n", "overwrite", timeout=1.0, interval=0.05)
        dt2 = time.time() - t0
        th.join()
        ok &= _assert(got2 and dt2 >= 0.15,
                      f"F4: _poll_for_write picks up a write that lands within the timeout "
                      f"(got={got2}, dt={dt2:.3f}s)")

        # --- _poll_for_write: content that never lands -> False, bounded by timeout ---
        p3 = os.path.join(tmpdir, "never.md")
        open(p3, "w").write("something else entirely\n")
        t0 = time.time()
        got3 = _poll_for_write(p3, "this never arrives\n", "overwrite", timeout=0.3, interval=0.05)
        dt3 = time.time() - t0
        ok &= _assert(not got3 and 0.25 <= dt3 <= 1.0,
                      f"F4: _poll_for_write times out (False) when the content never lands "
                      f"(got={got3}, dt={dt3:.3f}s)")

        # --- _dedupe_if_doubled: the CLI write landed late, doubling the block ---
        p4 = os.path.join(tmpdir, "doubled.md")
        block = "### Beat 3 — Something (2026-01-01)\nThe prose for this beat.\n"
        open(p4, "w").write("prefix\n\n" + block + "\n" + block + "suffix\n")
        warnings.clear()
        _dedupe_if_doubled(p4, block, "append", label="doubled.md")
        after4 = open(p4).read()
        ok &= _assert(
            after4.count(block.strip()) == 1 and "landed late" in "\n".join(warnings),
            f"F4: _dedupe_if_doubled removes a late-landed duplicate and warns loudly "
            f"(count={after4.count(block.strip())}, warned={'landed late' in ' '.join(warnings)})"
        )

        # --- _dedupe_if_doubled: only ONE occurrence -> no-op ---
        p5 = os.path.join(tmpdir, "single.md")
        open(p5, "w").write("prefix\n\n" + block + "suffix\n")
        before5 = open(p5).read()
        _dedupe_if_doubled(p5, block, "append", label="single.md")
        after5 = open(p5).read()
        ok &= _assert(after5 == before5, "F4: _dedupe_if_doubled is a no-op when the block appears once")

        # --- _dedupe_if_doubled: overwrite mode never dedupes (can't "double") ---
        p6 = os.path.join(tmpdir, "overwrite_doubled.md")
        content6 = "same content\n"
        open(p6, "w").write(content6 + content6)
        before6 = open(p6).read()
        _dedupe_if_doubled(p6, content6, "overwrite", label="overwrite_doubled.md")
        after6 = open(p6).read()
        ok &= _assert(after6 == before6, "F4: _dedupe_if_doubled is a no-op in overwrite mode")
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmpdir, ignore_errors=True)
    return ok


def _run_beat(env, *args, cwd=None, timeout=60):
    """Invoke THIS beat.py as a fresh subprocess with the given environment —
    the only way to test against a different CLAUDE_PROJECT_DIR in-process,
    since prose-lint.py resolves its own VAULT constant at import time and a
    live global-swap here would desync the two modules."""
    r = subprocess.run(
        [sys.executable, os.path.join(_HOOKS_DIR, "beat.py")] + list(args),
        env=env, cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )
    return r


def _selftest_npc_warn():
    """A8 regression: an --npc slug that matches no character file must warn
    LOUDLY (this file's own "degrade LOUDLY" contract) instead of being
    silently dropped — the brief used to ship an empty '(no named on-stage
    characters this beat)' section with no signal that a requested
    character's sheet never made it in, and `cmd_open`'s own printed summary
    never named which characters actually resolved."""
    ok = True
    real_root = _selftest_repo_root()
    tmp_root, story_path, story = _scaffold_tmp_story(real_root)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = tmp_root
    try:
        _run_beat(env, "open-chapter", "--n", "1", "--title", "Opening", "--budget", "4",
                  "--clock", "By midnight, or the gate closes for good.",
                  "--turns", "the door opens; something changes")
        r = _run_beat(env, "open", "--type", "scene", "--npc", "nobody_by_this_name",
                      "--input", "look around")
        ok &= _assert(
            "--npc 'nobody_by_this_name' matched no file" in r.stdout and "ONSTAGE" in r.stdout,
            f"open --npc <unmatched slug> -> loud warning + ONSTAGE line printed (out={r.stdout!r})"
        )
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp_root, ignore_errors=True)
    return ok


def _selftest_characters_on_stage():
    """F3 regression: on-stage derivation used to be a bare capitalised-token
    regex (`\\b[A-Z][a-z]{2,}\\b`) over the last two beats' raw text — so a
    beat mentioning "Bell Street", "Buy a stick" and "Merchant Court", plus
    the literal `**Choices offered:**` marker, produced onstage=Bell,Buy,
    Choices,Court, each triggering a loud (and correct-for-its-own-logic,
    but useless) "--npc 'X' matched no file" warning — and the PC's own
    sheet was never in the brief unless passed explicitly via --npc, even
    though the PC is on stage every beat by construction. The roster is now
    built from characters/*.md and matched by NAME (title / **Name**: /
    name:) against the player's input and the last beats' text; the fake
    prior beat below reuses the exact strings the old regex false-positived
    on to prove none of them survive as slugs."""
    ok = True
    real_root = _selftest_repo_root()
    tmp_root, story_path, story = _scaffold_tmp_story(real_root)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = tmp_root
    cdir = os.path.join(story_path, "characters")
    cf = os.path.join(story_path, "chapters", "chapter_1.md")
    try:
        _run_beat(env, "open-chapter", "--n", "1", "--title", "Opening", "--budget", "4",
                  "--clock", "By midnight, or the gate closes for good.",
                  "--turns", "the door opens; something changes")

        with open(os.path.join(cdir, "mair.md"), "w") as f:
            f.write("---\ntype: character\n---\n\n# Mair Tully\n\n## Identity\n\n- **Name**: Mair Tully\n")
        with open(os.path.join(cdir, "kessler.md"), "w") as f:
            f.write("---\ntype: character\n---\n\n# Rill Kessler\n\n## Identity\n\n- **Name**: Rill Kessler\n")

        text = open(cf).read()
        open(cf, "w").write(
            text.rstrip("\n") + "\n\n### Beat 1 — Test (" + today() + ")\n"
            '<!-- beat: type=scene obligation="test" onstage= -->\n\n'
            "She walked down Bell Street to buy a stick of chalk from the stall at Merchant "
            "Court.\n\n**Choices offered:**\n1. Go home.\n2. Keep walking.\n"
        )

        r = _run_beat(env, "open", "--type", "scene", "--input", "I ask Mair")
        onstage_line = next((ln for ln in r.stdout.splitlines() if ln.startswith("ONSTAGE")), "")
        slugs = onstage_line.split(None, 1)[-1].strip() if onstage_line else ""
        ok &= _assert(
            slugs == "player_character, mair",
            f"characters_on_stage: 'I ask Mair' -> onstage is exactly "
            f"'player_character, mair', PC always first (got {slugs!r})"
        )
        ok &= _assert(
            "matched no file" not in r.stdout,
            f"characters_on_stage: no spurious --npc warnings with no --npc passed "
            f"(out={r.stdout!r})"
        )
        for false_slug in ("bell", "buy", "choices", "court", "street", "stick", "merchant"):
            ok &= _assert(
                false_slug not in slugs.lower(),
                f"characters_on_stage: raw capitalised prose ('Bell Street' / 'Buy a stick' / "
                f"'**Choices offered:**' / 'Merchant Court') produces no false slug '{false_slug}' "
                f"(onstage={slugs!r})"
            )
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp_root, ignore_errors=True)
    return ok


def _selftest_stamp_subcommand():
    """F2 regression: `beat.py stamp <path>` is the GM-side fallback for
    when a subagent's own PostToolUse hook (added to narrator.md's and
    second-reader.md's frontmatter) does not fire on this harness/build —
    it runs the exact --post routing WITHOUT stdin: draft -> lint + stamp,
    reader -> parse_verdict + stamp, exit 2 on FAIL / 0 on pass, and a path
    that is neither a draft nor a reader-verdict file is a silent no-op."""
    ok = True
    real_root = _selftest_repo_root()
    tmp_root, story_path, story = _scaffold_tmp_story(real_root)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = tmp_root
    ledger_file = os.path.join(story_path, "scratchpad", LEDGER_NAME)

    def _L():
        return json.load(open(ledger_file))

    try:
        _run_beat(env, "open-chapter", "--n", "1", "--title", "Opening", "--budget", "4",
                  "--clock", "By midnight, or the gate closes for good.",
                  "--turns", "the door opens; something changes")
        _run_beat(env, "open", "--type", "scene", "--input", "look around")
        L = _L()
        draft_path = L["draft"]
        draft_text = (
            '<!-- beat: type=scene obligation="the door opens" onstage= -->\n'
            "The corridor smelled of rain and old paper. Something ahead did not want to be "
            "found, and the silence past the threshold had a shape to it, almost a weight. He "
            "went in anyway, one hand trailing the wall.\n\n"
            "**Choices offered:**\n1. Push forward.\n2. Call out.\n3. Turn back.\n"
        )
        open(draft_path, "w").write(draft_text)

        # --- clean draft -> exit 0, stamps the ledger ---
        r = _run_beat(env, "stamp", draft_path)
        L2 = _L()
        ok &= _assert(
            r.returncode == 0 and "LINT OK" in r.stdout and L2.get("lint") == "ok",
            f"F2: stamp on a clean draft -> exit0, LINT OK, ledger stamped "
            f"(rc={r.returncode}, out={r.stdout[:120]!r}, lint={L2.get('lint')!r})"
        )

        # --- over-ceiling draft -> exit 2 ---
        good_fixture = os.path.join(_HOOKS_DIR, "fixtures", "ch3b3_good.md")
        filler = getattr(pl, "_FILLER", "") if pl else ""
        big_text = open(good_fixture).read().rstrip("\n") + "\n\n" + filler + \
            "\n\n**Choices offered:**\n1. a\n2. b\n"
        open(draft_path, "w").write(big_text)
        r = _run_beat(env, "stamp", draft_path)
        ok &= _assert(
            r.returncode == 2 and "size-ceiling" in r.stdout,
            f"F2: stamp on an over-ceiling draft -> exit2, size-ceiling reported "
            f"(rc={r.returncode}, out={r.stdout[:160]!r})"
        )
        open(draft_path, "w").write(draft_text)
        r = _run_beat(env, "stamp", draft_path)
        ok &= _assert(r.returncode == 0,
                      f"F2: stamp re-clears once the draft is fixed (rc={r.returncode})")

        # --- good verdict -> exit 0, stamps ---
        L3 = _L()
        reader_out = L3.get("reader_out")
        if not reader_out:
            _run_beat(env, "reader-brief")
            L3 = _L()
            reader_out = L3.get("reader_out")
        open(reader_out, "w").write(
            "VERDICT: CLEAN\nOBLIGATION: delivered\nCLOCK: intact\nMENU: 3 distinct\n")
        r = _run_beat(env, "stamp", reader_out)
        L4 = _L()
        ok &= _assert(
            r.returncode == 0 and "VERDICT: CLEAN" in r.stdout and L4.get("reader") == "clean",
            f"F2: stamp on a good verdict -> exit0, ledger stamped reader=clean "
            f"(rc={r.returncode}, reader={L4.get('reader')!r})"
        )

        # --- 5-finding verdict -> exit 2 (cap is 4) ---
        five_findings = (
            "VERDICT: 5 FINDING(S)\nOBLIGATION: delivered\nCLOCK: intact\nMENU: 3 distinct\n"
            + "".join(
                f'[F{i}] QUOTE   "x"\n     RULE    r\n     WHY     w\n     FIX     f\n'
                for i in range(1, 6)
            )
        )
        open(reader_out, "w").write(five_findings)
        r = _run_beat(env, "stamp", reader_out)
        ok &= _assert(
            r.returncode == 2 and "cap is" in r.stdout,
            f"F2: stamp on a 5-finding verdict -> exit2, cap named "
            f"(rc={r.returncode}, out={r.stdout[:160]!r})"
        )

        # --- non-beat path -> silent, exit 0 ---
        bible_path = os.path.join(story_path, "STORY_BIBLE.md")
        r = _run_beat(env, "stamp", bible_path)
        ok &= _assert(
            r.returncode == 0 and not r.stdout.strip(),
            f"F2: stamp on a non-beat path -> silent, exit0 (rc={r.returncode}, out={r.stdout!r})"
        )
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp_root, ignore_errors=True)
    return ok


def _selftest_close_chapter_blank_outline_row():
    r"""F6: `_scaffold_tmp_story` copies `_template/` verbatim for the story,
    so `story_outline.md`'s '## Estimated Chapter Breakdown' table still has
    the template's own blank row (`|         |       |     |       |        |`
    — no leading `| 1 |`) exactly as a real fresh scaffold would (this is
    what the two live dry runs actually had). `cmd_close_chapter`'s
    `row_re = re.compile(rf"^\|\s*{N}\s*\|.*\|$")` cannot match a row whose
    first cell is empty, so this must WARN loudly (not crash), and a
    subsequent `open-chapter --n 2` must still succeed — `close-chapter`
    never touching story_outline.md's Status/Beats cell is a cosmetic gap,
    not a blocker."""
    ok = True
    real_root = _selftest_repo_root()
    tmp_root, story_path, story = _scaffold_tmp_story(real_root)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = tmp_root
    outline = os.path.join(story_path, "story_outline.md")
    try:
        ok &= _assert(
            os.path.isfile(outline) and re.search(r"^\|\s*\|\s*\|\s*\|\s*\|\s*\|\s*$", open(outline).read(), re.M),
            "F6 setup: the scaffolded story_outline.md still has the template's blank "
            "breakdown row (no leading chapter number)"
        )
        r = _run_beat(env, "open-chapter", "--n", "1", "--title", "Opening", "--budget", "1",
                      "--clock", "By midnight, or the gate closes for good.",
                      "--turns", "the door opens; something changes")
        ok &= _assert(r.returncode == 0, f"F6: open-chapter ch1 succeeds (rc={r.returncode})")

        r2 = _run_beat(env, "close-chapter")
        ok &= _assert(
            r2.returncode == 0 and "!! BEAT.PY ERROR" not in r2.stdout and "Traceback" not in r2.stderr,
            f"F6: close-chapter with a blank outline row does not crash (rc={r2.returncode}, "
            f"out={r2.stdout!r}, err={r2.stderr!r})"
        )
        ok &= _assert(
            "story_outline.md has no breakdown row for chapter 1" in r2.stdout,
            f"F6: close-chapter WARNS loudly about the missing breakdown row, rather than "
            f"silently skipping it (out={r2.stdout!r})"
        )
        ok &= _assert(
            "Chapter 1 closed" in r2.stdout,
            f"F6: close-chapter still completes and reports the chapter closed (out={r2.stdout!r})"
        )

        r3 = _run_beat(env, "open-chapter", "--n", "2", "--title", "Second", "--budget", "4",
                       "--clock", "Sunday noon, or the deal is off.",
                       "--turns", "a new thing")
        ok &= _assert(
            r3.returncode == 0 and "Chapter 2 opened" in r3.stdout,
            f"F6: open-chapter --n 2 still succeeds after close-chapter warned "
            f"(rc={r3.returncode}, out={r3.stdout!r})"
        )
        cf2 = os.path.join(story_path, "chapters", "chapter_2.md")
        ok &= _assert(
            os.path.isfile(cf2) and parse_plan(open(cf2).read()) is not None,
            "F6: chapter_2.md exists with a parseable plan block"
        )
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp_root, ignore_errors=True)
    return ok


def _selftest_close_not_delivered_and_autolog():
    """T5 regression (previously untested): `beat.py close --not-delivered`
    leaves the plan turn `status: open` (on purpose — the turn genuinely
    wasn't delivered, so ticking it anyway would lie about the story) but
    still has to satisfy `_check_plan_untouched` (via `beats_used == beat`,
    the "close ran at all" signal — see that function's own docstring) so the
    Stop meter doesn't block on a beat that was closed correctly, just closed
    without delivering. AND `autolog()`'s `delivered_word` — "delivered" vs
    "NOT delivered" in the `_craft_log.md` line — which nothing asserted
    before this: the existing round-trip/hooks tests only checked that SOME
    autolog line landed, never which word it carried."""
    ok = True
    real_root = _selftest_repo_root()
    tmp_root, story_path, story = _scaffold_tmp_story(real_root)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = tmp_root
    cf = os.path.join(story_path, "chapters", "chapter_1.md")
    gs = os.path.join(story_path, "game_state.md")
    craft_log = os.path.join(story_path, "_craft_log.md")
    ledger_file = os.path.join(story_path, "scratchpad", LEDGER_NAME)

    def _L():
        return json.load(open(ledger_file))

    def _ship_one_beat(not_delivered, verdict_text=None):
        """open -> draft -> reader-brief -> fake verdict (clean by default,
        or `verdict_text` verbatim) -> append -> close [--not-delivered] ->
        meter (msg = draft body + menu). Returns (close_stdout,
        ledger_after_close, meter_response)."""
        r_open = _run_beat(env, "open", "--type", "scene", "--input", "look around")
        L = _L()
        draft_text = (
            '<!-- beat: type=scene obligation="the door opens" onstage= -->\n'
            "The corridor smelled of rain and old paper. Something ahead did not want to "
            "be found, and the quiet past the threshold had a shape to it, almost a "
            "weight. He went in anyway, one hand trailing the wall.\n\n"
            "**Choices offered:**\n1. Push forward.\n2. Call out.\n3. Turn back.\n"
        )
        open(L["draft"], "w").write(draft_text)
        _run_beat(env, "reader-brief")
        L = _L()
        if L.get("reader_out"):
            open(L["reader_out"], "w").write(
                verdict_text or
                "VERDICT: CLEAN\nOBLIGATION: delivered\nCLOCK: intact\nMENU: 3 distinct\n")
            okp, parsed, _err = parse_verdict(open(L["reader_out"]).read())
            L["reader"] = "clean" if (okp and parsed["clean"]) else "findings"
            L["reader_findings"] = parsed.get("n", 0) if okp else None
            L["reader_flags"] = parsed.get("flags", {}) if okp else {}
            if L["reader"] == "findings":
                # F7: a findings verdict only satisfies reader_gate_reason
                # (so `append` below can succeed) once revisions has hit the
                # limit — mirrors the real "ship at the limit" path.
                L["revisions"] = L.get("revisions_max", MAX_REVISIONS)
        L["draft_sha"] = sha_norm(draft_text)
        json.dump(L, open(ledger_file, "w"), indent=2)
        _run_beat(env, "append")
        gtext = open(gs).read()
        gtext = re.sub(r"^- \*\*Position:\*\*.*\n", "", gtext, flags=re.M)
        resume_line = f"- **Position:** ch {L['chapter']} · beat {L['beat']} · budget 4 · type scene\n"
        # The template's heading is "## Resume — read this first on a cold
        # start", not a bare "## Resume" — match the heading LINE (whatever
        # follows on it), not an exact "## Resume$".
        if re.search(r"^## Resume\b.*$", gtext, re.M):
            gtext = re.sub(r"(^## Resume\b.*\n)", r"\1" + resume_line, gtext, count=1, flags=re.M)
        else:
            gtext += "\n## Resume\n" + resume_line
        open(gs, "w").write(gtext)
        close_args = ["close", "--not-delivered"] if not_delivered else ["close"]
        r_close = _run_beat(env, *close_args)
        L_after_close = _L()
        body_text = pl_strip_meta(draft_text)
        menu_text = "**Choices offered:**\n1. Push forward.\n2. Call out.\n3. Turn back.\n"
        r_meter = _run_hook(env, "--meter", {"last_assistant_message": body_text + "\n\n" + menu_text})
        return r_close, L_after_close, r_meter

    try:
        _run_beat(env, "open-chapter", "--n", "1", "--title", "Opening", "--budget", "4",
                  "--clock", "By midnight, or the gate closes for good.",
                  "--turns", "the door opens; something changes")

        # --- beat 1: NOT delivered ---
        r_close, L1, r_meter1 = _ship_one_beat(not_delivered=True)
        ok &= _assert("NOT DELIVERED" in r_close.stdout,
                      f"close --not-delivered: prints NOT DELIVERED (out={r_close.stdout!r})")
        ok &= _assert(L1.get("delivered") is False and L1.get("beats_used") == L1.get("beat"),
                      f"close --not-delivered: ledger delivered=False, beats_used==beat "
                      f"(delivered={L1.get('delivered')}, beats_used={L1.get('beats_used')}, "
                      f"beat={L1.get('beat')})")
        plan1 = parse_plan(open(cf).read())
        t1 = next((t for t in plan1["turns"] if t["id"] == L1.get("turn_id")), None)
        ok &= _assert(t1 is not None and t1["status"] == "open",
                      f"close --not-delivered: the plan turn stays status:open, not ticked "
                      f"(turn={t1})")
        ok &= _assert(any("did not deliver" in n for n in plan1.get("rescope", [])),
                      f"close --not-delivered: a rescope note records the miss (rescope="
                      f"{plan1.get('rescope')})")
        ok &= _assert_silent(
            r_meter1, "meter: beat closed --not-delivered (plan turn still open, "
                      "beats_used==beat) -> NOT blocked on plan-untouched (T5)"
        )
        log_after_1 = open(craft_log).read()
        log_line_1 = [ln for ln in log_after_1.splitlines() if ln.startswith("- ") and "ch1 b1" in ln]
        ok &= _assert(
            bool(log_line_1) and "NOT delivered" in log_line_1[0]
            and not re.search(r"(?<!NOT )\bdelivered\b", log_line_1[0]),
            f"autolog: ch1 b1 (not-delivered close) log line says 'NOT delivered', not "
            f"'delivered' (line={log_line_1[0] if log_line_1 else None!r})"
        )

        # --- beat 2: delivered normally — the other half of the word choice ---
        r_close2, L2, r_meter2 = _ship_one_beat(not_delivered=False)
        ok &= _assert("NOT DELIVERED" not in r_close2.stdout,
                      f"close (delivered): does not print NOT DELIVERED (out={r_close2.stdout!r})")
        ok &= _assert(L2.get("delivered") is True,
                      f"close (delivered): ledger delivered=True (delivered={L2.get('delivered')})")
        ok &= _assert_silent(r_meter2, "meter: beat 2 closed normally -> silent pass")
        log_after_2 = open(craft_log).read()
        log_line_2 = [ln for ln in log_after_2.splitlines() if ln.startswith("- ") and "ch1 b2" in ln]
        ok &= _assert(
            bool(log_line_2) and "NOT delivered" not in log_line_2[0]
            and bool(re.search(r"\bdelivered\b", log_line_2[0])),
            f"autolog: ch1 b2 (normal close) log line says 'delivered', not 'NOT delivered' "
            f"(line={log_line_2[0] if log_line_2 else None!r})"
        )

        # --- beat 3: F7 point 3 — the reader's last verdict said the
        # obligation was NOT delivered, but the GM closes WITHOUT
        # --not-delivered (forgot, or disagrees). `cmd_close` must print a
        # one-line HINT naming --not-delivered — and must NOT auto-apply it:
        # the ledger's own `delivered` flag stays True, because only the GM
        # knows what actually happened on stage. ---
        r_close3, L3, r_meter3 = _ship_one_beat(
            not_delivered=False,
            verdict_text=(
                "VERDICT: 1 FINDING\nOBLIGATION: not delivered — she left before opening it\n"
                "CLOCK: intact\nMENU: 3 distinct\n"
                "[F1] QUOTE: \"she left\" / RULE: obligation / WHY: the turn was not landed "
                "/ FIX: land it next beat.\n"
            ),
        )
        ok &= _assert(
            "--not-delivered" in r_close3.stdout and "OBLIGATION: not delivered" in r_close3.stdout,
            f"close: last verdict OBLIGATION not delivered, closed without --not-delivered -> "
            f"prints a hint naming --not-delivered (out={r_close3.stdout!r})"
        )
        ok &= _assert(
            L3.get("delivered") is True,
            f"close: the OBLIGATION hint is a HINT, not auto-applied — ledger delivered stays "
            f"True since --not-delivered was not actually passed (delivered={L3.get('delivered')})"
        )
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp_root, ignore_errors=True)
    return ok


def _selftest_revision_limit_ships():
    """F7 regression: a beat whose second-reader keeps returning findings
    must never deadlock the loop. The design annex's "Explicitly rejected"
    list forbids a hard CLEAN gate ("the model would learn to satisfy the
    reader instead of writing well; only the reader's *existence* is
    enforced") — but the B9 fix reintroduced exactly that by checking
    `reader != "clean"` unconditionally in `reader_gate_reason`, so
    `beat.py append` and the Stop meter stayed blocked even after
    `revise-brief` correctly refused a third revision cycle and told the GM
    to ship. This drives two full revise-brief cycles against a findings
    verdict, checks the RULE 5 ship line and exit 0 at the limit (revisions
    are NOT incremented a third time), and checks `append` actually succeeds
    once at the limit — the observed live failure was exactly this deadlock,
    not merely a wrong message."""
    ok = True
    real_root = _selftest_repo_root()
    tmp_root, story_path, story = _scaffold_tmp_story(real_root)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = tmp_root
    cf = os.path.join(story_path, "chapters", "chapter_1.md")
    ledger_file = os.path.join(story_path, "scratchpad", LEDGER_NAME)

    def _L():
        return json.load(open(ledger_file))

    def _stamp_findings_verdict():
        """Simulate --post stamping a verdict that auto-promoted (CLOCK
        widened) — reader=="findings" even though only 1 [Fn] block is
        declared, exactly as parse_verdict folds annex §2.3's rule."""
        L = _L()
        if L.get("reader_out"):
            open(L["reader_out"], "w").write(
                "VERDICT: 1 FINDING\nOBLIGATION: delivered\nCLOCK: widened — she gave him "
                "until Sunday\nMENU: 3 distinct\n"
                "[F1] QUOTE: \"the door was open\" / RULE: clock / WHY: widened the deadline "
                "/ FIX: keep it Saturday.\n"
            )
            okp, parsed, _err = parse_verdict(open(L["reader_out"]).read())
            L["reader"] = "clean" if (okp and parsed["clean"]) else "findings"
            L["reader_findings"] = parsed.get("n", 0) if okp else None
            L["reader_flags"] = parsed.get("flags", {}) if okp else {}
            json.dump(L, open(ledger_file, "w"), indent=2)
        return L

    try:
        _run_beat(env, "open-chapter", "--n", "1", "--title", "Opening", "--budget", "4",
                  "--clock", "By midnight, or the gate closes for good.",
                  "--turns", "the door opens; something changes")
        _run_beat(env, "open", "--type", "scene", "--input", "look around")
        L = _L()
        draft_text = (
            '<!-- beat: type=scene obligation="the door opens" onstage= -->\n'
            "The corridor smelled of rain and old paper. Something ahead did not want to "
            "be found, and the quiet past the threshold had a shape to it, almost a "
            "weight. He went in anyway, one hand trailing the wall.\n\n"
            "**Choices offered:**\n1. Push forward.\n2. Call out.\n3. Turn back.\n"
        )
        open(L["draft"], "w").write(draft_text)
        _run_beat(env, "reader-brief")
        _stamp_findings_verdict()

        # Cycle 1: revisions 0 -> 1. A revision brief, never RULE 5 — this is
        # the first of two allowed cycles.
        r1 = _run_beat(env, "revise-brief")
        L1 = _L()
        ok &= _assert(
            r1.returncode == 0 and "BRIEF:" in r1.stdout and "RULE 5" not in r1.stdout
            and L1.get("revisions") == 1,
            f"revise-brief cycle 1: writes a revision brief, not RULE 5, revisions 0->1 "
            f"(rc={r1.returncode}, out={r1.stdout!r}, revisions={L1.get('revisions')})"
        )

        # The narrator "revises" (draft unchanged is fine here — only the
        # revision bookkeeping is under test), the reader runs again, still
        # findings.
        _run_beat(env, "reader-brief")
        _stamp_findings_verdict()

        # Cycle 2: revisions 1 -> 2. Still a revision brief, not RULE 5 —
        # this IS the second (last) allowed cycle.
        r2 = _run_beat(env, "revise-brief")
        L2 = _L()
        ok &= _assert(
            r2.returncode == 0 and "BRIEF:" in r2.stdout and "RULE 5" not in r2.stdout
            and L2.get("revisions") == 2,
            f"revise-brief cycle 2: writes a revision brief, not RULE 5, revisions 1->2 "
            f"(rc={r2.returncode}, out={r2.stdout!r}, revisions={L2.get('revisions')})"
        )
        _run_beat(env, "reader-brief")
        _stamp_findings_verdict()

        # A third call is AT the limit: RULE 5 ship line, exit 0, revisions
        # NOT incremented a third time — this is the exact deadlock point
        # observed live.
        r3 = _run_beat(env, "revise-brief")
        L3 = _L()
        ok &= _assert(
            r3.returncode == 0 and "RULE 5" in r3.stdout and "ship" in r3.stdout.lower()
            and "beat.py append" in r3.stdout and "do not grind" in r3.stdout.lower()
            and L3.get("revisions") == 2,
            f"revise-brief at MAX_REVISIONS: prints the RULE 5 ship line, exits 0, does not "
            f"grind a third cycle (rc={r3.returncode}, out={r3.stdout!r}, "
            f"revisions={L3.get('revisions')})"
        )

        # The chain must now actually be appendable — F7's whole point: the
        # reader gate is satisfied once findings persist AND revisions has
        # hit the limit, not only on a clean verdict.
        r_append = _run_beat(env, "append")
        landed = open(cf).read()
        ok &= _assert(
            "APPENDED" in r_append.stdout and "The corridor smelled of rain" in landed,
            f"append after the revision limit, with residual findings still on the ledger, "
            f"succeeds (F7 — no deadlock) (out={r_append.stdout!r})"
        )
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp_root, ignore_errors=True)
    return ok


def _selftest_digest_parity():
    """Compare digests(story) against the OLD craft-gate.sh's shell output for
    a live vault, read-only. This repo must never hardcode a vault path, so
    both paths come from the environment; the test skips cleanly (PASS) when
    they are not set — a plain `--selftest` run in this repo never touches
    any vault. To exercise it:
        BEAT_PY_SELFTEST_VAULT="/path/to/vault" \\
        BEAT_PY_SELFTEST_OLD_GATE="/path/to/backup/.../craft-gate.sh" \\
        python3 .claude/hooks/beat.py --selftest
    """
    old_sh = os.environ.get("BEAT_PY_SELFTEST_OLD_GATE", "")
    vault_dir = os.environ.get("BEAT_PY_SELFTEST_VAULT", "")
    if not old_sh or not vault_dir or not os.path.isfile(old_sh) or not os.path.isdir(vault_dir):
        print("SELFTEST digest parity: SKIP (set BEAT_PY_SELFTEST_VAULT + "
              "BEAT_PY_SELFTEST_OLD_GATE to run this against a live vault)")
        return True
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = vault_dir
    try:
        r = subprocess.run(["sh", old_sh], env=env, capture_output=True, text=True, timeout=20)
        old_out = r.stdout
    except Exception as e:
        print(f"SELFTEST digest parity: SKIP (old script failed: {e})")
        return True
    m = re.search(r"=== ACTIVE REGISTER[^\n]*===\n(.*)\n=== END CRAFT GATE", old_out, re.S)
    old_reg = m.group(1).strip() if m else ""

    # Fresh subprocess so prose-lint.py's own VAULT constant (import-time) and
    # this file's agree — a real-world CLAUDE_PROJECT_DIR is fixed per process.
    code = (
        "import importlib.util, json, sys\n"
        f"spec = importlib.util.spec_from_file_location('beat', {json.dumps(os.path.join(_HOOKS_DIR, 'beat.py'))})\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "story = m.resolve_story()\n"
        "blocks = m.digests(story)\n"
        "print(json.dumps([d for _, d in blocks]))\n"
    )
    r2 = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=20)
    try:
        texts = json.loads(r2.stdout.strip().splitlines()[-1])
    except Exception as e:
        print(f"SELFTEST digest parity: FAIL (could not parse digest subprocess output: {e})")
        print(f"   stdout: {r2.stdout!r}\n   stderr: {r2.stderr!r}")
        return False
    new_reg = "\n\n".join(texts).strip()

    ok = bool(old_reg) and new_reg == old_reg
    print(f"SELFTEST digest parity vs old craft-gate.sh ({len(texts)} digests) -> {'PASS' if ok else 'FAIL'}")
    if not ok:
        print(f"   old_reg len={len(old_reg)}  new_reg len={len(new_reg)}")
        for i in range(min(len(old_reg), len(new_reg))):
            if old_reg[i] != new_reg[i]:
                print(f"   first diff at char {i}: old={old_reg[max(0,i-20):i+20]!r} new={new_reg[max(0,i-20):i+20]!r}")
                break
    return ok


def _scaffold_tmp_story(root):
    """Build a throwaway VAULT under /tmp — _template/, _craft_research/ (a
    symlink; it's large, read-only reference data) and one story copied from
    _template/ — for the round-trip test. Never touches the real vault."""
    import tempfile
    import shutil as _shutil
    tmp_root = tempfile.mkdtemp(prefix="beatpy_selftest_")
    _shutil.copytree(os.path.join(root, "_template"), os.path.join(tmp_root, "_template"))
    os.symlink(os.path.join(root, "_craft_research"), os.path.join(tmp_root, "_craft_research"))
    story = "selftest_story_01"
    story_path = os.path.join(tmp_root, story)
    _shutil.copytree(os.path.join(root, "_template"), story_path)
    # minimal fills so the machinery has something to read
    mi = os.path.join(story_path, "master_index.md")
    txt = open(mi).read()
    txt = txt.replace("{{ADVENTURE_NAME}}", "Selftest Story")
    txt = txt.replace(
        "- {{as-needed modes for this story, e.g. `romance-and-intimacy`, `genre-cosmic-horror`}}",
        "- `foreshadowing-and-payoff`"
    )
    open(mi, "w").write(txt)
    gs = os.path.join(story_path, "game_state.md")
    txt = open(gs).read().replace("current_chapter: 0", "current_chapter: 1") \
                          .replace('"{{ADVENTURE_NAME}}"', '"Selftest Story"')
    open(gs, "w").write(txt)
    bible = os.path.join(story_path, "STORY_BIBLE.md")
    if os.path.isfile(bible):
        pass
    exemplars = os.path.join(story_path, "_exemplars.md")
    craft_log = os.path.join(story_path, "_craft_log.md")
    with open(craft_log, "w") as f:
        f.write("# Craft Log — Selftest Story\n\n## Standing watchlist\n\n## Log\n")
    active = os.path.join(tmp_root, "ACTIVE_GAME.md")
    with open(active, "w") as f:
        f.write(f"---\nactive_path: {story}\n---\n")
    return tmp_root, story_path, story


def _selftest_round_trip():
    """open -> (fake draft) -> reader-brief -> append -> close, driven entirely
    through subprocess CLI calls against a scaffolded TEMP story under /tmp —
    never the vault. A fresh process per step is what makes prose-lint.py's
    own VAULT constant agree with this file's, exactly as in real play."""
    ok = True
    real_root = _selftest_repo_root()
    tmp_root, story_path, story = _scaffold_tmp_story(real_root)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = tmp_root
    cf = os.path.join(story_path, "chapters", "chapter_1.md")
    ledger_file = os.path.join(story_path, "scratchpad", LEDGER_NAME)

    def _L():
        return json.load(open(ledger_file)) if os.path.isfile(ledger_file) else None

    try:
        r = _run_beat(env, "open-chapter", "--n", "1", "--title", "Opening", "--budget", "4",
                      "--clock", "By midnight, or the gate closes for good.",
                      "--turns", "the door opens; something changes")
        plan_written = os.path.isfile(cf) and parse_plan(open(cf).read()) is not None
        print(f"SELFTEST round-trip open-chapter writes a parseable plan -> {'PASS' if plan_written else 'FAIL'}")
        if not plan_written:
            print(f"   stdout: {r.stdout!r}\n   stderr: {r.stderr!r}")
        ok &= plan_written

        r = _run_beat(env, "open", "--type", "scene", "--input", "look around")
        L = _L()
        opened_ok = L is not None and L["beat"] == 1 and os.path.isfile(L["brief"])
        print(f"SELFTEST round-trip open writes ledger + brief -> {'PASS' if opened_ok else 'FAIL'}")
        if not opened_ok:
            print(f"   stdout: {r.stdout!r}\n   stderr: {r.stderr!r}")
        ok &= opened_ok
        if not opened_ok:
            return ok

        draft_text = (
            '<!-- beat: type=scene obligation="the door opens" onstage= -->\n'
            "The corridor smells of rain and old paper. Something ahead does not want to be found.\n\n"
            "**Choices offered:**\n1. Push forward.\n2. Call out.\n3. Turn back.\n"
        )
        with open(L["draft"], "w") as f:
            f.write(draft_text)

        r = _run_beat(env, "reader-brief")
        L = _L()
        lint_ok = L.get("lint") == "ok"
        print(f"SELFTEST round-trip reader-brief lints clean -> {'PASS' if lint_ok else 'FAIL'}")
        if not lint_ok:
            print(f"   stdout: {r.stdout!r}\n   stderr: {r.stderr!r}")
        ok &= lint_ok

        # Fake the second-reader's verdict file, then stamp the ledger exactly
        # as --post will (T3): this is the one place the round trip stands in
        # for a hook mode that is still a stub in this track.
        if L.get("reader_out"):
            with open(L["reader_out"], "w") as f:
                f.write("VERDICT: CLEAN\nOBLIGATION: delivered\nCLOCK: intact\nMENU: 3 distinct\n")
            okp, parsed, err = parse_verdict(open(L["reader_out"]).read())
            L["reader"] = "clean" if (okp and parsed["clean"]) else "findings"
            L["reader_findings"] = parsed.get("n", 0) if okp else None
            L["reader_flags"] = parsed.get("flags", {}) if okp else {}
            with open(ledger_file, "w") as f:
                json.dump(L, f, indent=2)

        r = _run_beat(env, "append")
        landed = open(cf).read()
        appended_ok = "The corridor smells of rain" in landed and "### Beat 1" in landed
        print(f"SELFTEST round-trip append lands draft in chapter file -> {'PASS' if appended_ok else 'FAIL'}")
        if not appended_ok:
            print(f"   stdout: {r.stdout!r}\n   stderr: {r.stderr!r}")
        ok &= appended_ok
        recap_still_present = RECAP_HEADING in landed
        print(f"SELFTEST round-trip append preserves trailing scaffold -> {'PASS' if recap_still_present else 'FAIL'}")
        ok &= recap_still_present

        r = _run_beat(env, "close")
        L = _L()
        closed_ok = L.get("closed") is True
        print(f"SELFTEST round-trip close marks ledger closed -> {'PASS' if closed_ok else 'FAIL'}")
        if not closed_ok:
            print(f"   stdout: {r.stdout!r}\n   stderr: {r.stderr!r}")
        ok &= closed_ok
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp_root, ignore_errors=True)
    return ok


def _selftest_repo_root():
    """The kit's own root, independent of what the checkout directory is named.
    Used to be a name-based walk up to a directory literally called
    'story-loop' — which crashed (FileNotFoundError on `<root>/_template`)
    the moment this repo is cloned or deployed under any other name, e.g. the
    README's own `git clone ... ~/my-story`, or this vault's own
    `Adventure Games`. `_HOOKS_DIR` is always `<root>/.claude/hooks`, so two
    `dirname()` calls get there with no assumption about names at all."""
    return os.path.dirname(os.path.dirname(_HOOKS_DIR))


def _run_hook(env, mode, stdin_payload, timeout=30):
    """Invoke THIS beat.py's hook mode as a fresh subprocess, feeding the
    payload on stdin exactly as the harness would. A fresh process is
    required: --guard/--post/--meter all call sys.exit() internally, and each
    needs its own CLAUDE_PROJECT_DIR (see _run_beat)."""
    return subprocess.run(
        [sys.executable, os.path.join(_HOOKS_DIR, "beat.py"), mode],
        input=json.dumps(stdin_payload), env=env, capture_output=True, text=True, timeout=timeout,
    )


def _assert(cond, label):
    print(f"SELFTEST hooks: {label} -> {'PASS' if cond else 'FAIL'}")
    return bool(cond)


def _last_json(stdout):
    """Parse hook stdout exactly as the real harness does: the WHOLE stdout
    must be one JSON value, or there is no decision. This used to scan the
    output in reverse for the last line that happened to parse as JSON, which
    is strictly MORE forgiving than the harness's own `JSON.parse(stdout)` — a
    stray '!! BEAT.PY WARNING:' line ahead of the real JSON (see warn()'s
    _STDOUT_IS_JSON contract) would still parse here even though it silently
    drops the decision for real. Never relax this back to a per-line scan."""
    try:
        return json.loads(stdout.strip())
    except Exception:
        return {}


def _assert_deny(r, label, must_contain=None):
    j = _last_json(r.stdout)
    hso = j.get("hookSpecificOutput", {})
    reason = hso.get("permissionDecisionReason", "")
    cond = (r.returncode == 0 and hso.get("permissionDecision") == "deny"
            and (must_contain is None or must_contain in reason))
    if not cond:
        label += f" (rc={r.returncode} out={r.stdout!r} err={r.stderr!r})"
    return _assert(cond, label)


def _assert_block(r, label, must_contain=None):
    j = _last_json(r.stdout)
    reason = j.get("reason", "")
    cond = (r.returncode == 0 and j.get("decision") == "block"
            and (must_contain is None or must_contain in reason))
    if not cond:
        label += f" (rc={r.returncode} out={r.stdout!r} err={r.stderr!r})"
    return _assert(cond, label)


def _assert_silent(r, label):
    cond = r.returncode == 0 and not r.stdout.strip()
    if not cond:
        label += f" (rc={r.returncode} out={r.stdout!r} err={r.stderr!r})"
    return _assert(cond, label)


# --------------------------------------------------------------------------
# 9.3 — canned hook payloads against a scaffolded TEMP story under /tmp. Never
# the vault. Every row of the annex's §9.3 table, plus the plan's two extra
# --meter cases (menu-signature delta).
# --------------------------------------------------------------------------
def _selftest_hooks(real_root):
    ok = True
    tmp_root, story_path, story = _scaffold_tmp_story(real_root)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = tmp_root
    cf = os.path.join(story_path, "chapters", "chapter_1.md")
    ledger_file = os.path.join(story_path, "scratchpad", LEDGER_NAME)

    def _L():
        return json.load(open(ledger_file))

    try:
        # --- setup: a chapter with a plan, one beat carried lint-clean and
        # reader-clean through the whole chain (mirrors _selftest_round_trip).
        _run_beat(env, "open-chapter", "--n", "1", "--title", "Opening", "--budget", "4",
                  "--clock", "By midnight, or the gate closes for good.",
                  "--turns", "the door opens; something changes")
        ok &= _assert(os.path.isfile(cf), "setup: open-chapter wrote chapter_1.md")

        _run_beat(env, "open", "--type", "scene", "--input", "look around")
        L = _L()
        draft_path = L["draft"]
        draft_text = (
            '<!-- beat: type=scene obligation="the door opens" onstage= -->\n'
            "The corridor smelled of rain and old paper. Something ahead did not want to be "
            "found, and the silence past the threshold had a shape to it, almost a weight. He "
            "went in anyway, one hand trailing the wall.\n\n"
            "**Choices offered:**\n1. Push forward.\n2. Call out.\n3. Turn back.\n"
        )
        open(draft_path, "w").write(draft_text)
        _run_beat(env, "reader-brief")
        L = _L()
        ok &= _assert(L.get("lint") == "ok", "setup: reader-brief lints clean")
        if L.get("reader_out"):
            open(L["reader_out"], "w").write(
                "VERDICT: CLEAN\nOBLIGATION: delivered\nCLOCK: intact\nMENU: 3 distinct\n")
            okp, parsed, _err = parse_verdict(open(L["reader_out"]).read())
            L["reader"] = "clean" if (okp and parsed["clean"]) else "findings"
            L["reader_findings"] = parsed.get("n", 0) if okp else None
            L["reader_flags"] = parsed.get("flags", {}) if okp else {}
        L["draft_sha"] = sha_norm(draft_text)
        json.dump(L, open(ledger_file, "w"), indent=2)
        clean_ledger = dict(L)

        chapter_write_ti = {"file_path": cf, "content": draft_text}

        # ------------------------------------------------------------------
        # --guard
        # ------------------------------------------------------------------
        os.remove(ledger_file)
        r = _run_hook(env, "--guard", {"tool_name": "Write", "tool_input": chapter_write_ti})
        ok &= _assert_deny(r, "guard: Write to chapter file, no ledger -> deny")

        L2 = dict(clean_ledger)
        L2["reader"] = None
        L2["reader_waived"] = False
        json.dump(L2, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--guard", {"tool_name": "Write", "tool_input": chapter_write_ti})
        ok &= _assert_deny(r, "guard: lint ok, reader null -> deny naming second-reader",
                            must_contain="second-reader")

        # B9 regression, F7-revised: `L["reader"]` truthy ("findings") used to
        # be enough for the guard AND the meter's no-reader check to pass,
        # even when the verdict auto-promoted (any non-intact/delivered/
        # distinct flag forces a revision even on a literal VERDICT: CLEAN —
        # annex §2.3). Simulate exactly that: a chain otherwise complete, but
        # the reader's own flags say the clock widened and reader=="findings"
        # (as --post would actually stamp it — parse_verdict folds
        # auto-promotion into parsed["clean"]), with revisions still below
        # the limit (0 < MAX_REVISIONS). This must still DENY, naming the
        # cycle count — F7 restores the annex's rejected-list semantics: only
        # the reader's *existence* is enforced, not a clean verdict, so the
        # gate exists to drive revision cycles, not to block forever.
        L2b = dict(clean_ledger)
        L2b["reader"] = "findings"
        L2b["reader_flags"] = {"obligation": "delivered", "clock": "widened — she gave him "
                                "until Sunday", "menu": "3 distinct"}
        L2b["revisions"] = 0
        json.dump(L2b, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--guard", {"tool_name": "Write", "tool_input": chapter_write_ti})
        ok &= _assert_deny(
            r, "guard: reader='findings' (auto-promoted, CLOCK widened), revisions=0 -> deny "
               "naming cycle 1 of 2, NOT a truthy-only pass (B9)",
            must_contain="cycle 1 of 2"
        )

        # F7: once MAX_REVISIONS is reached, the SAME findings verdict must
        # no longer block — rule 5 says ship the best draft, and a hard gate
        # here is exactly the deadlock `beat.py revise-brief` refuses to
        # cause once it has told the GM to ship.
        L2c = dict(clean_ledger)
        L2c["reader"] = "findings"
        L2c["reader_flags"] = L2b["reader_flags"]
        L2c["revisions"] = MAX_REVISIONS
        json.dump(L2c, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--guard", {"tool_name": "Write", "tool_input": chapter_write_ti})
        ok &= _assert_silent(
            r, "guard: reader='findings', revisions==MAX_REVISIONS -> silent pass (F7 — ship "
               "the best draft, do not deadlock)"
        )

        json.dump(clean_ledger, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--guard", {"tool_name": "Write", "tool_input": chapter_write_ti})
        ok &= _assert_silent(r, "guard: full ledger, content = the draft -> silent pass")

        retyped_ti = {"file_path": cf, "content": (
            "Something else entirely, retyped by hand instead of read from the cleared draft "
            "file — long enough to clear the guard's 200-char verbatim-check floor and short "
            "enough to obviously not be the corridor scene the reader actually cleared."
        )}
        r = _run_hook(env, "--guard", {"tool_name": "Write", "tool_input": retyped_ti})
        ok &= _assert_deny(r, "guard: full ledger, retyped content -> deny sha mismatch",
                            must_contain="sha mismatch")

        os.remove(ledger_file)
        bash_append_ti = {"command": f'obsidian vault=x append path="{story}/chapters/chapter_4.md" content=hi'}
        r = _run_hook(env, "--guard", {"tool_name": "Bash", "tool_input": bash_append_ti})
        ok &= _assert_deny(r, "guard: Bash obsidian-append chapter_4.md, empty ledger -> deny")

        # A9/B5 regression: `targets_chapter`'s Bash verb alternation used to
        # require append|create|modify|>>|write — `tee -a` and `sed -i` matched
        # NEITHER, so a chapter write through either one sailed past the guard
        # silently allowed, empty ledger and all. Both must now be caught.
        tee_write_ti = {"command": f'tee -a "{cf}" <<< "should not land via tee"'}
        r = _run_hook(env, "--guard", {"tool_name": "Bash", "tool_input": tee_write_ti})
        ok &= _assert_deny(r, "guard: Bash 'tee -a' onto the chapter file, empty ledger -> "
                              "deny (A9/B5 — used to be silently allowed)")

        sed_write_ti = {"command": f"sed -i '$a extra line' \"{cf}\""}
        r = _run_hook(env, "--guard", {"tool_name": "Bash", "tool_input": sed_write_ti})
        ok &= _assert_deny(r, "guard: Bash 'sed -i' on the chapter file, empty ledger -> "
                              "deny (A9/B5 — used to be silently allowed)")

        # A9/B5 regression: the `beat.py append` Bash fast-path used to match
        # `"beat.py" in cmd and " append" in cmd` — two bare substrings
        # anywhere in the command — so an UNRELATED chapter write with those
        # two words trailing in a comment (or after a `;`) bypassed the guard
        # entirely. The fast-path must now be anchored to the WHOLE command.
        disguised_ti = {"command": (
            f'cat >> "{cf}" <<\'EOF\'\nsomething retyped by hand, not read from the draft\nEOF\n'
            f"# then: python3 .claude/hooks/beat.py append"
        )}
        r = _run_hook(env, "--guard", {"tool_name": "Bash", "tool_input": disguised_ti})
        ok &= _assert_deny(r, "guard: chapter write with 'beat.py append' trailing as a "
                              "comment -> still evaluated and denied, NOT fast-pathed (A9/B5)")

        # The real, legitimate invocation — anchored but still allowed.
        real_append_ti = {"command": "python3 .claude/hooks/beat.py append --label 'ch1 b1'"}
        r = _run_hook(env, "--guard", {"tool_name": "Bash", "tool_input": real_append_ti})
        ok &= _assert_silent(r, "guard: the real 'beat.py append' invocation (with args) "
                                 "still fast-paths -> silent pass")

        # B1 regression: a Bash chapter write the hook cannot inline-extract
        # (no heredoc — a `tee -a ... <<<` herestring, which _extract_inline_prose
        # does not parse) ALSO has to fire warn() ("could not extract inline
        # prose"). warn() used to print that line to the SAME stdout the deny
        # JSON is on, corrupting it (`json.loads(stdout)` failing) so the deny
        # was silently dropped by the harness. Assert stdout parses as JSON
        # STRICTLY (the harness's own contract, not _last_json's old forgiving
        # reversed-line scan) with the deny intact, and that the warning landed
        # on stderr instead.
        L3 = dict(clean_ledger)
        L3["reader"] = None
        L3["reader_waived"] = False
        json.dump(L3, open(ledger_file, "w"), indent=2)
        tee_ti = {"command": f'tee -a "{cf}" <<< "should not land via tee"'}
        r = _run_hook(env, "--guard", {"tool_name": "Bash", "tool_input": tee_ti})
        strict_j = {}
        try:
            strict_j = json.loads(r.stdout.strip())
        except Exception:
            strict_j = {}
        ok &= _assert(
            strict_j.get("hookSpecificOutput", {}).get("permissionDecision") == "deny",
            f"guard: Bash tee (unparseable inline prose) + missing reader -> stdout is "
            f"STRICTLY one JSON deny, warn() did not corrupt it (out={r.stdout!r})"
        )
        ok &= _assert("could not extract inline prose" in r.stderr,
                      f"guard: the inline-extraction warning landed on stderr, not stdout "
                      f"(stderr={r.stderr!r})")
        json.dump(clean_ledger, open(ledger_file, "w"), indent=2)

        t0 = time.time()
        r = _run_hook(env, "--guard", {"tool_name": "Bash", "tool_input": {"command": "ls"}})
        dt_ms = (time.time() - t0) * 1000
        ok &= _assert_silent(r, "guard: Bash 'ls' -> silent pass")
        print(f"SELFTEST hooks: guard bash 'ls' round-trip took {dt_ms:.1f} ms "
              "(subprocess spawn dominates this figure; the in-process bail-out this measures "
              "is targets_chapter() returning False before any ledger/story I/O)")

        # Delta: `beat.py append` itself is never guarded — it verifies its
        # own chain.
        r = _run_hook(env, "--guard", {"tool_name": "Bash",
                      "tool_input": {"command": "python3 .claude/hooks/beat.py append"}})
        ok &= _assert_silent(r, "guard: Bash 'beat.py append' fast-path -> silent pass, no re-check")

        # C1 regression: `targets_chapter`'s Bash branch used to match the
        # chapter-path regex and the write-verb alternation INDEPENDENTLY,
        # anywhere in the command — so a READ-ONLY command that merely
        # mentioned a chapter path (`tail`, `grep`, `cat | wc`, a `sed -n`
        # read, a python `open()` read, `diff ... > /tmp/x`, an obsidian
        # `read`) was denied outright as soon as the SAME command also
        # contained an unrelated `>`/`2>&1`/write-flavoured word anywhere
        # else. Observed live: `tail -c 1500 chapter.md; grep ...; python3
        # prose-lint.py draft.md 2>&1 | head -4` was denied with "no open
        # beat" purely because of the `2>&1`. Run every read-only shape
        # against BOTH an open-but-incomplete ledger (reader not yet run)
        # AND no ledger at all — read-only Bash must never be denied
        # regardless of chain state — and every real write shape must still
        # be denied in both states.
        c1_allow = [
            "tail -c 1500 {cf}",
            "grep -n T1 {cf} 2>&1 | head",
            "cat {cf} | wc -c",
            "sed -n '1,20p' {cf}",
            "python3 -c \"print(open('{cf}').read()[:100])\"",
            "diff a.md {cf} > /tmp/x.diff",
            "obsidian vault=V read path={cf}",
        ]
        c1_deny = [
            "cat >> {cf} <<EOF\nx\nEOF",
            "printf x > {cf}",
            "echo x | tee -a {cf}",
            "sed -i 's/a/b/' {cf}",
            "python3 -c \"open('{cf}','a').write('x')\"",
            "obsidian vault=V append path={cf} content=x",
            "cp /tmp/x.md {cf}",
        ]
        incomplete_ledger = dict(clean_ledger)
        incomplete_ledger["reader"] = None
        incomplete_ledger["reader_waived"] = False
        for state_label, state_setup in (
            ("open-but-incomplete ledger", lambda: json.dump(incomplete_ledger, open(ledger_file, "w"), indent=2)),
            ("no ledger", lambda: os.remove(ledger_file) if os.path.isfile(ledger_file) else None),
        ):
            state_setup()
            for tmpl in c1_allow:
                cmd = tmpl.format(cf=cf)
                r = _run_hook(env, "--guard", {"tool_name": "Bash", "tool_input": {"command": cmd}})
                ok &= _assert_silent(r, f"C1: guard Bash read-only, {state_label} -> silent pass ({cmd!r})")
            for tmpl in c1_deny:
                cmd = tmpl.format(cf=cf)
                r = _run_hook(env, "--guard", {"tool_name": "Bash", "tool_input": {"command": cmd}})
                ok &= _assert_deny(r, f"C1: guard Bash write, {state_label} -> deny ({cmd!r})")

        json.dump(clean_ledger, open(ledger_file, "w"), indent=2)

        # ------------------------------------------------------------------
        # F1 — session-scoped ledger: .beat_owner round-trip (guard -> open),
        # and --guard's foreign-session chapter-write deny.
        # ------------------------------------------------------------------
        owner_path = os.path.join(story_path, "scratchpad", ".beat_owner")
        if os.path.isfile(owner_path):
            os.remove(owner_path)

        # --guard sees the GM's OWN 'beat.py open' Bash call and captures the
        # session id off it — never denies (this command doesn't target the
        # chapter file at all), just writes .beat_owner silently.
        r = _run_hook(env, "--guard", {
            "tool_name": "Bash",
            "tool_input": {"command": "python3 .claude/hooks/beat.py open --type scene --input hi"},
            "session_id": "sess-A",
        })
        ok &= _assert_silent(r, "F1: guard sees the GM's 'beat.py open' Bash call -> silent pass")
        owner_written = open(owner_path).read().strip() if os.path.isfile(owner_path) else None
        ok &= _assert(owner_written == "sess-A",
                      f"F1: .beat_owner written with the calling session id (got {owner_written!r})")

        # cmd_open reads .beat_owner ONCE into the new ledger's session_id,
        # then deletes it.
        _run_beat(env, "open", "--type", "scene", "--input", "look around")
        L_owned = _L()
        ok &= _assert(
            L_owned.get("session_id") == "sess-A" and not os.path.isfile(owner_path),
            f"F1: cmd_open reads .beat_owner into the ledger and deletes the file "
            f"(session_id={L_owned.get('session_id')!r}, "
            f"owner_path still exists={os.path.isfile(owner_path)})"
        )

        # No .beat_owner at all -> falls back to CLAUDE_SESSION_ID (unset in
        # this test env), so the ledger's session_id is "" — a session-
        # oblivious ledger that --guard/--post/--meter never gate on.
        _run_beat(env, "open", "--type", "scene", "--input", "look again")
        L_unowned = _L()
        ok &= _assert(
            L_unowned.get("session_id") == "",
            f"F1: no .beat_owner present -> ledger session_id falls back to '' "
            f"(got {L_unowned.get('session_id')!r})"
        )

        # --guard: a chapter write from a session that does NOT own the open
        # beat must be denied — even though this beat's own chain (reused
        # from `clean_ledger`) looks otherwise complete.
        owned_ledger = dict(clean_ledger)
        owned_ledger["session_id"] = "sess-A"
        json.dump(owned_ledger, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--guard", {
            "tool_name": "Write", "tool_input": chapter_write_ti, "session_id": "sess-B",
        })
        ok &= _assert_deny(
            r, "F1: guard denies a chapter write from a session that does not own the open beat",
            must_contain="another session owns the open beat"
        )

        r = _run_hook(env, "--guard", {
            "tool_name": "Write", "tool_input": chapter_write_ti, "session_id": "sess-A",
        })
        ok &= _assert_silent(r, "F1: guard allows the OWNING session's chapter write "
                                 "(matching session_id)")

        r = _run_hook(env, "--guard", {
            "tool_name": "Write", "tool_input": chapter_write_ti,
            "session_id": "sess-B", "agent_id": "subagent-1",
        })
        ok &= _assert_silent(r, "F1: guard allows a subagent call (agent_id set) even with a "
                                 "mismatched session_id — its parent is assumed to be the owner")

        ownerless_ledger = dict(clean_ledger)
        ownerless_ledger["session_id"] = ""
        json.dump(ownerless_ledger, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--guard", {
            "tool_name": "Write", "tool_input": chapter_write_ti, "session_id": "sess-B",
        })
        ok &= _assert_silent(r, "F1: guard applies no session gate when the ledger tracks no "
                                 "owner (session_id=='') — backward compatible")

        json.dump(clean_ledger, open(ledger_file, "w"), indent=2)

        # ------------------------------------------------------------------
        # --post
        # ------------------------------------------------------------------
        # Reuse ch3b3_good.md (real, Tier-A-clean prose, already 2,637 chars —
        # over the 2,400 scene ceiling on its own) plus prose-lint's own
        # _FILLER paragraph (T1's calibrated ceiling-only regression text,
        # deliberately free of every other Tier-A/B trigger). A repeated
        # sentence would instead trip repeat-in-beat and bury the
        # size-ceiling line under MAX_REPORT_LINES.
        good_fixture = os.path.join(_HOOKS_DIR, "fixtures", "ch3b3_good.md")
        filler = getattr(pl, "_FILLER", "") if pl else ""
        big_text = open(good_fixture).read().rstrip("\n") + "\n\n" + filler + \
            "\n\n**Choices offered:**\n1. a\n2. b\n"
        open(draft_path, "w").write(big_text)
        r = _run_hook(env, "--post", {"tool_input": {"file_path": draft_path}})
        ok &= _assert(r.returncode == 2 and "size-ceiling" in r.stderr and "cut" in r.stderr,
                      f"post: oversized scene draft -> exit2 size-ceiling/'cut' "
                      f"(rc={r.returncode}, stderr={r.stderr[:160]!r})")
        open(draft_path, "w").write(draft_text)

        bridge_draft = os.path.join(os.path.dirname(draft_path), "ch1_beat2_draft.md")
        bridge_text = (
            '<!-- beat: type=bridge obligation="a quiet morning passes" onstage= -->\n'
            "Morning came and went in a handful of unremarkable minutes, and nothing in it "
            "changed anything that mattered. By the time the second bell rang the corridor had "
            "already filled and emptied once, and he was at his desk before it faded.\n\n"
            "**Choices offered:**\n1. Go to breakfast.\n2. Go straight to the library.\n"
        )
        open(bridge_draft, "w").write(bridge_text)
        r = _run_hook(env, "--post", {"tool_input": {"file_path": bridge_draft}})
        ok &= _assert(r.returncode == 0 and "LINT OK" in r.stdout and "Chain" in r.stdout,
                      f"post: 620ish-char bridge draft -> exit0 LINT OK + Chain line "
                      f"(rc={r.returncode}, out={r.stdout[:200]!r})")

        bad_reader = os.path.join(os.path.dirname(draft_path), "ch1_beat1_reader.md")
        open(bad_reader, "w").write("OBLIGATION: delivered\nCLOCK: intact\nMENU: 3 distinct\n")
        r = _run_hook(env, "--post", {"tool_input": {"file_path": bad_reader}})
        ok &= _assert(r.returncode == 2, f"post: reader file with no VERDICT: line -> exit2 "
                      f"(rc={r.returncode})")

        r = _run_hook(env, "--post", {"tool_input": {"file_path": os.path.join(story_path, "STORY_BIBLE.md")}})
        ok &= _assert_silent(r, "post: unrelated file path -> silent pass")

        # B3 regression: a `*_draft.md` file that is NOT this ledger's own
        # tracked draft (any path ending `_draft.md` used to be enough to
        # unconditionally overwrite L["draft"]/["draft_sha"]/["lint"] — a
        # foreign or throwaway file could hijack the open beat's chain of
        # custody, and `beat.py append` would go on to land THAT file in the
        # chapter log). Confirm the ledger is untouched by a foreign draft.
        before = json.load(open(ledger_file))
        foreign_draft = os.path.join(tmp_root, "outside_scratchpad_beat1_draft.md")
        open(foreign_draft, "w").write(bridge_text)
        r = _run_hook(env, "--post", {"tool_input": {"file_path": foreign_draft}})
        after = json.load(open(ledger_file))
        ok &= _assert(
            r.returncode == 0 and after.get("draft") == before.get("draft")
            and after.get("draft_sha") == before.get("draft_sha"),
            f"post: a foreign _draft.md file lints but does NOT repoint the ledger's "
            f"draft/draft_sha (before={before.get('draft')!r}, after={after.get('draft')!r})"
        )
        ok &= _assert("is not the open ledger's tracked draft" in r.stderr,
                      f"post: foreign-draft warning landed on stderr (stderr={r.stderr[:200]!r})")

        # ------------------------------------------------------------------
        # F1 — post: stamping is gated by session ownership too. Corrupt
        # the ledger's stamped fields first, so "the ledger was NOT touched"
        # can be asserted precisely (a fresh, idempotent re-stamp of already-
        # correct values would look identical to a skipped stamp otherwise).
        # ------------------------------------------------------------------
        owned_ledger_post = dict(clean_ledger)
        owned_ledger_post["session_id"] = "sess-A"

        corrupted = dict(owned_ledger_post)
        corrupted["lint"] = "stale-marker"
        corrupted["draft_sha"] = "0" * 64
        json.dump(corrupted, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--post", {
            "tool_input": {"file_path": draft_path}, "session_id": "sess-B",
        })
        after_post = json.load(open(ledger_file))
        ok &= _assert(
            r.returncode == 0 and "LINT OK" in r.stdout
            and after_post.get("lint") == "stale-marker" and after_post.get("draft_sha") == "0" * 64,
            f"F1: post from a non-owning session still lints (exit0, LINT OK reported) but "
            f"leaves the ledger's stamped fields untouched (lint={after_post.get('lint')!r})"
        )
        ok &= _assert("does not own it" in r.stderr,
                      f"F1: post from a non-owning session warns on stderr "
                      f"(stderr={r.stderr[:200]!r})")

        json.dump(corrupted, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--post", {
            "tool_input": {"file_path": draft_path}, "session_id": "sess-A",
        })
        after_post2 = json.load(open(ledger_file))
        ok &= _assert(
            r.returncode == 0 and after_post2.get("lint") == "ok"
            and after_post2.get("draft_sha") == sha_norm(draft_text),
            f"F1: post from the OWNING session DOES stamp (corrupted marker restored: "
            f"lint={after_post2.get('lint')!r})"
        )

        json.dump(corrupted, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--post", {
            "tool_input": {"file_path": draft_path},
            "session_id": "sess-B", "agent_id": "subagent-1",
        })
        after_post3 = json.load(open(ledger_file))
        ok &= _assert(
            r.returncode == 0 and after_post3.get("lint") == "ok"
            and after_post3.get("draft_sha") == sha_norm(draft_text),
            f"F1: post with agent_id set stamps even with a mismatched session_id (a "
            f"subagent's parent is assumed to be the owner) — marker restored "
            f"(lint={after_post3.get('lint')!r})"
        )

        # Same session gate, reader-verdict branch.
        reader_out_path = clean_ledger.get("reader_out")
        good_verdict = "VERDICT: CLEAN\nOBLIGATION: delivered\nCLOCK: intact\nMENU: 3 distinct\n"
        open(reader_out_path, "w").write(good_verdict)

        corrupted_reader = dict(owned_ledger_post)
        corrupted_reader["reader"] = "stale-marker"
        json.dump(corrupted_reader, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--post", {
            "tool_input": {"file_path": reader_out_path}, "session_id": "sess-B",
        })
        after_r = json.load(open(ledger_file))
        ok &= _assert(
            r.returncode == 0 and after_r.get("reader") == "stale-marker",
            f"F1: post (reader file) from a non-owning session parses but does NOT stamp "
            f"(reader={after_r.get('reader')!r})"
        )

        json.dump(corrupted_reader, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--post", {
            "tool_input": {"file_path": reader_out_path}, "session_id": "sess-A",
        })
        after_r2 = json.load(open(ledger_file))
        ok &= _assert(
            r.returncode == 0 and after_r2.get("reader") == "clean",
            f"F1: post (reader file) from the OWNING session DOES stamp "
            f"(reader={after_r2.get('reader')!r})"
        )

        json.dump(clean_ledger, open(ledger_file, "w"), indent=2)

        # ------------------------------------------------------------------
        # --meter
        # ------------------------------------------------------------------
        # F5: `stop_hook_active` no longer short-circuits before the eight
        # checks run — at THIS point in the test, ledger_file == clean_ledger
        # (chain fields complete, but never actually appended/resume-
        # rewritten in this story tree), so `not-saved` fails and a retry
        # must never emit `decision:block` for it — at most an advisory. The
        # full "retry passes cleanly" / "retry still fails" pair is covered
        # below, after `_prep_complete_beat` gives a genuinely complete chain
        # to retry against.
        r = _run_hook(env, "--meter", {"stop_hook_active": True,
                      "last_assistant_message": "x" * 2000})
        j0 = _last_json(r.stdout)
        ok &= _assert(
            r.returncode == 0 and j0.get("decision") != "block",
            f"F5: meter stop_hook_active:true (retry) with a failing chain -> never blocks "
            f"(rc={r.returncode}, out={r.stdout!r})"
        )

        if os.path.isfile(ledger_file):
            os.remove(ledger_file)
        # Multiple paragraphs, like real prose. Real beats are several
        # paragraphs; this fixture matches that shape.
        _para = ("Sable set the notebook down and did not open it again. The room went on "
                 "without her, one ordinary sound at a time, and none of it asked to be noticed.")
        no_menu_prose = "\n\n".join([_para] * 10)
        ok &= _assert(len(no_menu_prose) > 1400, "harness: no_menu_prose is >1400 chars")
        r = _run_hook(env, "--meter", {"last_assistant_message": no_menu_prose})
        ok &= _assert_silent(r, "meter: no ledger + 1,400 chars, NO menu signature -> silent (plan delta)")

        with_menu_prose = no_menu_prose + "\n\n**Choices offered:**\n1. a\n2. b\n"
        r = _run_hook(env, "--meter", {"last_assistant_message": with_menu_prose})
        ok &= _assert_block(r, "meter: no ledger + 1,400 chars + menu signature -> block (anti-bypass)")

        r = _run_hook(env, "--meter", {"last_assistant_message": "Sure — you're at chapter 1, beat 2."})
        ok &= _assert_silent(r, "meter: no ledger + a 200-char answer -> silent")

        # B4 regression: three realistic non-beat replies, each long enough
        # (>900 chars, >=4 sentences) to have tripped the OLD listy-ratio veto
        # in either direction, each ending in (or containing) a 2-4 item
        # numbered list the way a real design write-up, recap, or status
        # report often does — but each also carries OTHER structural markup
        # (a heading, bullets, a table) that a hand-typed beat bypassing the
        # loop never has. None of these may ever block.
        design_explanation = (
            "## Why the ledger needs a chain field\n\n"
            "Right now the guard infers completeness from three separate booleans, and every "
            "time one of them drifts out of sync with the others a beat gets stuck in a state "
            "no single check explains. A single `chain` enum collapses that surface: it can "
            "only ever be in one of a handful of named states, and the guard reads exactly one "
            "field instead of reconstructing the story from three. That also makes the Stop "
            "meter's own decision tree easier to reason about, since it stops needing to "
            "special-case the same drift on its own side of the fence.\n\n"
            "It also closes a real gap: right now two of those three booleans can independently "
            "regress without the third noticing, which is exactly how a stale ledger ends up "
            "looking complete when it is not. A single enum can only ever be wrong in one place "
            "at a time, and every reader of the ledger — the guard, the meter, and a human "
            "running `beat.py status` — agrees on what each state means without re-deriving it "
            "from the other fields first.\n\n"
            "Three follow-on changes fall out of this:\n\n"
            "1. Collapse `draft_sha`/`lint`/`reader` into a single `chain` field.\n"
            "2. Update the guard's `missing` list to read off that one field.\n"
            "3. Update the meter's checks to do the same.\n"
        )
        ok &= _assert(len(design_explanation) > 900, "harness: design_explanation is >900 chars")
        r = _run_hook(env, "--meter", {"last_assistant_message": design_explanation})
        ok &= _assert_silent(r, "meter: design explanation (# heading + numbered list) -> "
                                 "NOT blocked (must-not-block, B4)")

        chapter_recap = (
            "Here's where things stand at the end of Chapter 3, before we open Chapter 4:\n\n"
            "- Kessler still doesn't know the register was altered, only that the numbers "
            "don't add up.\n"
            "- Pru has the second ledger, and has not decided whether to hand it over.\n"
            "- The department's Saturday deadline is still live and nobody on the page knows "
            "it yet except the reader.\n"
            "- The corridor door has not been opened again since the first night, and nothing "
            "in the text has explained why.\n\n"
            "None of these four threads has actually converged yet, which is worth naming "
            "plainly before Chapter 4 opens: Kessler and Pru have not been in the same room "
            "since the first chapter, the corridor has been mentioned but never revisited, and "
            "the deadline has only ever been felt by the reader, never by either of them on the "
            "page. That gap is the whole reason Chapter 4 exists.\n\n"
            "Three ways Chapter 4 could open, structurally:\n\n"
            "1. Kessler confronts Pru directly, forcing the ledger into the open early.\n"
            "2. The registrar's own deadline forces a decision before either of them is ready.\n"
            "3. A third party (the corridor, or whoever left it unlocked) forces the pace "
            "instead of either of them.\n"
        )
        ok &= _assert(len(chapter_recap) > 900, "harness: chapter_recap is >900 chars")
        r = _run_hook(env, "--meter", {"last_assistant_message": chapter_recap})
        ok &= _assert_silent(r, "meter: chapter recap (- bullets + numbered list) -> "
                                 "NOT blocked (must-not-block, B4)")

        status_report = (
            "Status of the four build tracks, as of the last sync:\n\n"
            "| Track | Owner | State |\n"
            "|---|---|---|\n"
            "| T1 linter surgery | Sonnet | done |\n"
            "| T2 beat.py core | Sonnet | done |\n"
            "| T3 hook modes | Sonnet | in review |\n"
            "| T4 agents/docs | Sonnet | in review |\n\n"
            "Nothing here is blocked on anything else finishing first; T3 and T4 were only "
            "ever run in parallel because they touch disjoint files, not because either "
            "depends on the other's output. The remaining risk is entirely in T5's own "
            "integration pass, which has not started yet, and which cannot really start until "
            "both of the tracks above report clean — there is no partial-credit version of an "
            "integration pass that only checks half the surface area.\n\n"
            "Three things T5 still needs to confirm before this ships:\n\n"
            "1. Every selftest is green in a checkout that is not named 'story-loop'.\n"
            "2. No absolute developer-machine path leaked into any tracked file.\n"
            "3. The gate's byte count still fits the live vault's five-mode register.\n"
        )
        ok &= _assert(len(status_report) > 900, "harness: status_report is >900 chars")
        r = _run_hook(env, "--meter", {"last_assistant_message": status_report})
        ok &= _assert_silent(r, "meter: status report (| table + numbered list) -> "
                                 "NOT blocked (must-not-block, B4)")

        menu_text = "**Choices offered:**\n1. Push forward.\n2. Call out.\n3. Turn back.\n"
        body_text = pl_strip_meta(draft_text)
        full_msg = body_text + "\n\n" + menu_text

        def _prep_complete_beat():
            """A ledger that is OPEN (not yet meter-closed) with every other
            file-truth signal already satisfied: appended to the chapter,
            resume rewritten, plan turn ticked. Mirrors runbook steps 1-9.

            Deliberately uses only PATH-EXPLICIT / VAULT-free operations
            (plain file I/O, parse_plan/render_plan on text already in hand)
            rather than beat.py's own chapter_file()/story_dir()/write_plan()
            helpers — those resolve against the process-global VAULT, which
            was fixed at THIS process's own import time (the real repo, not
            tmp_root, since this whole selftest runs as a bare `python3
            beat.py --selftest --hooks` with no CLAUDE_PROJECT_DIR override).
            _run_beat()/_run_hook() sidestep this by spawning a subprocess
            with `env` (tmp_root) every time; this helper does the equivalent
            by never calling a VAULT-bound function in-process."""
            L3 = dict(clean_ledger)
            L3["closed"] = False
            L3["blocks"] = 0
            json.dump(L3, open(ledger_file, "w"), indent=2)

            chapter_now = open(cf).read()
            if "### Beat 1" not in chapter_now:
                open(cf, "w").write(chapter_now.rstrip("\n") + "\n\n### Beat 1 — Test (" +
                                     today() + ")\n" + draft_text + "\n")
                chapter_now = open(cf).read()

            gs = os.path.join(story_path, "game_state.md")
            gtext = open(gs).read()
            resume_line = f"- **Position:** ch {L3['chapter']} · beat {L3['beat']} · budget 4 · type scene\n"
            gtext = re.sub(r"^- \*\*Position:\*\*.*\n", "", gtext, flags=re.M)
            if re.search(r"^## Resume\s*$", gtext, re.M):
                gtext = re.sub(r"(^## Resume\s*\n)", r"\1" + resume_line, gtext, count=1, flags=re.M)
            else:
                gtext += "\n## Resume\n" + resume_line
            open(gs, "w").write(gtext)

            plan = parse_plan(chapter_now)
            if plan and L3.get("turn_id"):
                for t in plan["turns"]:
                    if t["id"] == L3["turn_id"]:
                        t["status"] = "delivered"
                block = render_plan(plan)
                if block is not None:
                    open(cf, "w").write(PLAN_RE.sub(lambda m: block, chapter_now, count=1))
            return L3

        _prep_complete_beat()
        r = _run_hook(env, "--meter", {"last_assistant_message": full_msg})
        L4 = _L()
        craft_log = open(os.path.join(story_path, "_craft_log.md")).read()
        ok &= _assert(
            r.returncode == 0 and not r.stdout.strip() and L4.get("closed") is True
            and f"ch{clean_ledger['chapter']} b{clean_ledger['beat']}" in craft_log,
            f"meter: complete chain, msg=draft+menu -> silent pass, autolog, closed:true "
            f"(rc={r.returncode}, out={r.stdout!r}, closed={L4.get('closed')})"
        )

        # B9 regression, meter side, F7-revised: an otherwise-complete chain
        # whose reader verdict auto-promoted (reader=="findings", not
        # "clean") must still BLOCK at the meter while revisions are still
        # below the limit — even though `L["reader"]` is truthy — naming the
        # cycle count, not demanding a clean verdict outright.
        L3b = _prep_complete_beat()
        L3b["reader"] = "findings"
        L3b["reader_flags"] = {"obligation": "delivered", "clock": "widened — she gave him "
                                "until Sunday", "menu": "3 distinct"}
        L3b["revisions"] = 0
        json.dump(L3b, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--meter", {"last_assistant_message": full_msg})
        ok &= _assert_block(
            r, "meter: reader='findings' (auto-promoted, CLOCK widened), revisions=0 -> block "
               "naming cycle 1 of 2, NOT a truthy-only pass (B9)",
            must_contain="cycle 1 of 2"
        )

        # F7: at MAX_REVISIONS, the same findings verdict must PASS the meter
        # (rule 5 — ship the best draft, do not deadlock) and autolog must
        # record the shipped-with-findings outcome honestly rather than
        # collapsing it to the same word a mid-revision beat would show.
        L3c = _prep_complete_beat()
        L3c["reader"] = "findings"
        L3c["reader_findings"] = 2
        L3c["reader_flags"] = L3b["reader_flags"]
        L3c["revisions"] = MAX_REVISIONS
        json.dump(L3c, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--meter", {"last_assistant_message": full_msg})
        L4c = _L()
        craft_log_c = open(os.path.join(story_path, "_craft_log.md")).read()
        ok &= _assert(
            r.returncode == 0 and not r.stdout.strip() and L4c.get("closed") is True,
            f"meter: reader='findings', revisions==MAX_REVISIONS -> silent pass, closed:true "
            f"(F7) (rc={r.returncode}, out={r.stdout!r}, closed={L4c.get('closed')})"
        )
        ok &= _assert(
            "finding(s), shipped after 2 revisions" in craft_log_c,
            "meter: autolog for a findings-at-limit ship records "
            "'finding(s), shipped after 2 revisions' honestly (F7)"
        )

        _prep_complete_beat()
        chatty_msg = full_msg + "\n\n" + ("By the way, here is some extra commentary for you. " * 20)
        r = _run_hook(env, "--meter", {"last_assistant_message": chatty_msg})
        ok &= _assert_block(r, "meter: draft+menu+900 chars chatter -> block meta-tax",
                             must_contain="meta-tax")

        _prep_complete_beat()
        heading_msg = "**1 · Opening**\n\n" + full_msg
        r = _run_hook(env, "--meter", {"last_assistant_message": heading_msg})
        ok &= _assert_silent(r, "meter: first line is a whitelisted chapter heading -> pass")

        _prep_complete_beat()
        closer_msg = full_msg + '\n\n*Chapter 1 — "Opening" — ends here.*'
        r = _run_hook(env, "--meter", {"last_assistant_message": closer_msg})
        ok &= _assert_silent(r, "meter: msg ends with a whitelisted close-beat trailer -> pass")

        _prep_complete_beat()
        leak_msg = full_msg + "\n\n(Beat 11 note to self: check this.)"
        r = _run_hook(env, "--meter", {"last_assistant_message": leak_msg})
        ok &= _assert_block(r, "meter: message contains 'Beat 11' -> block meta-leak-chat",
                             must_contain="meta-leak-chat")

        # B7: MAX_BLOCKS counts CONSECUTIVE blocks on the SAME check (here,
        # 'meta-tax' — the check chatty_msg trips). A ledger already at
        # blocks==MAX_BLOCKS with last_block SET TO THAT SAME CHECK means this
        # would be the (MAX_BLOCKS+1)th in a row -> downgrade to advisory.
        L5 = _prep_complete_beat()
        L5["blocks"] = MAX_BLOCKS
        L5["last_block"] = "meta-tax"
        json.dump(L5, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--meter", {"last_assistant_message": chatty_msg})
        j = _last_json(r.stdout)
        ok &= _assert(
            r.returncode == 0 and j.get("decision") != "block"
            and j.get("hookSpecificOutput", {}).get("additionalContext"),
            f"meter: {MAX_BLOCKS + 1} CONSECUTIVE blocks on the same check -> additionalContext, "
            f"not a block (out={r.stdout!r})"
        )

        # B7 regression proper: the bug was that a DIFFERENT check failing
        # right after ANOTHER check had already "used up" the block budget —
        # a beat that fails check A once then check B once used to be
        # downgraded on B (only one of the eight checks ever really enforced
        # per beat). Simulate exactly that: blocks==MAX_BLOCKS from a
        # DIFFERENT prior check ('not-lint-clean') must NOT carry over to
        # 'meta-tax' — this must still be a real, hard block.
        L6 = _prep_complete_beat()
        L6["blocks"] = MAX_BLOCKS
        L6["last_block"] = "not-lint-clean"
        json.dump(L6, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--meter", {"last_assistant_message": chatty_msg})
        ok &= _assert_block(
            r, "meter: blocks==MAX_BLOCKS from a DIFFERENT prior check -> still a real block "
               "on THIS check, not carried over (B7)",
            must_contain="meta-tax"
        )
        L6b = _L()
        ok &= _assert(L6b.get("blocks") == 1 and L6b.get("last_block") == "meta-tax",
                      f"meter: a different failing check resets the consecutive-block streak "
                      f"to 1 (blocks={L6b.get('blocks')}, last_block={L6b.get('last_block')!r})")

        # ------------------------------------------------------------------
        # F1 — meter session scoping: a ledger owned by a DIFFERENT session
        # is never judged (no block, no advisory, ledger untouched); the
        # owning session, or a ledger tracking no owner, is unaffected.
        # ------------------------------------------------------------------
        L7 = _prep_complete_beat()
        L7["session_id"] = "sess-A"
        json.dump(L7, open(ledger_file, "w"), indent=2)
        before_meter = json.load(open(ledger_file))
        r = _run_hook(env, "--meter", {"last_assistant_message": "x" * 2000, "session_id": "sess-B"})
        after_meter = json.load(open(ledger_file))
        ok &= _assert(
            r.returncode == 0 and not r.stdout.strip() and after_meter == before_meter,
            f"F1: meter skips a ledger owned by a different session entirely — silent, "
            f"ledger untouched (rc={r.returncode}, out={r.stdout!r}, "
            f"ledger changed={after_meter != before_meter})"
        )
        ok &= _assert("owned by session sess-A" in r.stderr,
                      f"F1: meter's foreign-session skip is noted on stderr "
                      f"(stderr={r.stderr[:200]!r})")

        json.dump(L7, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--meter", {"last_assistant_message": "x" * 2000, "session_id": "sess-A"})
        ok &= _assert_block(
            r, "F1: meter still enforces normally for the OWNING session (matching "
               "session_id) — the chain is genuinely incomplete for this message",
            must_contain="does not contain the draft"
        )

        L8 = _prep_complete_beat()
        L8["session_id"] = ""
        json.dump(L8, open(ledger_file, "w"), indent=2)
        r = _run_hook(env, "--meter", {"last_assistant_message": "x" * 2000, "session_id": "sess-Z"})
        ok &= _assert_block(
            r, "F1: meter applies no session gate when the ledger tracks no owner "
               "(session_id=='') — backward compatible, still enforces normally",
            must_contain="does not contain the draft"
        )

        # ------------------------------------------------------------------
        # F5 — stop_hook_active retry still runs the 8 checks: a chain that
        # is now complete autologs + closes exactly once; a chain that still
        # fails a check is never (re-)blocked, only (at most) advised, and
        # gets no autolog line.
        # ------------------------------------------------------------------
        craft_log_path = os.path.join(story_path, "_craft_log.md")
        tag = f"ch{clean_ledger['chapter']} b{clean_ledger['beat']} "

        _prep_complete_beat()
        before_count = open(craft_log_path).read().count(tag)
        r = _run_hook(env, "--meter", {"stop_hook_active": True, "last_assistant_message": full_msg})
        after_count = open(craft_log_path).read().count(tag)
        L9 = _L()
        ok &= _assert(
            r.returncode == 0 and not r.stdout.strip() and L9.get("closed") is True
            and after_count == before_count + 1,
            f"F5: stop_hook_active retry, chain now complete -> silent pass, autolog fires "
            f"exactly once, closed:true (rc={r.returncode}, out={r.stdout!r}, "
            f"closed={L9.get('closed')}, log occurrences before={before_count} after={after_count})"
        )

        _prep_complete_beat()
        before_count2 = open(craft_log_path).read().count(tag)
        r = _run_hook(env, "--meter", {"stop_hook_active": True, "last_assistant_message": chatty_msg})
        after_count2 = open(craft_log_path).read().count(tag)
        j2 = _last_json(r.stdout)
        ok &= _assert(
            r.returncode == 0 and j2.get("decision") != "block" and after_count2 == before_count2,
            f"F5: stop_hook_active retry, a check still fails (meta-tax) -> never (re-)blocks "
            f"and gets no autolog line (rc={r.returncode}, out={r.stdout!r}, "
            f"log occurrences before={before_count2} after={after_count2})"
        )

        # ------------------------------------------------------------------
        # malformed stdin, every entry point
        # ------------------------------------------------------------------
        for mode in ("--guard", "--post", "--meter"):
            r = subprocess.run(
                [sys.executable, os.path.join(_HOOKS_DIR, "beat.py"), mode],
                input="not json{{{", env=env, capture_output=True, text=True, timeout=20,
            )
            ok &= _assert(
                r.returncode == 0 and "!! BEAT.PY ERROR:" in r.stdout,
                f"{mode}: malformed stdin -> exit0 + '!! BEAT.PY ERROR:' on stdout "
                f"(rc={r.returncode}, out={r.stdout!r})"
            )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    return ok


# --------------------------------------------------------------------------
# 9.2 item 2/3 — --gate output shape and the no-plan-block form.
# --------------------------------------------------------------------------
def _selftest_gate_chrome_budget(real_root):
    """B8 regression: craft-gate.sh hardcodes its own `used=NNN` chrome
    allowance (header + banners + footer, everything in its stdout besides
    the spine `cat` and beat.py --gate's own output) and passes
    `used + spine_bytes` to `beat.py --gate --used`, which trusts that number
    completely — beat.py has no way to see craft-gate.sh's own bytes. If the
    hardcoded allowance ever under-counts the real chrome (exactly what
    happened here: the header claimed ~440/460 after two cold-start lines
    were added to the END banner, pushing the real figure to ~627), the
    budget check silently passes garbage and a documented-size register can
    overshoot MAX_BYTES with no WARNING at all. This measures the REAL chrome
    (shell script total minus the spine minus beat.py --gate's own output at
    --used 0) and asserts the hardcoded constant is not smaller than it."""
    ok = True
    gate_sh = os.path.join(_HOOKS_DIR, "craft-gate.sh")
    m = re.search(r"^used=(\d+)", open(gate_sh).read(), re.M)
    hardcoded = int(m.group(1)) if m else None
    ok &= _assert(hardcoded is not None, "gate: craft-gate.sh has a bare `used=NNN` line to check")
    if hardcoded is None:
        return ok

    tmp_root, story_path, story = _scaffold_tmp_story(real_root)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = tmp_root
    try:
        _run_beat(env, "open-chapter", "--n", "1", "--title", "Opening", "--budget", "4",
                  "--clock", "By midnight, or the gate closes for good.",
                  "--turns", "the door opens; something changes")
        total = subprocess.run(["sh", gate_sh], env=env, capture_output=True, timeout=20).stdout
        py_out = subprocess.run(
            [sys.executable, os.path.join(_HOOKS_DIR, "beat.py"), "--gate", "--used", "0"],
            env=env, capture_output=True, timeout=20,
        ).stdout
        spine_path = os.path.join(tmp_root, "_craft_research", "CRAFT_SPINE.md")
        spine_bytes = os.path.getsize(spine_path) if os.path.isfile(spine_path) else 0
        real_chrome = len(total) - spine_bytes - len(py_out)
        ok &= _assert(
            hardcoded >= real_chrome,
            f"gate: craft-gate.sh's hardcoded used={hardcoded} covers the REAL measured "
            f"chrome ({real_chrome} B = total {len(total)} - spine {spine_bytes} - "
            f"beat.py-gate-output {len(py_out)})"
        )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    return ok


def _selftest_gate_shape(real_root):
    ok = True
    tmp_root, story_path, story = _scaffold_tmp_story(real_root)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = tmp_root
    cf = os.path.join(story_path, "chapters", "chapter_1.md")
    try:
        _run_beat(env, "open-chapter", "--n", "1", "--title", "Opening", "--budget", "4",
                  "--clock", "By midnight, or the gate closes for good.",
                  "--turns", "the door opens; something changes")
        used = 3015
        r = subprocess.run(
            [sys.executable, os.path.join(_HOOKS_DIR, "beat.py"), "--gate", "--used", str(used)],
            env=env, capture_output=True, text=True, timeout=20,
        )
        out = r.stdout
        out_bytes = len(out.encode("utf-8"))
        ok &= _assert(out_bytes <= (MAX_BYTES - used),
                      f"gate: --used {used} output {out_bytes} B <= MAX_BYTES-used ({MAX_BYTES-used})")
        meter_m = re.search(r"=== CHAPTER METER.*?=== END METER ===\n?", out, re.S)
        meter_bytes = len(meter_m.group(0).encode("utf-8")) if meter_m else -1
        ok &= _assert(bool(meter_m) and meter_bytes <= METER_MAX_BYTES,
                      f"gate: meter block {meter_bytes} B <= METER_MAX_BYTES ({METER_MAX_BYTES})")
        contents_ok = bool(meter_m) and all(
            s in meter_m.group(0) for s in (story, "Ch1", "next beat", "budget", "Clock:", "Open:", "Chain:")
        )
        ok &= _assert(contents_ok, "gate: meter contains story/chapter/next-beat/budget/clock/open/Chain")

        text = open(cf).read()
        open(cf, "w").write(PLAN_RE.sub("(plan block removed for this test)", text, count=1))
        r2 = subprocess.run(
            [sys.executable, os.path.join(_HOOKS_DIR, "beat.py"), "--gate", "--used", "630"],
            env=env, capture_output=True, text=True, timeout=20,
        )
        noplan_ok = (r2.returncode == 0 and "no plan block" in r2.stdout and "open-chapter" in r2.stdout)
        ok &= _assert(noplan_ok, "gate: plan block removed -> 'no plan block' meter names open-chapter, exit0")
        digests_ok = "=== ACTIVE REGISTER" in r2.stdout
        ok &= _assert(digests_ok, "gate: digests still emitted with no plan block")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    return ok


# --------------------------------------------------------------------------
# 9.2 item 5 — parse_verdict cases, including auto-promotion.
# --------------------------------------------------------------------------
def _selftest_parse_verdict_cases(fixtures_dir):
    ok = True
    ok_path = os.path.join(fixtures_dir, "reader_verdict_ok.md")
    bad_path = os.path.join(fixtures_dir, "reader_verdict_bad.md")
    if os.path.isfile(ok_path):
        okp, parsed, err = parse_verdict(open(ok_path).read())
        ok &= _assert(okp and parsed.get("clean") is True,
                      f"parse_verdict: reader_verdict_ok.md -> clean ({err})")
    else:
        print("SELFTEST hooks: reader_verdict_ok.md: SKIP (fixture missing)")
    if os.path.isfile(bad_path):
        okp, parsed, err = parse_verdict(open(bad_path).read())
        ok &= _assert((not okp) and "cap is" in err,
                      f"parse_verdict: reader_verdict_bad.md (5 findings) -> exit2, cap named ({err})")
    else:
        print("SELFTEST hooks: reader_verdict_bad.md: SKIP (fixture missing)")

    no_clock = "VERDICT: CLEAN\nOBLIGATION: delivered\nMENU: 3 distinct\n"
    okp, parsed, err = parse_verdict(no_clock)
    ok &= _assert((not okp) and "CLOCK" in err, f"parse_verdict: missing CLOCK: line -> rejected ({err})")

    widened = ("VERDICT: CLEAN\nOBLIGATION: delivered\nCLOCK: widened — she gave him until Sunday\n"
               "MENU: 3 distinct\n")
    okp, parsed, err = parse_verdict(widened)
    ok &= _assert(okp and parsed.get("clean") is False and parsed.get("auto_promoted") is True,
                  "parse_verdict: VERDICT CLEAN + CLOCK widened -> auto-promoted to findings")

    # A3 regressions: tolerance for trailing whitespace, a trailing period, a
    # bold-markdown label, and CRLF line endings — all four used to reject an
    # otherwise-correct verdict with "missing required line(s)" even though
    # the line was right there.
    trailing_space = ("VERDICT: CLEAN\nOBLIGATION: delivered   \nCLOCK: intact\nMENU: 3 distinct\n")
    okp, parsed, err = parse_verdict(trailing_space)
    ok &= _assert(okp and parsed.get("clean") is True,
                  f"parse_verdict: OBLIGATION line has trailing spaces -> still parses ({err})")

    trailing_period = ("VERDICT: CLEAN\nOBLIGATION: delivered.\nCLOCK: intact\nMENU: 3 distinct\n")
    okp, parsed, err = parse_verdict(trailing_period)
    ok &= _assert(okp and parsed.get("clean") is True,
                  f"parse_verdict: OBLIGATION line has a trailing period -> still parses ({err})")

    bold_markers = ("**VERDICT:** CLEAN\n**OBLIGATION:** delivered\n**CLOCK:** intact\n"
                     "**MENU:** 3 distinct\n")
    okp, parsed, err = parse_verdict(bold_markers)
    ok &= _assert(okp and parsed.get("clean") is True,
                  f"parse_verdict: every label bold-markdown-wrapped -> still parses ({err})")

    crlf = "VERDICT: CLEAN\r\nOBLIGATION: delivered\r\nCLOCK: intact\r\nMENU: 3 distinct\r\n"
    okp, parsed, err = parse_verdict(crlf)
    ok &= _assert(okp and parsed.get("clean") is True,
                  f"parse_verdict: CRLF line endings throughout -> still parses ({err})")

    # The brief's own aligned `label: A | label: B | label: C` alternation
    # shape, copied verbatim instead of the agent picking ONE value — this
    # must still be REJECTED (it is genuinely ambiguous), but with a message
    # that says the line is present-but-unparseable and shows the expected
    # shape, not "missing", which sent a reader hunting for a line that was
    # right there.
    aligned_verbatim = (
        "VERDICT: CLEAN\n"
        "OBLIGATION: delivered            | not delivered — <one clause>\n"
        "CLOCK: intact                    | widened — <one clause> | dissolved — <one clause>\n"
        "MENU: 4 distinct                 | none (climax) | repeat — <which options collide>\n"
    )
    okp, parsed, err = parse_verdict(aligned_verbatim)
    ok &= _assert(
        (not okp) and "present but unparseable" in err and "OBLIGATION" in err
        and "missing" not in err,
        f"parse_verdict: the brief's aligned-alternation shape copied verbatim -> rejected as "
        f"'present but unparseable', not 'missing' ({err})"
    )
    return ok


# --------------------------------------------------------------------------
# 9.2 item 9 — menu-echo calibration, live corpus. Read-only against a vault
# named by BEAT_PY_SELFTEST_VAULT (never hardcoded — see _selftest_digest_
# parity's docstring for why). Reported only; asserts nothing beyond "ran".
# --------------------------------------------------------------------------
def _selftest_menu_echo_calibration():
    vault_dir = os.environ.get("BEAT_PY_SELFTEST_VAULT", "")
    if not vault_dir or not os.path.isdir(vault_dir):
        print("SELFTEST hooks: menu-echo calibration: SKIP (set BEAT_PY_SELFTEST_VAULT to run "
              "this report against a live vault)")
        return True
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = vault_dir
    code = (
        "import importlib.util, json, os, re\n"
        f"spec = importlib.util.spec_from_file_location('beat', {json.dumps(os.path.join(_HOOKS_DIR, 'beat.py'))})\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "story = m.resolve_story()\n"
        "rows = []\n"
        "for n in range(1, 5):\n"
        "    cf = m.chapter_file(story, n)\n"
        "    if not os.path.isfile(cf):\n"
        "        continue\n"
        "    text = open(cf).read()\n"
        "    parts = re.split(r'(?m)^(### Beat[^\\n]*)$', text)\n"
        "    blocks = []\n"
        "    for i in range(1, len(parts), 2):\n"
        "        title = parts[i].strip()\n"
        "        body = parts[i + 1]\n"
        "        cut = re.search(r'\\n---\\n', body)\n"
        "        body = body[:cut.start()] if cut else body\n"
        "        blocks.append((f'ch{n} ' + title, m.pl_menu_options(body)))\n"
        "    for i in range(len(blocks) - 1):\n"
        "        a_title, a_opts = blocks[i]\n"
        "        b_title, b_opts = blocks[i + 1]\n"
        "        if not a_opts or not b_opts:\n"
        "            continue\n"
        "        overlaps = 0\n"
        "        for bo in b_opts:\n"
        "            bsig = m.pl._option_signature(bo)\n"
        "            if any(bsig & m.pl._option_signature(ao) for ao in a_opts):\n"
        "                overlaps += 1\n"
        "        rows.append([a_title, b_title, overlaps, len(b_opts)])\n"
        "print(json.dumps(rows))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=20)
    try:
        rows = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        print(f"SELFTEST hooks: menu-echo calibration: FAIL (report crashed: {e}; stderr={r.stderr!r})")
        return False
    print("SELFTEST hooks: menu-echo calibration (advisory-only; standing record, never Tier-A):")
    for a_title, b_title, overlaps, total in rows:
        flag = " <-- Ch4 cardinal-point repeat" if "ch4" in b_title.lower() else ""
        print(f"   {a_title} -> {b_title}: {overlaps}/{total} options share a per-option "
              f"signature with the prior menu{flag}")
    return _assert(True, "menu-echo calibration report printed (reported only, never Tier-A)")


def _selftest_repo_root_name_independence():
    """A1/B2 regression: this exact command (README's pre-flight check, and
    `new-story` SKILL.md's own "Check before the first beat") must not
    silently crash-and-exit-0 the moment the checkout directory is not
    literally named 'story-loop' — e.g. the README's own
    `git clone ... ~/my-story`, or this kit deployed into a vault named
    something else entirely. Copies the real kit into a /tmp dir named
    anything else and drives a real `--selftest` subprocess against it."""
    import tempfile
    import shutil as _shutil
    real_root = _selftest_repo_root()
    tmp_root = tempfile.mkdtemp(prefix="beatpy_name_indep_")
    renamed = os.path.join(tmp_root, "not-story-loop-at-all")
    try:
        _shutil.copytree(os.path.join(real_root, ".claude"), os.path.join(renamed, ".claude"))
        _shutil.copytree(os.path.join(real_root, "_template"), os.path.join(renamed, "_template"))
        os.symlink(os.path.join(real_root, "_craft_research"), os.path.join(renamed, "_craft_research"))
        r = subprocess.run(
            [sys.executable, os.path.join(renamed, ".claude", "hooks", "beat.py"), "--selftest"],
            capture_output=True, text=True, timeout=120,
        )
        crashed = "BEAT.PY ERROR" in r.stdout
        landed = "SELFTEST round-trip append lands draft in chapter file -> PASS" in r.stdout
        ok = r.returncode == 0 and not crashed and landed
        print(f"SELFTEST repo-root resolution is independent of the checkout's directory "
              f"name -> {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"   rc={r.returncode}\n   stdout tail: {r.stdout[-1200:]!r}\n   stderr: {r.stderr[-400:]!r}")
        return ok
    finally:
        _shutil.rmtree(tmp_root, ignore_errors=True)


def selftest(hooks=False):
    ok = True
    fixtures_dir = os.path.join(_HOOKS_DIR, "fixtures")
    if _PL_LOAD_ERROR:
        print(f"!! BEAT.PY ERROR: could not load prose-lint.py: {_PL_LOAD_ERROR}")
        ok = False
    ok &= _selftest_plan_roundtrip(fixtures_dir)
    ok &= _selftest_obligation_selection()
    ok &= _selftest_open_chapter_refuses_empty_clock(None)
    ok &= _selftest_plan_sanitisation()
    ok &= _selftest_vault_write_transport()
    ok &= _selftest_digest_parity()
    ok &= _selftest_round_trip()
    ok &= _selftest_npc_warn()
    ok &= _selftest_characters_on_stage()
    ok &= _selftest_stamp_subcommand()
    ok &= _selftest_close_chapter_blank_outline_row()
    ok &= _selftest_close_not_delivered_and_autolog()
    ok &= _selftest_revision_limit_ships()
    ok &= _selftest_parse_verdict_cases(fixtures_dir)
    if _PL_FALLBACKS_USED:
        print(f"!! BEAT.PY: prose-lint.py interface fallbacks used (T1 not yet complete): "
              f"{sorted(_PL_FALLBACKS_USED)}")
    if hooks:
        real_root = _selftest_repo_root()
        ok &= _selftest_gate_chrome_budget(real_root)
        ok &= _selftest_gate_shape(real_root)
        ok &= _selftest_hooks(real_root)
        ok &= _selftest_menu_echo_calibration()
        ok &= _selftest_repo_root_name_independence()
    return ok


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main():
    argv = sys.argv[1:]

    if "--gate" in argv:
        used = 630  # B8: matches craft-gate.sh's own measured chrome default; kept in
                    # sync so a standalone `beat.py --gate` (no --used) budgets the same
        if "--used" in argv:
            i = argv.index("--used")
            if i + 1 < len(argv):
                try:
                    used = int(argv[i + 1])
                except ValueError:
                    pass
        return cmd_gate(used)
    if "--guard" in argv:
        return cmd_guard()
    if "--post" in argv:
        return cmd_post()
    if "--meter" in argv:
        return cmd_meter()
    if "--selftest" in argv:
        hooks = "--hooks" in argv
        # A selftest must never exit 0 on a crash — that is the ONE other
        # exception (besides --post's FAIL path) to the "every error path
        # exits 0" contract above. Without this, main.py's bottom-level
        # try/except (a broken beat.py must never block PLAY) would also
        # swallow a broken beat.py --selftest and report it green: exactly the
        # false-pass this repo's own pre-flight check (`new-story` step, this
        # file's README) depends on never happening.
        try:
            ok = selftest(hooks=hooks)
        except Exception as e:
            import traceback
            print(f"!! BEAT.PY ERROR: selftest crashed: {type(e).__name__}: {e}")
            traceback.print_exc()
            sys.exit(1)
        sys.exit(0 if ok else 1)

    ap = argparse.ArgumentParser(prog="beat.py")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("open")
    p.add_argument("--type", choices=["bridge", "scene", "setpiece", "close"], default=None)
    p.add_argument("--npc", default="")
    p.add_argument("--obligation", default=None)
    p.add_argument("--input", default="")
    p.add_argument("--route", default=None)
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("reader-brief")
    p.set_defaults(func=cmd_reader_brief)

    p = sub.add_parser("revise-brief")
    p.set_defaults(func=cmd_revise_brief)

    p = sub.add_parser("append")
    p.add_argument("--label", default=None)
    p.set_defaults(func=cmd_append)

    p = sub.add_parser("close")
    p.add_argument("--not-delivered", action="store_true", dest="not_delivered")
    p.set_defaults(func=cmd_close)

    p = sub.add_parser("rescope")
    p.add_argument("--turn", required=True)
    p.add_argument("--latest", required=True, type=int)
    p.add_argument("--why", required=True)
    p.set_defaults(func=cmd_rescope)

    p = sub.add_parser("open-chapter")
    p.add_argument("--n", required=True, type=int)
    p.add_argument("--title", required=True)
    p.add_argument("--budget", required=True, type=int)
    p.add_argument("--clock", required=True)
    p.add_argument("--turns", default=None, help="';'-separated turn texts")
    p.add_argument("--adventure-name", dest="adventure_name", default=None)
    p.set_defaults(func=cmd_open_chapter)

    p = sub.add_parser("close-chapter")
    p.set_defaults(func=cmd_close_chapter)

    p = sub.add_parser("status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("abort")
    p.set_defaults(func=cmd_abort)

    p = sub.add_parser("lint")
    p.add_argument("path")
    p.add_argument("--type", default=None)
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("stamp")
    p.add_argument("path")
    p.set_defaults(func=cmd_stamp)

    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        ap.print_usage(sys.stderr)
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # a broken beat.py must never block play
        print(f"!! BEAT.PY ERROR: {type(e).__name__}: {e}", file=sys.stdout)
        sys.exit(0)
