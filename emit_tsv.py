#!/usr/bin/env python3
"""Generate BLB interlinear TSV using MSB source as scaffold.

Walks through the MSB (Majority Standard Bible) source TSV verse by verse.
For each verse:
1. Collects all scaffold rows
2. Matches Greek rows to aligned BLB words
3. Re-sorts rows by BLB English reading order
4. Emits with updated BLB Sort values

Usage:
    python3 emit_tsv.py output/aligned.json -o output/blb_interlinear.tsv \\
        --scaffold cache/majoritybible/source.tsv \\
        --tagnt output/tagnt_parsed.json \\
        --blb output/blb_parsed.json
"""

import argparse
import json
import re
import sys


def load_aligned(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_verse_mapping(aligned_verse, blb_verse):
    """Build mappings for a verse's alignment data.

    Returns:
        greek_to_eng: dict gi → (eng_text, begQ, pnc, endQ, first_eng_idx)
        non_greek: list of (eng_text, begQ, pnc, endQ, first_eng_idx)
    """
    words = blb_verse["words"]
    pre_puncts = blb_verse["pre_punct"]
    post_puncts = blb_verse["post_punct"]

    greek_to_eng = {}
    non_greek = []

    for a in aligned_verse:
        gi = a["greek_index"]
        ei_list = a["english_indices"]

        if not ei_list:
            continue

        eng_parts = []
        begQ = ""
        pnc = ""
        endQ = ""

        for idx, ei in enumerate(ei_list):
            eng_parts.append(words[ei])
            if idx == 0:
                pre = pre_puncts[ei] if ei < len(pre_puncts) else ""
                begQ = pre.replace("|", "\u201c") if pre else ""
            if idx == len(ei_list) - 1:
                post = post_puncts[ei] if ei < len(post_puncts) else ""
                for ch in post:
                    if ch == "|":
                        endQ += "\u201d"
                    elif ch in '.,;:!?':
                        pnc += ch
                    else:
                        pnc += ch

        eng_text = " ".join(eng_parts)
        first_ei = ei_list[0]

        if gi is not None:
            greek_to_eng[gi] = (eng_text, begQ, pnc, endQ, first_ei)
        else:
            non_greek.append((eng_text, begQ, pnc, endQ, first_ei))

    return greek_to_eng, non_greek


def match_greek_row(row_strongs, row_greek_sort, greek_words, used_gi):
    """Find the best matching greek_index for a scaffold row."""
    if not row_strongs:
        return None

    try:
        strongs_num = int(row_strongs)
        target_strongs = f"G{strongs_num:04d}"
    except ValueError:
        target_strongs = row_strongs

    candidates = []
    for gi, gw in enumerate(greek_words):
        if gi in used_gi:
            continue
        gs = gw.get("strongs", "")
        gs_norm = re.match(r'^(G\d+)', gs)
        gs_norm = gs_norm.group(1) if gs_norm else gs
        if gs_norm == target_strongs:
            candidates.append(gi)

    if not candidates:
        return None

    return min(candidates, key=lambda gi: abs(gi + 1 - row_greek_sort))


def process_verse(verse_rows, verse_id, verse_eng, tagnt, base_sort):
    """Process all scaffold rows for a single verse.

    Returns list of (sort_key, fields) tuples, sorted by BLB reading order.
    """
    if verse_id not in verse_eng:
        # No alignment data — pass through as-is
        return [fields for fields in verse_rows]

    greek_to_eng, non_greek = verse_eng[verse_id]
    greek_words = tagnt.get(verse_id, [])
    used_gi = set()

    # Phase 1: match each Greek scaffold row to alignment data
    matched_rows = []    # (first_eng_idx, fields) for rows with BLB matches
    unmatched_rows = []  # (fields,) for padding rows not yet assigned
    greek_no_eng = []    # Greek rows with no BLB English

    for fields in verse_rows:
        row_strongs = fields[11].strip()
        row_greek_word = fields[6].strip() if len(fields) > 6 else ""

        try:
            row_greek_sort = int(fields[1]) if fields[1].strip() else 0
        except ValueError:
            row_greek_sort = 0

        if not row_greek_word and not row_strongs:
            # Padding row
            unmatched_rows.append(fields)
            continue

        gi = match_greek_row(row_strongs, row_greek_sort, greek_words, used_gi)

        if gi is not None and gi in greek_to_eng:
            eng_text, begQ, pnc, endQ, first_ei = greek_to_eng[gi]
            fields[17] = begQ
            fields[18] = f" {eng_text} "
            fields[19] = pnc
            fields[20] = endQ
            used_gi.add(gi)
            matched_rows.append((first_ei, fields))
        else:
            # Greek word with no BLB match
            fields[18] = " - "
            greek_no_eng.append(fields)

    # Phase 2: assign non-Greek (added) words to padding rows
    non_greek_sorted = sorted(non_greek, key=lambda x: x[4])  # sort by first_eng_idx
    non_greek_matched = []

    for ng in non_greek_sorted:
        eng_text, begQ, pnc, endQ, first_ei = ng
        if unmatched_rows:
            fields = unmatched_rows.pop(0)
            fields[17] = begQ
            fields[18] = f" {eng_text} "
            fields[19] = pnc
            fields[20] = endQ
            non_greek_matched.append((first_ei, fields))
        # else: more added words than padding rows — skip

    # Phase 3: handle remaining padding rows (blank)
    blank_rows = []
    for fields in unmatched_rows:
        fields[18] = " "
        blank_rows.append(fields)

    # Phase 4: combine and sort all rows by BLB English reading order
    # matched_rows and non_greek_matched have (first_eng_idx, fields)
    # greek_no_eng rows: place them at their Greek position relative to matched rows
    all_sorted = []
    all_sorted.extend(matched_rows)
    all_sorted.extend(non_greek_matched)

    # For unmatched Greek words, estimate position based on Greek index ratio
    if matched_rows:
        max_ei = max(ei for ei, _ in matched_rows) if matched_rows else 0
        for fields in greek_no_eng:
            try:
                grk_sort = int(fields[1]) if fields[1].strip() else 0
            except ValueError:
                grk_sort = 0
            n_greek = len(greek_words) if greek_words else 1
            est_ei = (grk_sort / max(n_greek, 1)) * max_ei
            all_sorted.append((est_ei, fields))

    # Sort by English word index
    all_sorted.sort(key=lambda x: x[0])

    # Append blank padding rows at the end
    for fields in blank_rows:
        all_sorted.append((999999, fields))

    # Assign new BLB Sort values
    result = []
    for sort_pos, (_, fields) in enumerate(all_sorted, start=1):
        fields[2] = str(base_sort + sort_pos)
        result.append(fields)

    return result


def main():
    parser = argparse.ArgumentParser(description="Emit BLB interlinear TSV")
    parser.add_argument("aligned", help="Aligned JSON file")
    parser.add_argument("-o", "--output", default="output/blb_interlinear.tsv")
    parser.add_argument("--scaffold", default="sources/msb_source.tsv",
                        help="MSB source TSV to use as scaffold")
    parser.add_argument("--tagnt", default="output/tagnt_parsed.json")
    parser.add_argument("--blb", default="output/blb_parsed.json")
    args = parser.parse_args()

    print("Loading data...", file=sys.stderr)
    aligned = load_aligned(args.aligned)

    with open(args.tagnt, "r", encoding="utf-8") as f:
        tagnt = json.load(f)

    with open(args.blb, "r", encoding="utf-8") as f:
        blb = json.load(f)

    # Pre-build per-verse English mappings
    verse_eng = {}
    for verse_ref in aligned:
        if verse_ref in blb:
            greek_to_eng, non_greek = build_verse_mapping(
                aligned[verse_ref], blb[verse_ref]
            )
            verse_eng[verse_ref] = (greek_to_eng, non_greek)

    print("Processing scaffold...", file=sys.stderr)

    out_lines = []
    rows_written = 0
    verses_processed = 0

    with open(args.scaffold, "r", encoding="utf-8-sig") as f:
        header = f.readline().rstrip("\n\r")
        hdr_fields = header.split("\t")
        if len(hdr_fields) > 18:
            hdr_fields[18] = " BLB version "
        if len(hdr_fields) > 2:
            hdr_fields[2] = "BLB Sort"
        out_lines.append("\t".join(hdr_fields))

        # Collect rows by verse
        current_verse_num = None
        current_verse_id = None
        verse_rows = []

        def flush_verse():
            nonlocal rows_written, verses_processed
            if not verse_rows or current_verse_id is None:
                return

            # Determine base sort from first row
            try:
                base_sort = int(verse_rows[0][2]) - 1
            except (ValueError, IndexError):
                base_sort = 0

            result = process_verse(
                verse_rows, current_verse_id, verse_eng, tagnt, base_sort
            )
            for fields in result:
                out_lines.append("\t".join(fields))
                rows_written += 1
            verses_processed += 1

        for line in f:
            line = line.rstrip("\n\r")
            fields = line.split("\t")

            if len(fields) < 23:
                fields.extend([""] * (23 - len(fields)))

            lang = fields[4].strip()
            if lang != "Greek":
                flush_verse()
                verse_rows = []
                current_verse_id = None
                current_verse_num = None
                out_lines.append(line)
                continue

            verse_num = fields[3]
            verse_id = fields[12].strip() if fields[12].strip() else current_verse_id

            # Detect verse change
            if verse_id and verse_id != current_verse_id:
                flush_verse()
                verse_rows = []
                current_verse_id = verse_id
                current_verse_num = verse_num

            verse_rows.append(fields)

        # Flush final verse
        flush_verse()

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")

    print(f"Written {rows_written} rows for {verses_processed} verses to {args.output}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
