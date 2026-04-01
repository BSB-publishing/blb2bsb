#!/usr/bin/env bash
#
# fetch_sources.sh — Download all external source data into sources/
#
# Uses conditional downloading (curl -z) so repeated runs only fetch
# files that are newer on the remote. Safe to run at any time.
#
# Data sources and licenses:
#   TAGNT Greek NT        — STEPBible.org, CC-BY 4.0
#   STEPBible Lexicons    — Tyndale House Cambridge, CC-BY 4.0
#   BSB source tables     — bereanbible.com (free licensing)
#   MSB source tables     — majoritybible.com (free licensing)
#   BSB Strong's USJ      — BSB-publishing/bsb2usfm, GitHub release
#
set -euo pipefail

SOURCES_DIR="$(cd "$(dirname "$0")" && pwd)/sources"
mkdir -p "$SOURCES_DIR"

# ── Helpers ───────────────────────────────────────────────────────────────────

# Download a file only if the remote version is newer (or local doesn't exist).
# Usage: fetch_url <url> <local_path>
fetch_url() {
    local url="$1"
    local dest="$2"

    if [ -f "$dest" ]; then
        echo "  Checking for updates: $(basename "$dest")"
        # curl -z: only download if remote is newer than local file
        curl -fSL -z "$dest" -o "$dest.tmp" "$url" 2>/dev/null || true
        if [ -f "$dest.tmp" ]; then
            mv "$dest.tmp" "$dest"
            echo "    Updated."
        else
            echo "    Up to date."
        fi
    else
        echo "  Downloading: $(basename "$dest")"
        curl -fSL -o "$dest" "$url"
        echo "    Done."
    fi
}

# ── 1. TAGNT Greek NT (STEPBible) ────────────────────────────────────────────

echo "=== TAGNT Greek New Testament ==="

TAGNT_BASE="https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/Translators%20Amalgamated%20OT%2BNT"

fetch_url \
    "${TAGNT_BASE}/TAGNT%20Mat-Jhn%20-%20Translators%20Amalgamated%20Greek%20NT%20-%20STEPBible.org%20CC-BY.txt" \
    "$SOURCES_DIR/tagnt_mat_jhn.txt"

fetch_url \
    "${TAGNT_BASE}/TAGNT%20Act-Rev%20-%20Translators%20Amalgamated%20Greek%20NT%20-%20STEPBible.org%20CC-BY.txt" \
    "$SOURCES_DIR/tagnt_act_rev.txt"

# ── 2. BSB / MSB source tables ───────────────────────────────────────────────

echo ""
echo "=== Bible source tables ==="

fetch_url \
    "https://bereanbible.com/bsb_tables.tsv" \
    "$SOURCES_DIR/bsb_source.tsv"

fetch_url \
    "https://majoritybible.com/msb_nt_tables.tsv" \
    "$SOURCES_DIR/msb_source.tsv"

# ── 3. STEPBible Extended Strong's Lexicons (npm package) ────────────────────

echo ""
echo "=== STEPBible Lexicons ==="

LEXICON_GREEK="$SOURCES_DIR/stepbible-tbesg.json"
LEXICON_HEBREW="$SOURCES_DIR/stepbible-tbesh.json"

if [ -f "$LEXICON_GREEK" ] && [ -f "$LEXICON_HEBREW" ]; then
    echo "  Lexicons already present, skipping."
    echo "  (Delete sources/stepbible-tbes*.json to force re-download)"
else
    echo "  Downloading lexicon package via npm..."
    TMPDIR=$(mktemp -d)
    (
        cd "$TMPDIR"
        npm pack @metaxia/scriptures-source-stepbible-lexicon --quiet 2>/dev/null
        tar xzf metaxia-scriptures-source-stepbible-lexicon-*.tgz
        cp package/data/stepbible-tbesg.json "$LEXICON_GREEK"
        cp package/data/stepbible-tbesh.json "$LEXICON_HEBREW"
    )
    rm -rf "$TMPDIR"
    echo "    Done."
fi

# ── 4. BSB Strong's USJ files (GitHub release) ───────────────────────────────

echo ""
echo "=== BSB Strong's USJ files ==="

BSB_USJ_DIR="$SOURCES_DIR/bsb_strongs_full"

if [ -d "$BSB_USJ_DIR" ] && [ "$(ls -1 "$BSB_USJ_DIR"/*.usj 2>/dev/null | wc -l)" -gt 0 ]; then
    echo "  USJ files already present ($(ls -1 "$BSB_USJ_DIR"/*.usj | wc -l) books), skipping."
    echo "  (Delete sources/bsb_strongs_full/ to force re-download)"
else
    echo "  Downloading from BSB-publishing/bsb2usfm latest release..."
    mkdir -p "$BSB_USJ_DIR"
    TMPDIR=$(mktemp -d)
    (
        cd "$TMPDIR"
        # Try gh CLI first, fall back to curl
        if command -v gh &>/dev/null; then
            gh release download --repo BSB-publishing/bsb2usfm --pattern "BSB_full_strongs_usj.zip" --dir .
        else
            # Get latest release download URL via GitHub API
            ZIP_URL=$(curl -fsSL "https://api.github.com/repos/BSB-publishing/bsb2usfm/releases/latest" \
                | grep -o '"browser_download_url":[^,]*BSB_full_strongs_usj.zip[^,]*' \
                | cut -d'"' -f4)
            curl -fSL -o "BSB_full_strongs_usj.zip" "$ZIP_URL"
        fi
        unzip -q -o "BSB_full_strongs_usj.zip" -d extracted
        # The zip may contain files at top level or in a subdirectory
        find extracted -name "*.usj" -exec cp {} "$BSB_USJ_DIR/" \;
    )
    rm -rf "$TMPDIR"
    echo "    Extracted $(ls -1 "$BSB_USJ_DIR"/*.usj | wc -l) books."
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "=== Sources summary ==="
echo "  TAGNT Mat-Jhn:     $(du -h "$SOURCES_DIR/tagnt_mat_jhn.txt" 2>/dev/null | cut -f1 || echo 'MISSING')"
echo "  TAGNT Act-Rev:     $(du -h "$SOURCES_DIR/tagnt_act_rev.txt" 2>/dev/null | cut -f1 || echo 'MISSING')"
echo "  BSB source:        $(du -h "$SOURCES_DIR/bsb_source.tsv" 2>/dev/null | cut -f1 || echo 'MISSING')"
echo "  MSB source:        $(du -h "$SOURCES_DIR/msb_source.tsv" 2>/dev/null | cut -f1 || echo 'MISSING')"
echo "  Greek lexicon:     $(du -h "$SOURCES_DIR/stepbible-tbesg.json" 2>/dev/null | cut -f1 || echo 'MISSING')"
echo "  Hebrew lexicon:    $(du -h "$SOURCES_DIR/stepbible-tbesh.json" 2>/dev/null | cut -f1 || echo 'MISSING')"
echo "  BSB Strong's USJ:  $(ls -1 "$SOURCES_DIR/bsb_strongs_full/"*.usj 2>/dev/null | wc -l | tr -d ' ') books"
echo ""
echo "All sources ready. Run 'make all' to build the pipeline."
