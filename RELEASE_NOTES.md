# Berean Literal Bible Interlinear

23-column word-level interlinear of the Berean Literal Bible (BLB), aligned to the Greek New Testament.

Two editions are provided, using different scaffolds:

## Assets

### Berean Standard Bible scaffold
- **BLB_interlinear_bsb.zip** — BLB interlinear using BSB column structure (full Bible scaffold, Greek NT rows)

### Majority Standard Bible scaffold
- **BLB_interlinear_msb.zip** — BLB interlinear using MSB column structure (NT-only scaffold)

### Source data
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
- **Scaffolds:** Berean Standard Bible ([bereanbible.com](https://bereanbible.com)) and Majority Standard Bible ([majoritybible.com](https://majoritybible.com))
