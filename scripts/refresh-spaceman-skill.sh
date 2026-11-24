#!/usr/bin/env bash
# Fetch the latest Spaceman setup skill from anomalyco/spaceman (falling back to
# https://anoma.ly/spaceman/skill.md) into skills/spaceman-setup/SKILL.md.
#
# Updates the file only when content changes; keeps any existing local copy if
# offline. Called by setup.sh before per-agent symlink wiring.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="$REPO_DIR/skills/spaceman-setup"
SKILL_MD="$SKILL_DIR/SKILL.md"
PRIMARY_URL="https://raw.githubusercontent.com/anomalyco/spaceman/HEAD/skills/spaceman-setup/SKILL.md"
FALLBACK_URL="https://anoma.ly/spaceman/skill.md"

if ! command -v curl >/dev/null 2>&1; then
  echo "skip     spaceman-setup skill (curl not on PATH)"
  exit 0
fi

mkdir -p "$SKILL_DIR"
tmp="$(mktemp)"
cleanup() { rm -f "$tmp"; }
trap cleanup EXIT

if ! curl -fsSL --max-time 15 "$PRIMARY_URL" -o "$tmp" 2>/dev/null \
  && ! curl -fsSL --max-time 15 "$FALLBACK_URL" -o "$tmp" 2>/dev/null; then
  echo "warn: could not fetch spaceman-setup skill (keeping existing local copy if present)" >&2
  exit 0
fi

if ! grep -q '^name:[[:space:]]*spaceman-setup$' "$tmp"; then
  echo "warn: fetched spaceman-setup skill failed frontmatter check; ignoring" >&2
  exit 0
fi

if [ -f "$SKILL_MD" ] && cmp -s "$tmp" "$SKILL_MD"; then
  exit 0
fi

mv "$tmp" "$SKILL_MD"
echo "refreshed spaceman-setup skill"
