#!/bin/sh
# craft-gate.sh — UserPromptSubmit hook: inject the craft spine + the active
# story's chapter meter and standing-register digests every turn.
#
# HARD CONSTRAINT: total stdout must stay under Claude Code's hook-output
# threshold. Measured from the v2.1.257 binary: the threshold is 10,000 CHARS
# (dQn=1e4), not the ~24KB this header used to claim. Above it, stdout is
# persisted to a file and only a 2,000-char preview reaches the model — which
# silently disables the gate. MAX_BYTES is 8200, so the real headroom is
# ~1,800 chars, not ~16KB. Do not raise it on the old reasoning.
#
# MAX_BYTES now lives in .claude/hooks/beat.py and is the single source of
# truth for both this script's budget and the digest assembly it delegates.
#
# Self-check:  sh .claude/hooks/craft-gate.sh | wc -c     # expect ~7,270 for a 5-mode
#                                                           register, no real WARNING line

VAULT="${CLAUDE_PROJECT_DIR:-.}"
SPINE="$VAULT/_craft_research/CRAFT_SPINE.md"
# beat.py is kit machinery shipped alongside this script — not story data — so
# it resolves against craft-gate.sh's OWN directory, never against $VAULT.
# Same reasoning as prose-lint.py's FIXTURES path and beat.py's own importlib
# contract for prose-lint.py ("from its own directory, never from VAULT"):
# getting this wrong would silently break the one command that tests this
# repo's kit against a foreign story tree (CLAUDE_PROJECT_DIR pointed at a
# vault that has not received this repo's beat.py yet). The story DATA beat.py
# reads (ACTIVE_GAME.md, chapters, master_index.md, ...) still resolves via
# $VAULT — that part is exactly right, since beat.py reads CLAUDE_PROJECT_DIR
# itself.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# B8: this used to be 460, measured only against the ORIGINAL header/banner
# text — never re-measured after the two cold-start lines were added to the
# END banner. Real measured chrome (this script's own header + banners +
# footer, everything except the spine `cat` and beat.py --gate's own output)
# is ~627 B; 630 leaves a few bytes of margin. Getting this wrong doesn't
# warn — it silently lets the real total overshoot beat.py's own MAX_BYTES
# budget check, which trusts this number.
used=630   # chrome allowance: header + banners + footer (measured ~627)

warn() { printf '!! CRAFT GATE WARNING: %s\n' "$1"; }

printf '=== CRAFT GATE — auto-injected every turn; on non-prose turns, ignore ===\n\n'

# --- 1. Spine (always) ---
if [ -s "$SPINE" ]; then
  cat "$SPINE"
  used=$(( used + $(wc -c < "$SPINE") ))
else
  warn "CRAFT_SPINE.md missing/empty — craft floor NOT loaded. Read _craft_research/CRAFT_SPINE.md before any prose this turn."
fi

# --- 2. Chapter meter + standing-mode digests. ONE implementation, in beat.py.
# A second parser here is exactly the drift that made craft-gate.sh:57 (/as-needed/,
# case-insensitive) and prose-lint.py:552 (.split("As-needed")) disagree. There is
# deliberately NO fallback path in this script: a Python failure degrades to
# spine + a loud warning, never to silence.
blocks=""
if [ -f "$SCRIPT_DIR/beat.py" ]; then
  blocks=$(python3 "$SCRIPT_DIR/beat.py" --gate --used "$used" 2>/dev/null)
fi
if [ -n "$blocks" ]; then
  printf '\n%s\n' "$blocks"
else
  warn "beat.py --gate produced nothing — chapter budget, clock, open turns and story digests are NOT in context this turn. Read <story>/master_index.md's plan block and its House Register cards in _craft_research/cards/ manually before any prose."
fi

printf '\n=== END CRAFT GATE — run every prose beat against the through-lines, the ship tests, and every digest above (already in context; no Read needed). Mode with no digest above: Read its card in _craft_research/cards/. Major set-piece: Read the full _craft_research/reports/ file. Heed any WARNING lines above.\n'
printf 'Cold start (new session, /clear, compaction): read <story>/game_state.md '"'"'## Resume'"'"'\n'
printf 'and the chapter file'"'"'s plan block before anything else — they are the whole state.\n'
printf 'The chat reply is the beat and the menu. Nothing else goes in it. ===\n'
exit 0
