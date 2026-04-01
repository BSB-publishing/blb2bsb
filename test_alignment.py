#!/usr/bin/env python3
"""Test alignment quality by comparing with BSB source and spot-checking.

Usage:
    python3 test_alignment.py
"""

import json
import re
import sys
from collections import Counter


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_bsb_verse_words(bsb_path, verse_id):
    """Load BSB word-level data for a verse from the source TSV."""
    words = []
    with open(bsb_path, "r", encoding="utf-8-sig") as f:
        in_verse = False
        for line in f:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 19:
                continue
            vid = fields[12].strip()
            if vid == verse_id:
                in_verse = True
            elif in_verse and vid and vid != verse_id:
                break
            if not in_verse:
                continue
            if fields[4].strip() != "Greek":
                continue
            strongs = fields[11].strip()
            english = fields[18].strip()
            if strongs and english and english != "-":
                try:
                    snum = int(strongs)
                    words.append((f"G{snum:04d}", english.lower()))
                except ValueError:
                    pass
    return words


def print_verse_alignment(verse_ref, aligned, tagnt, blb):
    """Pretty-print alignment for a single verse."""
    print(f"\n{'='*60}")
    print(f"  {verse_ref}")
    print(f"{'='*60}")
    print(f"  BLB: {blb[verse_ref]['text']}")
    print()

    for a in aligned[verse_ref]:
        gi = a["greek_index"]
        if gi is not None:
            gw = tagnt[verse_ref][gi]
            greek = gw["greek"]
            strongs = a["strongs"] or ""
        else:
            greek = "-"
            strongs = ""

        eng = ", ".join(blb[verse_ref]["words"][i] for i in a["english_indices"]) if a["english_indices"] else "-"
        conf = a["confidence"]
        method = a["method"]

        print(f"  {greek:20s} -> {eng:25s} [{strongs:>8s}] {conf:.2f} {method}")


def compute_stats(aligned):
    """Compute overall alignment statistics."""
    method_counts = Counter()
    confidence_sum = 0
    confidence_count = 0
    total_greek = 0
    total_eng = 0
    matched_greek = 0

    for verse_ref, aligns in aligned.items():
        for a in aligns:
            method_counts[a["method"]] += 1
            confidence_sum += a["confidence"]
            confidence_count += 1

            if a["greek_index"] is not None:
                total_greek += 1
                if a["english_indices"]:
                    matched_greek += 1
            if a["english_indices"]:
                total_eng += len(a["english_indices"])

    return {
        "method_counts": dict(method_counts),
        "avg_confidence": confidence_sum / max(confidence_count, 1),
        "total_greek": total_greek,
        "matched_greek": matched_greek,
        "greek_coverage": matched_greek / max(total_greek, 1) * 100,
        "total_english": total_eng,
        "total_verses": len(aligned),
    }


def main():
    print("Loading data...", file=sys.stderr)

    try:
        aligned = load_json("output/aligned.json")
        tagnt = load_json("output/tagnt_parsed.json")
        blb = load_json("output/blb_parsed.json")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run 'make parse' and 'make align' first.", file=sys.stderr)
        sys.exit(1)

    # Test verses
    test_verses = [
        "Matthew 1:1",   # Simple genealogy
        "Matthew 1:23",  # Quotation with additions
        "John 1:1",      # Theological (In the beginning was the Word)
        "John 3:16",     # Famous verse
        "Acts 2:14",     # Speech
        "Romans 8:28",   # Theological
    ]

    print("\n" + "="*60)
    print("  ALIGNMENT SPOT CHECKS")
    print("="*60)

    for verse in test_verses:
        if verse in aligned and verse in blb:
            print_verse_alignment(verse, aligned, tagnt, blb)
        else:
            print(f"\n  {verse}: NOT FOUND in alignment data")

    # Overall statistics
    print("\n\n" + "="*60)
    print("  OVERALL STATISTICS")
    print("="*60)

    stats = compute_stats(aligned)

    print(f"\n  Verses aligned:     {stats['total_verses']}")
    print(f"  Greek words total:  {stats['total_greek']}")
    print(f"  Greek words matched:{stats['matched_greek']}")
    print(f"  Greek coverage:     {stats['greek_coverage']:.1f}%")
    print(f"  English words:      {stats['total_english']}")
    print(f"  Avg confidence:     {stats['avg_confidence']:.3f}")

    print(f"\n  Method breakdown:")
    for method, count in sorted(stats["method_counts"].items(), key=lambda x: -x[1]):
        pct = count / sum(stats["method_counts"].values()) * 100
        print(f"    {method:25s} {count:>8d}  ({pct:.1f}%)")

    # Confidence distribution
    print(f"\n  Confidence distribution:")
    conf_buckets = Counter()
    for aligns in aligned.values():
        for a in aligns:
            bucket = round(a["confidence"], 1)
            conf_buckets[bucket] += 1

    for bucket in sorted(conf_buckets.keys(), reverse=True):
        count = conf_buckets[bucket]
        pct = count / sum(conf_buckets.values()) * 100
        bar = "#" * int(pct)
        print(f"    {bucket:.1f}: {count:>8d}  ({pct:>5.1f}%) {bar}")

    print()


if __name__ == "__main__":
    main()
