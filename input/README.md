# Custom Input

Place a `.csv` file in this directory to use it instead of the default
Berean Literal Bible. If no CSV is found here, the pipeline uses
`sources/blb.csv` (fetched by `fetch_sources.sh`).

Only the first `.csv` file found (alphabetically) will be used.

## Expected CSV Format

```
Verse,Translation Name
Genesis 1:1,
Genesis 1:2,
...
Matthew 1:1,"<i>The</i> book of <i>the</i> genealogy of Jesus Christ, son of David, son of Abraham:"
Matthew 1:2,"Abraham begat Isaac, and Isaac begat Jacob, and Jacob begat Judah and his brothers."
```

### Requirements

- **Column 1:** Verse reference in `Book Chapter:Verse` format (e.g., `Matthew 1:1`)
- **Column 2:** English translation text
- **Encoding:** UTF-8
- **Header rows:** The first 3 lines are skipped (copyright, description, column header)
- **OT verses:** May be present but will be ignored (empty text)
- **NT verses:** Must cover Matthew through Revelation (~7,941 verses)

### Optional Features

- **`<i>` tags:** Wrap translator-added words in `<i>...</i>` to mark them as
  having no Greek source word. This improves alignment accuracy.
  Example: `<i>The</i> book` means "The" was added by the translator.

- **`|` quotes:** Use `|` to mark direct speech boundaries.
  Example: `Jesus said, |Go and sin no more.|`

### Best Results

The alignment works best with **literal translations** where:
- English word order closely follows the Greek
- Most Greek words have a direct English equivalent
- Added words are marked with `<i>` tags

More dynamic/paraphrastic translations will have lower alignment confidence.
