#!/usr/bin/env python3
"""Align BLB English words to TAGNT Greek words.

Uses multiple strategies in priority order:
1. Explicit additions (<i> tagged) — no Greek match
2. Gloss exact match (position-aware) — BLB word matches TAGNT gloss
3. BSB pattern match (from TSV + USJ) — learn Strong's→English mappings
4. Lexicon gloss match — use STEPBible lexicon glosses
5. Fuzzy gloss match — difflib similarity
6. Multi-word grouping — attach orphaned auxiliaries/prepositions to neighbors

Positional-only matching is deliberately avoided (produces too many wrong matches).

Usage:
    python3 align.py output/tagnt_parsed.json output/blb_parsed.json \\
        cache/bereanbible/source.tsv -o output/aligned.json \\
        --lexicon sources/stepbible-tbesg.json \\
        --usj-dir cache/bereanbible/strongs_full
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher


# ── Data loaders ──────────────────────────────────────────────────────────────

def load_bsb_patterns_tsv(bsb_path):
    """Learn Strong's → English patterns from BSB source TSV."""
    patterns = defaultdict(set)

    with open(bsb_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 19:
                continue
            if fields[4] != "Greek":
                continue

            strongs_raw = fields[11].strip()
            english_raw = fields[18].strip()
            if not strongs_raw or not english_raw:
                continue

            try:
                num = int(strongs_raw)
                strongs = f"G{num:04d}"
            except ValueError:
                continue

            english_clean = re.sub(r'\[.*?\]', '', english_raw).strip()
            if not english_clean or english_clean == "-":
                continue

            patterns[strongs].add(english_clean.lower())
            for w in english_clean.lower().split():
                if len(w) > 1:
                    patterns[strongs].add(w)

    return patterns


def load_bsb_patterns_usj(usj_dir):
    """Learn Strong's → English patterns from BSB USJ files.

    Each USJ file has word-level entries like:
        {"type": "char", "marker": "w", "strong": "G976", "content": ["record"]}
    """
    patterns = defaultdict(set)
    if not usj_dir or not os.path.isdir(usj_dir):
        return patterns

    for fname in sorted(os.listdir(usj_dir)):
        if not fname.endswith(".usj"):
            continue
        filepath = os.path.join(usj_dir, fname)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        _extract_usj_patterns(data.get("content", []), patterns)

    return patterns


def _extract_usj_patterns(content_list, patterns):
    """Recursively extract Strong's→English from USJ content tree."""
    for item in content_list:
        if isinstance(item, str):
            continue
        if not isinstance(item, dict):
            continue

        if item.get("marker") == "w" and "strong" in item:
            raw_strong = item["strong"].strip()
            # Normalize: "G976" → "G0976"
            m = re.match(r'^[GH]?(\d+)', raw_strong)
            if m:
                num = int(m.group(1))
                strongs = f"G{num:04d}"

                # Extract English text from content
                eng_parts = []
                for c in item.get("content", []):
                    if isinstance(c, str):
                        eng_parts.append(c)
                eng_text = " ".join(eng_parts).strip()
                eng_clean = re.sub(r'\[.*?\]', '', eng_text).strip().lower()
                if eng_clean and eng_clean != "-":
                    patterns[strongs].add(eng_clean)
                    for w in eng_clean.split():
                        if len(w) > 1:
                            patterns[strongs].add(w)

        # Recurse into nested content
        if "content" in item:
            _extract_usj_patterns(item["content"], patterns)


def load_lexicon(lexicon_path):
    """Load STEPBible lexicon JSON. Returns dict: strongs → gloss string."""
    if not lexicon_path:
        return {}
    with open(lexicon_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = {}
    for key, entry in data.items():
        gloss = entry.get("gloss", "")
        if gloss:
            result[key] = gloss.lower()
    return result


# ── Text helpers ──────────────────────────────────────────────────────────────

def clean_english(text):
    """Strip brackets, punctuation from TAGNT English gloss."""
    text = re.sub(r'[\[\]<>]', '', text)
    text = re.sub(r'[.,;:!?\'"()]', '', text)
    return text.strip().lower()


def clean_word(word):
    """Lowercase and strip punctuation from a BLB word."""
    return re.sub(r'[.,;:!?\'"()\[\]<>|]', '', word).strip().lower()


def normalize_strongs(s):
    """Normalize Strong's like G2424G → G2424, strip trailing letters."""
    if not s:
        return s
    m = re.match(r'^(G\d+)', s)
    return m.group(1) if m else s


# ── Auxiliary word detection ──────────────────────────────────────────────────

GROUPABLE_WORDS = {
    # Auxiliaries
    "having", "been", "being", "be", "is", "was", "were", "are", "am",
    "will", "shall", "should", "would", "could", "might", "may", "can",
    "do", "does", "did", "has", "have", "had",
    "let", "began",
    # Pronouns (often part of a Greek verb's implicit subject)
    "i", "he", "she", "it", "we", "you", "they",
    "me", "him", "her", "us", "them",
    "my", "his", "its", "our", "your", "their",
    # Prepositions / particles
    "of", "to", "in", "for", "by", "with", "from", "at", "on", "up",
    "out", "into", "upon", "through", "about", "against", "before",
    "after", "over", "under", "between", "among",
    "not", "no", "nor",
    "a", "an", "the",
    # Common verb particles
    "away", "down", "off", "back", "forth", "together",
    "as", "so", "also", "even", "yet", "still", "then",
}


# ── Core alignment ───────────────────────────────────────────────────────────

def align_verse(greek_words, blb_data, bsb_patterns, lexicon):
    """Align a single verse's BLB words to TAGNT Greek words."""
    eng_words = blb_data["words"]
    added_indices = set(blb_data["added_indices"])

    n_greek = len(greek_words)
    n_eng = len(eng_words)

    eng_matched = [False] * n_eng
    greek_matched = [False] * n_greek
    alignments = []

    # Strategy 1: Explicit additions (<i> tagged words)
    for ei in added_indices:
        alignments.append({
            "greek_index": None,
            "english_indices": [ei],
            "strongs": None,
            "confidence": 1.0,
            "method": "explicit_addition",
        })
        eng_matched[ei] = True

    # Build cleaned word lists
    eng_clean = [clean_word(w) for w in eng_words]
    greek_glosses = []
    for gw in greek_words:
        eng_gloss = clean_english(gw.get("english", ""))
        greek_glosses.append(eng_gloss.split())

    # Strategy 2: Gloss exact match (position-aware)
    # Process Greek words in order, using position-weighted candidate selection
    for gi in range(n_greek):
        if greek_matched[gi]:
            continue

        gloss_words = greek_glosses[gi]
        if not gloss_words:
            continue

        strongs = normalize_strongs(greek_words[gi].get("strongs", ""))

        best_match = _find_gloss_match(
            gloss_words, eng_clean, eng_matched, gi, n_greek, n_eng
        )

        if best_match is not None:
            for ei in best_match:
                eng_matched[ei] = True
            greek_matched[gi] = True
            alignments.append({
                "greek_index": gi,
                "english_indices": best_match,
                "strongs": strongs,
                "confidence": 0.95,
                "method": "gloss_exact",
            })

    # Strategy 3: BSB pattern match
    for gi in range(n_greek):
        if greek_matched[gi]:
            continue

        strongs = normalize_strongs(greek_words[gi].get("strongs", ""))
        if not strongs or strongs not in bsb_patterns:
            continue

        bsb_words = bsb_patterns[strongs]
        best_ei = _find_pattern_match(
            bsb_words, eng_clean, eng_matched, gi, n_greek, n_eng
        )

        if best_ei is not None:
            eng_matched[best_ei] = True
            greek_matched[gi] = True
            alignments.append({
                "greek_index": gi,
                "english_indices": [best_ei],
                "strongs": strongs,
                "confidence": 0.85,
                "method": "bsb_pattern",
            })

    # Strategy 4: Lexicon gloss match
    for gi in range(n_greek):
        if greek_matched[gi]:
            continue

        strongs = normalize_strongs(greek_words[gi].get("strongs", ""))
        if not strongs:
            continue

        lex_gloss = lexicon.get(strongs, "")
        if not lex_gloss:
            alt_key = re.sub(r'^G0+', 'G', strongs)
            lex_gloss = lexicon.get(alt_key, "")
        if not lex_gloss:
            continue

        lex_words = set(re.sub(r'[/,;()]', ' ', lex_gloss).lower().split())

        best_ei = _find_pattern_match(
            lex_words, eng_clean, eng_matched, gi, n_greek, n_eng
        )

        if best_ei is not None:
            eng_matched[best_ei] = True
            greek_matched[gi] = True
            alignments.append({
                "greek_index": gi,
                "english_indices": [best_ei],
                "strongs": strongs,
                "confidence": 0.80,
                "method": "lexicon_gloss",
            })

    # Strategy 5: Fuzzy gloss match
    for gi in range(n_greek):
        if greek_matched[gi]:
            continue

        strongs = normalize_strongs(greek_words[gi].get("strongs", ""))
        gloss_str = " ".join(greek_glosses[gi])
        if not gloss_str:
            continue

        best_ei = None
        best_score = 0.0

        for ei in range(n_eng):
            if eng_matched[ei]:
                continue
            score = SequenceMatcher(None, gloss_str, eng_clean[ei]).ratio()
            pos_score = 1.0 - abs(gi / max(n_greek, 1) - ei / max(n_eng, 1))
            combined = score * 0.7 + pos_score * 0.3
            if score > 0.6 and combined > best_score:
                best_score = combined
                best_ei = ei

        if best_ei is not None and best_score > 0.5:
            eng_matched[best_ei] = True
            greek_matched[gi] = True
            alignments.append({
                "greek_index": gi,
                "english_indices": [best_ei],
                "strongs": strongs,
                "confidence": round(min(0.70, best_score), 2),
                "method": "fuzzy_gloss",
            })

    # Strategy 6: Multi-word grouping
    # Attach unmatched auxiliaries/prepositions to their nearest matched neighbor
    _group_auxiliaries(alignments, eng_words, eng_clean, eng_matched,
                       greek_words, greek_matched, n_eng, n_greek)

    # NO positional fallback — it produces too many wrong matches.

    # Remaining unmatched English words
    for ei in range(n_eng):
        if not eng_matched[ei]:
            alignments.append({
                "greek_index": None,
                "english_indices": [ei],
                "strongs": None,
                "confidence": 0.30,
                "method": "unmatched_english",
            })

    # Remaining unmatched Greek words
    for gi in range(n_greek):
        if not greek_matched[gi]:
            strongs = normalize_strongs(greek_words[gi].get("strongs", ""))
            alignments.append({
                "greek_index": gi,
                "english_indices": [],
                "strongs": strongs,
                "confidence": 0.30,
                "method": "unmatched_greek",
            })

    # Sort by first English index, then Greek index
    alignments.sort(key=lambda a: (
        a["english_indices"][0] if a["english_indices"] else 9999,
        a["greek_index"] if a["greek_index"] is not None else 9999,
    ))

    return alignments


def _find_gloss_match(gloss_words, eng_clean, eng_matched, gi, n_greek, n_eng):
    """Find contiguous BLB words matching gloss, preferring positional proximity.

    For high-frequency words (the, and, etc.), strongly weights position.
    """
    n_gloss = len(gloss_words)
    expected_pos = (gi / max(n_greek, 1)) * n_eng

    # Determine if this is a high-frequency word needing strong position weighting
    is_high_freq = n_gloss == 1 and gloss_words[0] in {
        "the", "and", "of", "to", "in", "a", "is", "was", "not", "for",
        "but", "that", "he", "it", "you", "they", "we", "his", "him",
        "who", "which", "this", "with", "from", "be", "have", "has",
        "son", "god", "all", "will", "shall",
    }

    candidates = []

    # Try full contiguous match
    for start in range(n_eng - n_gloss + 1):
        if any(eng_matched[start + j] for j in range(n_gloss)):
            continue

        match = True
        for j in range(n_gloss):
            if eng_clean[start + j] != gloss_words[j]:
                match = False
                break

        if match:
            dist = abs(start - expected_pos)
            candidates.append((dist, list(range(start, start + n_gloss))))

    # For multi-word glosses: try matching any individual gloss word
    if not candidates and n_gloss > 1:
        for ew in gloss_words:
            for ei in range(n_eng):
                if eng_matched[ei]:
                    continue
                if eng_clean[ei] == ew:
                    dist = abs(ei - expected_pos)
                    candidates.append((dist, [ei]))

    if not candidates:
        return None

    if is_high_freq:
        # For high-frequency words, pick the closest positional match
        candidates.sort(key=lambda x: x[0])
    else:
        # For content words, still prefer proximity but allow more slack
        candidates.sort(key=lambda x: x[0])

    return candidates[0][1]


def _find_pattern_match(pattern_words, eng_clean, eng_matched, gi, n_greek, n_eng):
    """Find best unmatched BLB word matching any pattern word, nearest to position."""
    expected_pos = (gi / max(n_greek, 1)) * n_eng
    best_ei = None
    best_dist = float('inf')

    for ei in range(n_eng):
        if eng_matched[ei]:
            continue
        if eng_clean[ei] in pattern_words:
            dist = abs(ei - expected_pos)
            if dist < best_dist:
                best_dist = dist
                best_ei = ei

    return best_ei


def _group_auxiliaries(alignments, eng_words, eng_clean, eng_matched,
                       greek_words, greek_matched, n_eng, n_greek):
    """Attach unmatched auxiliary/preposition words to neighboring aligned words.

    For each unmatched English word that is an auxiliary verb or preposition,
    find the nearest already-aligned neighbor and merge into its english_indices.
    """
    # Build a map of english_index → alignment for already-matched words
    ei_to_align = {}
    for a in alignments:
        if a["greek_index"] is not None:
            for ei in a["english_indices"]:
                ei_to_align[ei] = a

    for ei in range(n_eng):
        if eng_matched[ei]:
            continue

        word = eng_clean[ei]
        if word not in GROUPABLE_WORDS:
            continue

        # Find the nearest matched English word
        best_neighbor = None
        best_dist = float('inf')

        for matched_ei, a in ei_to_align.items():
            dist = abs(ei - matched_ei)
            if dist < best_dist:
                best_dist = dist
                best_neighbor = a

        # Only group if the neighbor is close (within 4 words)
        if best_neighbor is not None and best_dist <= 4:
            best_neighbor["english_indices"].append(ei)
            best_neighbor["english_indices"].sort()
            eng_matched[ei] = True
            if best_neighbor["confidence"] > 0.85:
                best_neighbor["confidence"] = 0.90


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Align BLB to TAGNT")
    parser.add_argument("tagnt", help="Parsed TAGNT JSON")
    parser.add_argument("blb", help="Parsed BLB JSON")
    parser.add_argument("bsb", help="BSB source TSV")
    parser.add_argument("-o", "--output", default="output/aligned.json")
    parser.add_argument("--lexicon", default="sources/stepbible-tbesg.json",
                        help="STEPBible lexicon JSON")
    parser.add_argument("--usj-dir", default="sources/bsb_strongs_full",
                        help="Directory containing BSB USJ files")
    args = parser.parse_args()

    print("Loading TAGNT...", file=sys.stderr)
    with open(args.tagnt, "r", encoding="utf-8") as f:
        tagnt = json.load(f)

    print("Loading BLB...", file=sys.stderr)
    with open(args.blb, "r", encoding="utf-8") as f:
        blb = json.load(f)

    print("Loading BSB patterns (TSV)...", file=sys.stderr)
    bsb_patterns = load_bsb_patterns_tsv(args.bsb)
    print(f"  TSV patterns for {len(bsb_patterns)} Strong's numbers.", file=sys.stderr)

    print("Loading BSB patterns (USJ)...", file=sys.stderr)
    usj_patterns = load_bsb_patterns_usj(args.usj_dir)
    print(f"  USJ patterns for {len(usj_patterns)} Strong's numbers.", file=sys.stderr)

    # Merge USJ patterns into BSB patterns
    for strongs, words in usj_patterns.items():
        bsb_patterns[strongs] |= words
    print(f"  Combined patterns for {len(bsb_patterns)} Strong's numbers.", file=sys.stderr)

    print("Loading lexicon...", file=sys.stderr)
    lexicon = load_lexicon(args.lexicon)
    print(f"  Loaded {len(lexicon)} lexicon entries.", file=sys.stderr)

    result = {}
    stats = defaultdict(int)
    total_eng = 0
    total_matched = 0

    verses = sorted(set(tagnt.keys()) & set(blb.keys()))
    print(f"Aligning {len(verses)} verses...", file=sys.stderr)

    for verse_ref in verses:
        greek_words = tagnt[verse_ref]
        blb_data = blb[verse_ref]

        alignment = align_verse(greek_words, blb_data, bsb_patterns, lexicon)
        result[verse_ref] = alignment

        for a in alignment:
            stats[a["method"]] += 1
            if a["english_indices"]:
                total_matched += len(a["english_indices"])
        total_eng += len(blb_data["words"])

    print(f"\nAlignment Statistics:", file=sys.stderr)
    for method, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {method}: {count}", file=sys.stderr)
    print(f"  Total English words: {total_eng}", file=sys.stderr)
    print(f"  Total matched: {total_matched}", file=sys.stderr)
    if total_eng > 0:
        print(f"  Coverage: {total_matched/total_eng*100:.1f}%", file=sys.stderr)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print(f"\nWritten to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
