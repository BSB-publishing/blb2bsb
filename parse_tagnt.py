#!/usr/bin/env python3
"""Parse TAGNT (Translators Amalgamated Greek NT) files into structured JSON.

Reads the STEPBible TAGNT tab-separated files and extracts per-word data:
Greek text, Strong's number, morphology, gloss, editions, transliteration.

Usage:
    python3 parse_tagnt.py cache/tagnt_mat_jhn.txt cache/tagnt_act_rev.txt -o output/tagnt_parsed.json
"""

import argparse
import json
import re
import sys


# Book abbreviation to full name mapping (TAGNT uses 3-letter codes)
BOOK_NAMES = {
    "Mat": "Matthew", "Mrk": "Mark", "Luk": "Luke", "Jhn": "John",
    "Act": "Acts", "Rom": "Romans", "1Co": "1 Corinthians", "2Co": "2 Corinthians",
    "Gal": "Galatians", "Eph": "Ephesians", "Php": "Philippians", "Col": "Colossians",
    "1Th": "1 Thessalonians", "2Th": "2 Thessalonians",
    "1Ti": "1 Timothy", "2Ti": "2 Timothy", "Tit": "Titus", "Phm": "Philemon",
    "Heb": "Hebrews", "Jas": "James",
    "1Pe": "1 Peter", "2Pe": "2 Peter",
    "1Jn": "1 John", "2Jn": "2 John", "3Jn": "3 John",
    "Jud": "Jude", "Rev": "Revelation",
}

# Pattern for word-level data lines, e.g.: Mat.1.1#01=NKO
WORD_LINE_RE = re.compile(
    r'^([A-Za-z0-9]+)\.(\d+)\.(\d+)#(\d+)=([A-Za-z()]+)\t'
)


def normalize_ref(book_abbr, chapter, verse):
    """Convert 'Mat.1.1' style to 'Matthew 1:1'."""
    full = BOOK_NAMES.get(book_abbr, book_abbr)
    return f"{full} {chapter}:{verse}"


def parse_strongs(raw):
    """Extract Strong's number from 'G0976=N-NSF' format."""
    if not raw or raw == "-":
        return None, None
    parts = raw.split("=", 1)
    strongs = parts[0].strip()
    morph = parts[1].strip() if len(parts) > 1 else ""
    return strongs, morph


def parse_greek_field(raw):
    """Extract Greek word and transliteration from 'Βίβλος (Biblos)' format."""
    raw = raw.strip()
    m = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return raw, ""


def parse_gloss_field(raw):
    """Extract dictionary form and gloss from 'βίβλος=book' format."""
    raw = raw.strip()
    parts = raw.split("=", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return raw, ""


def parse_editions(raw):
    """Parse edition list like 'NA28+NA27+Tyn+SBL+WH+Treg+TR+Byz'."""
    raw = raw.strip()
    if not raw:
        return []
    return [e.strip() for e in raw.split("+") if e.strip()]


def parse_file(filepath):
    """Parse a single TAGNT file, yielding (verse_ref, word_data) tuples."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\n\r")
            m = WORD_LINE_RE.match(line)
            if not m:
                continue

            book_abbr = m.group(1)
            chapter = m.group(2)
            verse = m.group(3)
            position = int(m.group(4))
            word_type = m.group(5)

            fields = line.split("\t")
            # fields[0] = reference+type, [1]=Greek, [2]=English, [3]=dStrongs=Grammar,
            # [4]=Dict=Gloss, [5]=editions, [6]=meaning variants, [7]=spelling variants,
            # [8]=Spanish, [9]=sub-meaning, [10]=conjoin, [11]=sStrong+Instance, ...

            greek_raw = fields[1] if len(fields) > 1 else ""
            english = fields[2].strip() if len(fields) > 2 else ""
            strongs_grammar = fields[3] if len(fields) > 3 else ""
            dict_gloss = fields[4] if len(fields) > 4 else ""
            editions_raw = fields[5] if len(fields) > 5 else ""

            greek_word, translit = parse_greek_field(greek_raw)
            strongs, morphology = parse_strongs(strongs_grammar)
            dict_form, gloss = parse_gloss_field(dict_gloss)
            editions = parse_editions(editions_raw)

            verse_ref = normalize_ref(book_abbr, chapter, verse)

            word_data = {
                "position": position,
                "greek": greek_word,
                "translit": translit,
                "english": english,
                "strongs": strongs,
                "morphology": morphology,
                "dict_form": dict_form,
                "gloss": gloss,
                "editions": editions,
                "word_type": word_type,
            }

            yield verse_ref, word_data


def main():
    parser = argparse.ArgumentParser(description="Parse TAGNT files into JSON")
    parser.add_argument("files", nargs="+", help="TAGNT input file(s)")
    parser.add_argument("-o", "--output", default="output/tagnt_parsed.json",
                        help="Output JSON file")
    args = parser.parse_args()

    result = {}
    word_count = 0

    for filepath in args.files:
        print(f"Parsing {filepath}...", file=sys.stderr)
        for verse_ref, word_data in parse_file(filepath):
            if verse_ref not in result:
                result[verse_ref] = []
            result[verse_ref].append(word_data)
            word_count += 1

    print(f"Parsed {word_count} words across {len(result)} verses.", file=sys.stderr)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print(f"Written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
