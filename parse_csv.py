#!/usr/bin/env python3
"""Parse BLB (Berean Literal Bible) CSV into structured JSON.

Reads the BLB CSV file and extracts per-verse data:
raw text, clean text, word tokens, added-word indices, punctuation, quotes.

Usage:
    python3 parse_csv.py example/blb.csv -o output/blb_parsed.json
"""

import argparse
import csv
import json
import re
import sys


def parse_blb_text(raw):
    """Parse BLB verse text into structured word data.

    Handles:
    - <i>...</i> tags marking translator-added words
    - |...| marking direct speech / quotation boundaries
    - Punctuation separation
    """
    if not raw or not raw.strip():
        return None

    raw = raw.strip()

    # Track quote boundaries: | chars mark speech boundaries
    # We'll process them as part of tokenization

    # Step 1: identify added words (in <i> tags) by replacing them with markers
    # Build a list of tokens with metadata
    tokens = []
    added_indices = []

    # Remove outer quotes if present (CSV artifact)
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]

    # Process character by character, tracking <i> state and | quotes
    i = 0
    current_word = ""
    in_italic = False
    text_clean = ""  # text without tags

    # First pass: strip tags and build clean text, marking positions
    segments = []  # (text, is_added)
    while i < len(raw):
        if raw[i:i+3] == "<i>":
            if current_word:
                segments.append((current_word, False))
                current_word = ""
            in_italic = True
            i += 3
            continue
        elif raw[i:i+4] == "</i>":
            if current_word:
                segments.append((current_word, True))
                current_word = ""
            in_italic = False
            i += 4
            continue
        else:
            current_word += raw[i]
            i += 1

    if current_word:
        segments.append((current_word, in_italic))

    # Rejoin segments and tokenize
    full_text = "".join(seg[0] for seg in segments)

    # Build a character-level is_added map
    char_added = []
    for seg_text, seg_added in segments:
        for ch in seg_text:
            char_added.append(seg_added)

    # Tokenize: split on whitespace, then separate punctuation
    words = []
    word_added = []
    word_pre_punct = []   # punctuation/quotes before word
    word_post_punct = []  # punctuation/quotes after word

    # Split into raw whitespace-delimited tokens
    raw_tokens = full_text.split()
    char_pos = 0

    for rt in raw_tokens:
        # Find this token's position in full_text
        idx = full_text.find(rt, char_pos)
        if idx == -1:
            idx = char_pos
        char_pos = idx + len(rt)

        # Check if this token's alphabetic chars are from added segments
        alpha_added = []
        for j, ch in enumerate(rt):
            if ch.isalpha():
                ci = idx + j
                if ci < len(char_added):
                    alpha_added.append(char_added[ci])

        is_added = len(alpha_added) > 0 and all(alpha_added)

        # Separate leading punctuation/quotes
        pre = ""
        while rt and rt[0] in '|"\'(\u201c\u201d\u2018\u2019':
            pre += rt[0]
            rt = rt[1:]

        # Separate trailing punctuation/quotes
        post = ""
        while rt and rt[-1] in '|"\'.,;:!?)\u201c\u201d\u2018\u2019':
            post = rt[-1] + post
            rt = rt[:-1]

        if not rt:
            # Pure punctuation token — attach to previous word if possible
            if words:
                word_post_punct[-1] += pre + post
            continue

        words.append(rt)
        word_added.append(is_added)
        word_pre_punct.append(pre)
        word_post_punct.append(post)

    # Build added_indices list
    added_indices = [i for i, a in enumerate(word_added) if a]

    return {
        "raw": raw,
        "text": " ".join(words),
        "words": words,
        "added_indices": added_indices,
        "pre_punct": word_pre_punct,
        "post_punct": word_post_punct,
    }


def main():
    parser = argparse.ArgumentParser(description="Parse BLB CSV into JSON")
    parser.add_argument("file", help="BLB CSV input file")
    parser.add_argument("-o", "--output", default="output/blb_parsed.json",
                        help="Output JSON file")
    args = parser.parse_args()

    result = {}
    skipped = 0

    with open(args.file, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row_num, row in enumerate(reader):
            # Skip header/copyright lines (first 3 lines)
            if row_num < 3:
                continue

            if len(row) < 2:
                continue

            verse_ref = row[0].strip()
            text = row[1].strip() if len(row) > 1 else ""

            # Skip empty OT entries
            if not text:
                skipped += 1
                continue

            parsed = parse_blb_text(text)
            if parsed:
                result[verse_ref] = parsed

    print(f"Parsed {len(result)} verses (skipped {skipped} empty).", file=sys.stderr)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print(f"Written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
