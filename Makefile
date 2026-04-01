PYTHON = python3

# Source data paths (populated by fetch_sources.sh)
SOURCES_DIR = sources
TAGNT_MAT_JHN = $(SOURCES_DIR)/tagnt_mat_jhn.txt
TAGNT_ACT_REV = $(SOURCES_DIR)/tagnt_act_rev.txt
BSB_SOURCE = $(SOURCES_DIR)/bsb_source.tsv
BSB_SCAFFOLD = $(SOURCES_DIR)/bsb_source.tsv
MSB_SCAFFOLD = $(SOURCES_DIR)/msb_source.tsv
LEXICON = $(SOURCES_DIR)/stepbible-tbesg.json
USJ_DIR = $(SOURCES_DIR)/bsb_strongs_full

# Input and output
INPUT_CSV = $(SOURCES_DIR)/blb.csv
OUTPUT_DIR = output

# Release version (set via: make release VERSION=v1.1)
VERSION ?= v1.0

.PHONY: all help fetch berean majority parse align test clean release

# Default: build both editions
all: berean majority

berean: $(OUTPUT_DIR)/blb_interlinear_bsb.tsv
	@echo "Berean edition complete: $<"

majority: $(OUTPUT_DIR)/blb_interlinear_msb.tsv
	@echo "Majority edition complete: $<"

help:
	@echo "Usage:"
	@echo "  ./fetch_sources.sh  -- download all source data (run once)"
	@echo "  make all            -- build both BSB and MSB editions"
	@echo "  make berean         -- build BSB scaffold edition only"
	@echo "  make majority       -- build MSB scaffold edition only"
	@echo "  make parse          -- parse TAGNT and BLB CSV"
	@echo "  make align          -- align English words to Greek words"
	@echo "  make test           -- run alignment quality tests"
	@echo "  make clean          -- remove generated output files"
	@echo "  make release        -- create GitHub release (VERSION=v1.0)"
	@echo ""
	@echo "Input:  $(INPUT_CSV) (Berean Literal Bible)"
	@echo "Output: $(OUTPUT_DIR)/blb_interlinear_bsb.tsv (BSB scaffold)"
	@echo "        $(OUTPUT_DIR)/blb_interlinear_msb.tsv (MSB scaffold)"

# Fetch sources (delegates to fetch_sources.sh)
fetch:
	./fetch_sources.sh

# Ensure output directory exists
$(OUTPUT_DIR):
	mkdir -p $(OUTPUT_DIR)

# Check that sources exist
$(TAGNT_MAT_JHN) $(TAGNT_ACT_REV) $(BSB_SOURCE) $(MSB_SCAFFOLD) $(LEXICON) $(INPUT_CSV):
	@echo "Error: $@ not found. Run './fetch_sources.sh' first." && exit 1

# ── Parse ─────────────────────────────────────────────────────────────────────

$(OUTPUT_DIR)/tagnt_parsed.json: $(TAGNT_MAT_JHN) $(TAGNT_ACT_REV) | $(OUTPUT_DIR)
	@echo "Parsing TAGNT files..."
	$(PYTHON) parse_tagnt.py $(TAGNT_MAT_JHN) $(TAGNT_ACT_REV) -o $@

$(OUTPUT_DIR)/blb_parsed.json: $(INPUT_CSV) | $(OUTPUT_DIR)
	@echo "Parsing BLB CSV..."
	$(PYTHON) parse_csv.py $(INPUT_CSV) -o $@

parse: $(OUTPUT_DIR)/tagnt_parsed.json $(OUTPUT_DIR)/blb_parsed.json
	@echo "Parsing complete."

# ── Align ─────────────────────────────────────────────────────────────────────

$(OUTPUT_DIR)/aligned.json: $(OUTPUT_DIR)/tagnt_parsed.json $(OUTPUT_DIR)/blb_parsed.json $(BSB_SOURCE) $(LEXICON)
	@echo "Aligning English to Greek..."
	$(PYTHON) align.py $(OUTPUT_DIR)/tagnt_parsed.json $(OUTPUT_DIR)/blb_parsed.json $(BSB_SOURCE) -o $@ --lexicon $(LEXICON) --usj-dir $(USJ_DIR)

align: $(OUTPUT_DIR)/aligned.json
	@echo "Alignment complete."

# ── Emit (two editions, same alignment, different scaffolds) ──────────────────

$(OUTPUT_DIR)/blb_interlinear_bsb.tsv: $(OUTPUT_DIR)/aligned.json $(BSB_SCAFFOLD) $(OUTPUT_DIR)/tagnt_parsed.json $(OUTPUT_DIR)/blb_parsed.json
	@echo "Generating BSB edition..."
	$(PYTHON) emit_tsv.py $(OUTPUT_DIR)/aligned.json -o $@ --scaffold $(BSB_SCAFFOLD) --tagnt $(OUTPUT_DIR)/tagnt_parsed.json --blb $(OUTPUT_DIR)/blb_parsed.json

$(OUTPUT_DIR)/blb_interlinear_msb.tsv: $(OUTPUT_DIR)/aligned.json $(MSB_SCAFFOLD) $(OUTPUT_DIR)/tagnt_parsed.json $(OUTPUT_DIR)/blb_parsed.json
	@echo "Generating MSB edition..."
	$(PYTHON) emit_tsv.py $(OUTPUT_DIR)/aligned.json -o $@ --scaffold $(MSB_SCAFFOLD) --tagnt $(OUTPUT_DIR)/tagnt_parsed.json --blb $(OUTPUT_DIR)/blb_parsed.json

# ── Test ──────────────────────────────────────────────────────────────────────

test: $(OUTPUT_DIR)/aligned.json
	@echo "Running alignment tests..."
	$(PYTHON) test_alignment.py

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	rm -rf $(OUTPUT_DIR)

# ── Release ───────────────────────────────────────────────────────────────────

release: $(OUTPUT_DIR)/blb_interlinear_bsb.tsv $(OUTPUT_DIR)/blb_interlinear_msb.tsv
	@echo "Creating release $(VERSION)..."
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working tree is not clean. Commit changes first."; \
		exit 1; \
	fi
	@echo "Packaging assets..."
	@mkdir -p $(OUTPUT_DIR)/release
	@zip -j $(OUTPUT_DIR)/release/BLB_interlinear_bsb.zip $(OUTPUT_DIR)/blb_interlinear_bsb.tsv
	@zip -j $(OUTPUT_DIR)/release/BLB_interlinear_msb.zip $(OUTPUT_DIR)/blb_interlinear_msb.tsv
	@zip -j $(OUTPUT_DIR)/release/BLB_source_csv.zip $(INPUT_CSV)
	@zip -j $(OUTPUT_DIR)/release/BLB_aligned_json.zip $(OUTPUT_DIR)/aligned.json
	git tag -f $(VERSION)
	git push origin $(VERSION)
	gh release create $(VERSION) \
		--title "BLB Interlinear $(VERSION)" \
		--notes-file RELEASE_NOTES.md \
		$(OUTPUT_DIR)/release/BLB_interlinear_bsb.zip \
		$(OUTPUT_DIR)/release/BLB_interlinear_msb.zip \
		$(OUTPUT_DIR)/release/BLB_source_csv.zip \
		$(OUTPUT_DIR)/release/BLB_aligned_json.zip
	@echo "Released $(VERSION): https://github.com/BSB-publishing/blb2bsb/releases/tag/$(VERSION)"
