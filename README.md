# BLB to BSB Interlinear Converter

Convert verse-level Bible translations (like the Berean Literal Bible) into word-level interlinear format compatible with the BSB/MSB interlinear tables.

## Overview

This project solves the challenge of converting **verse-level English translations** into **word-level Greek-aligned interlinear data**. Unlike the [usj2bsb](https://github.com/BSB-publishing/usj2bsb) reference repository which works from USJ (JSON) input with pre-existing word boundaries, this pipeline performs automatic word-level alignment from plain verse text to Greek source words.

## Input Data

### 1. Berean Literal Bible (BLB)
- **Format:** CSV with columns: `Verse` (e.g. "Matthew 1:1"), `Text`
- **Scope:** New Testament only (~7,941 verses)
- **Features:** 
  - Literal translation with close word-for-word correspondence to Greek
  - `<i>` tags mark translator-added words (not in Greek source)
- **License:** Free (see http://berean.bible/licensing.htm)
- **Location:** `example/blb.csv`

Example:
```
Matthew 1:1,"<i>The</i> book of <i>the</i> genealogy of Jesus Christ, son of David, son of Abraham:"
```

### 2. STEPBible TAGNT (Greek NT)
- **Source:** https://github.com/STEPBible/STEPBible-Data
- **Format:** Tab-separated, one word per line
- **Key Features:**
  - All major Greek text traditions (NA27/28, TR, Byz, SBLGNT, WH, etc.)
  - Disambiguated Extended Strong's numbers (e.g. G1161a)
  - Robinson morphology codes
  - Context-sensitive English glosses
  - Text tradition markers for each word
- **License:** CC BY 4.0
- **Cached in:** `cache/tagnt_mat_jhn.txt`, `cache/tagnt_act_rev.txt`

### 3. BSB Source Tables (Reference)
- **Source:** https://bereanbible.com/bsb_tables.tsv
- **Purpose:** Defines target 23-column output format and provides training data for alignment
- **Cached in:** `cache/bsb_source.tsv`

## Output Format

The pipeline generates a 23-column TSV file matching the BSB interlinear format:

| Column | Name | Description | Source |
|--------|------|-------------|--------|
| 0 | Heb Sort | Hebrew word order | n/a for NT |
| 1 | Greek Sort | Greek word order | TAGNT position |
| 2 | BSB Sort | English word order | Derived from BLB |
| 3 | Verse | Verse number | Parsed from reference |
| 4 | Language | "Greek" for NT | Static |
| 5 | Nestle Base | Greek word (plain) | TAGNT |
| 6 | Nestle Base (variants) | With text tradition markers | TAGNT |
| 7 | Translit | Transliteration | Generated from Greek |
| 8 | Parsing (short) | Morphology abbreviation | TAGNT |
| 9 | Parsing (long) | Expanded morphology | TAGNT |
| 10 | Str Heb | Hebrew Strong's | empty for NT |
| 11 | Str Grk | Greek Strong's | TAGNT |
| 12 | VerseId | "Matthew 1:1" | From BLB |
| 13 | Hdg | Section heading | empty or from BLB |
| 14 | Crossref | Cross-references | empty |
| 15 | Par | Paragraph marker | empty |
| 16 | Space | Spacing | Generated |
| 17 | begQ | Opening quote mark | Parsed from BLB |
| 18 | English text | English word(s) | **BLB translation** |
| 19 | pnc | Punctuation | Parsed from BLB |
| 20 | endQ | Closing quote mark | Parsed from BLB |
| 21 | footnotes | Footnotes | empty |
| 22 | End text | End markers | empty |

## Pipeline Architecture

### Step 1: Download and Cache (`make download`)
Downloads source files to `cache/` directory (git-ignored):
- TAGNT Mat-Jhn from STEPBible GitHub
- TAGNT Act-Rev from STEPBible GitHub
- BSB source TSV from bereanbible.com (with conditional update check)

### Step 2: Parse TAGNT (`parse_tagnt.py`)
Parses TAGNT files into structured JSON:
```python
{
  "Matthew 1:1": [
    {
      "position": 1,
      "greek": "Βίβλος",
      "strongs": "G0976",
      "morphology": "N-NSF",
      "gloss": "book",
      "editions": ["NA28", "TR", "Byz", ...]
    },
    ...
  ]
}
```

### Step 3: Parse BLB CSV (`parse_csv.py`)
Parses translation CSV into structured JSON:
```python
{
  "Matthew 1:1": {
    "text": "The book of the genealogy of Jesus Christ...",
    "words": ["The", "book", "of", "the", "genealogy", ...],
    "added_words": [0, 3],  # indices of <i>-tagged words
    "raw": "<i>The</i> book of <i>the</i> genealogy..."
  }
}
```

### Step 4: Align English to Greek (`align.py`)
Core alignment algorithm using multiple strategies:

1. **Gloss Matching:** Compare BLB words to TAGNT context-sensitive glosses
2. **Strong's Pattern Learning:** Extract Strong's → English mappings from BSB source
3. **Positional Heuristics:** Leverage BLB's literal translation order
4. **Multi-word Expressions:** Handle Greek words mapping to multiple English words

Outputs alignment data:
```python
{
  "Matthew 1:1": [
    {
      "greek_index": 0,
      "english_indices": [1],  # "book" maps to Βίβλος
      "strongs": "G0976",
      "confidence": 0.95
    },
    {
      "greek_index": None,
      "english_indices": [0],  # "The" is translator addition
      "strongs": None,
      "confidence": 1.0
    },
    ...
  ]
}
```

### Step 5: Emit TSV (`emit_tsv.py`)
Generates the final 23-column TSV file with:
- Greek columns from TAGNT
- English columns from BLB
- Punctuation, quotes, spacing parsed and separated
- Proper sort orders maintained

## Installation & Usage

### Prerequisites
- Python 3.6+
- `curl`, `make`, `npm` (for lexicon download), `unzip`
- `gh` CLI (optional, for GitHub release download; falls back to `curl`)
- No external Python dependencies (uses stdlib only)

### Quick Start

```bash
# 1. Fetch all source data (only downloads what's missing or outdated)
./fetch_sources.sh

# 2. Run the full pipeline
make all

# Output will be in: output/blb_interlinear.tsv
```

### Individual Steps

```bash
# Parse source files only
make parse

# Run alignment algorithm
make align

# Generate output TSV
make emit

# Run alignment quality tests
make test

# Clean generated files
make clean
```

### Source Data

All external source data lives in `sources/` (gitignored). Run `./fetch_sources.sh` to populate it.
The script uses conditional downloads (`curl -z`) so re-running only fetches files that are newer on the remote.

| File | Source | License |
|------|--------|---------|
| `tagnt_mat_jhn.txt` | [STEPBible TAGNT](https://github.com/STEPBible/STEPBible-Data) | CC-BY 4.0 |
| `tagnt_act_rev.txt` | STEPBible TAGNT | CC-BY 4.0 |
| `stepbible-tbesg.json` | [STEPBible Lexicon](https://www.npmjs.com/package/@metaxia/scriptures-source-stepbible-lexicon) (Greek) | CC-BY 4.0 |
| `stepbible-tbesh.json` | STEPBible Lexicon (Hebrew) | CC-BY 4.0 |
| `bsb_source.tsv` | [bereanbible.com](https://bereanbible.com/bsb_tables.tsv) | Free licensing |
| `msb_source.tsv` | [majoritybible.com](https://majoritybible.com/msb_nt_tables.tsv) | Free licensing |
| `bsb_strongs_full/` | [BSB-publishing/bsb2usfm](https://github.com/BSB-publishing/bsb2usfm/releases) releases | Free licensing |

## Project Structure

```
blb2bsb/
├── Makefile               # Pipeline orchestration
├── fetch_sources.sh       # Download all source data
├── README.md              # This file
├── .gitignore             # Git ignore patterns
│
├── sources/               # External source data (git-ignored, fetched by fetch_sources.sh)
│   ├── tagnt_mat_jhn.txt      # TAGNT Greek NT (Matthew–John)
│   ├── tagnt_act_rev.txt      # TAGNT Greek NT (Acts–Revelation)
│   ├── bsb_source.tsv         # BSB full interlinear source
│   ├── msb_source.tsv         # MSB NT interlinear source (scaffold)
│   ├── stepbible-tbesg.json   # Greek Extended Strong's lexicon
│   ├── stepbible-tbesh.json   # Hebrew Extended Strong's lexicon
│   └── bsb_strongs_full/      # BSB word-level Strong's (USJ, 66 books)
│
├── example/               # Input data
│   └── blb.csv            # Berean Literal Bible CSV
│
├── output/                # Generated files (git-ignored)
│   ├── tagnt_parsed.json
│   ├── blb_parsed.json
│   ├── aligned.json
│   └── blb_interlinear.tsv   # FINAL OUTPUT
│
├── parse_tagnt.py         # Parse TAGNT to JSON
├── parse_csv.py           # Parse BLB CSV to JSON
├── align.py               # Alignment algorithm
├── emit_tsv.py            # Generate 23-column TSV
└── test_alignment.py      # Alignment quality tests
```

## Alignment Strategy

The BLB is a **literal translation**, meaning:
- Word order closely tracks Greek
- Most Greek words have direct English equivalents
- Added words are explicitly marked with `<i>` tags

### Alignment Priority (in order):

1. **Explicit Non-Alignment:** `<i>` tagged words get no Strong's number
2. **Gloss Exact Match:** TAGNT gloss == BLB word (case-insensitive)
3. **Gloss Fuzzy Match:** High similarity between gloss and word
4. **Strong's Pattern:** Use BSB source to learn Strong's → common English words
5. **Positional Proximity:** When ambiguous, prefer nearby words
6. **Multi-word Grouping:** One Greek word → multiple English words

### Confidence Scoring

Each alignment gets a confidence score (0.0 to 1.0):
- 1.0: `<i>` tagged (explicit non-alignment)
- 0.95: Exact gloss match
- 0.85: Strong's pattern match from BSB
- 0.70: Fuzzy gloss match
- 0.50: Positional heuristic

Low-confidence alignments can be flagged for manual review.

## License

This project uses data from multiple sources:

- **STEPBible TAGNT:** CC BY 4.0 (credit to STEPBible.org)
- **Berean Literal Bible:** Free licensing (see http://berean.bible/licensing.htm)
- **This Pipeline Code:** MIT License (see LICENSE file)

When using output data, please credit:
- "Greek text from STEPBible TAGNT (STEPBible.org, CC BY 4.0)"
- "English translation from Berean Literal Bible (berean.bible)"

## Related Projects

- **usj2bsb:** https://github.com/BSB-publishing/usj2bsb  
  Reference implementation for USJ → BSB interlinear conversion
  
- **STEPBible Data:** https://github.com/STEPBible/STEPBible-Data  
  Source of TAGNT Greek text data

- **Berean Bible:** https://berean.bible  
  Source of BLB translation

## Contributing

Contributions welcome! Areas for improvement:

1. **Alignment accuracy:** Test against known alignments, improve algorithms
2. **Edge cases:** Handle quotations, poetry, textual variants
3. **Performance:** Optimize for large-scale processing
4. **Documentation:** Add examples, tutorials, alignment guidelines

## Contact

For questions or issues with:
- **This pipeline:** Open an issue on GitHub
- **TAGNT data:** Contact STEPBibleATgmail.com
- **BLB translation:** Contact bereanstudybible@aol.com