#!/bin/sh
# craft-gate.sh — UserPromptSubmit hook: inject the craft spine + the active
# story's standing-register digests every turn.
#
# HARD CONSTRAINT: total stdout must stay well under Claude Code's internal
# hook-output threshold (observed: ~24KB gets persisted to a file with only a
# ~2KB preview reaching the model — which silently disables the gate).
#
# MAX_BYTES below is the single source of truth for this budget — CLAUDE.md and
# the auto-memory point here rather than restating a number. Set to 8200 on
# 2026-07-26: the largest size proven to arrive inline (23.4KB proven truncated;
# the earlier 9400 was never verified against the threshold). Degrade LOUDLY.
#
# Self-check:  sh .claude/hooks/craft-gate.sh | wc -c
# Steady state is ~6.8KB on a 5-mode register, ~7.6KB with the final-act mode
# added — so a sixth standing mode fits without starving anything.

VAULT="${CLAUDE_PROJECT_DIR:-.}"
SPINE="$VAULT/_craft_research/CRAFT_SPINE.md"
CARDS_DIR="$VAULT/_craft_research/cards"
ACTIVE="$VAULT/ACTIVE_GAME.md"
MAX_BYTES=8200
used=460   # chrome allowance: header + banners + footer (measured ~440)

warn() { printf '!! CRAFT GATE WARNING: %s\n' "$1"; }

printf '=== CRAFT GATE — auto-injected every turn; on non-prose turns, ignore ===\n\n'

# --- 1. Spine (always) ---
if [ -s "$SPINE" ]; then
  cat "$SPINE"
  used=$(( used + $(wc -c < "$SPINE") ))
else
  warn "CRAFT_SPINE.md missing/empty — craft floor NOT loaded. Read _craft_research/CRAFT_SPINE.md before any prose this turn."
fi

# --- 2. Active story -> House Register -> per-mode digests ---
story=""
[ -f "$ACTIVE" ] && story=$(sed -n 's/^active_path:[[:space:]]*//p' "$ACTIVE" | head -1 | tr -d '[:space:]')
story=${story%/}

if [ -z "$story" ]; then
  # A blank active_path is the documented state of a fresh clone, not a fault.
  # Warning on it every prompt until the first story exists reads as a broken
  # install, so this branch is informational and names the way forward. A
  # non-empty path that does not resolve IS a fault and still warns below.
  printf -- '-- CRAFT GATE: no active story yet — spine injected, no story digests.\n'
  printf -- '   Say "let'"'"'s start an adventure" to scaffold one (the new-story skill).\n'
elif [ ! -f "$VAULT/$story/master_index.md" ]; then
  warn "active_path names '$story' but $story/master_index.md is missing — no story digests injected. Fix active_path in ACTIVE_GAME.md or restore the story folder."
else
  MI="$VAULT/$story/master_index.md"
  register=$(awk '
    { low = tolower($0) }
    !inreg && low ~ /^## house register/ { inreg = 1; next }
    inreg && low ~ /^## /                { exit }
    inreg && low ~ /as-needed/           { exit }
    inreg                                { print }
  ' "$MI")
  slugs=$(ls "$CARDS_DIR" 2>/dev/null | sed -n 's/\.card\.md$//p' | paste -sd'|' -)
  modes=""
  [ -n "$slugs" ] && [ -n "$register" ] && \
    modes=$(printf '%s\n' "$register" | grep -oE "$slugs" | awk '!seen[$0]++')

  if [ -z "$modes" ]; then
    warn "could not parse a standing register from $story/master_index.md '## House Register' — Read the story's standing cards in _craft_research/cards/ manually this turn."
  else
    printf '\n=== ACTIVE REGISTER (%s) — standing-mode digests ===\n' "$story"
    for m in $modes; do
      card="$CARDS_DIR/$m.card.md"
      if [ ! -f "$card" ]; then
        warn "no card file for standing mode '$m' — expected $card."
        continue
      fi
      digest=$(sed -n '/<!-- digest:start -->/,/<!-- digest:end -->/p' "$card" | sed '1d;$d')
      if [ -z "$digest" ]; then
        warn "no digest block in $m.card.md — Read _craft_research/cards/$m.card.md before prose this turn."
        continue
      fi
      dsize=$(printf '%s\n' "$digest" | wc -c)
      if [ $(( used + dsize )) -gt "$MAX_BYTES" ]; then
        warn "size budget reached — digest '$m' NOT injected; Read _craft_research/cards/$m.card.md before prose this turn."
        continue
      fi
      printf '\n%s\n' "$digest"
      used=$(( used + dsize ))
    done
  fi
fi

printf '\n=== END CRAFT GATE — run every prose beat against the through-lines, the ship tests, and every digest above (already in context; no Read needed). Mode with no digest above: Read its card in _craft_research/cards/. Major set-piece: Read the full _craft_research/reports/ file. Heed any WARNING lines above. ===\n'
exit 0
