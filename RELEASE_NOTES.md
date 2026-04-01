# Berean Literal Bible Interlinear

23-column word-level interlinear of the Berean Literal Bible (BLB), aligned to the Greek New Testament.

## Assets

- **BLB_interlinear_tsv.zip** — Full NT interlinear TSV (7,932 verses, 219K rows, 23-column BSB format)
- **BLB_source_csv.zip** — BLB verse-level translation (input CSV)
- **BLB_aligned_json.zip** — Word-level alignment data (JSON, with confidence scores and method metadata)

## How to reproduce

```bash
git clone https://github.com/BSB-publishing/blb2bsb.git
cd blb2bsb
./fetch_sources.sh
make all
```

## Credits

- **English text:** Berean Literal Bible ([berean.bible](https://berean.bible))
- **Greek text:** TAGNT from [STEPBible.org](https://www.STEPBible.org) (CC BY 4.0), Tyndale House, Cambridge
- **Lexicon data:** STEPBible Extended Strong's (CC BY 4.0), Tyndale House, Cambridge
- **Scaffold:** Majority Standard Bible ([majoritybible.com](https://majoritybible.com))
