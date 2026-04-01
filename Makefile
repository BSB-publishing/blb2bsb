PYTHON = python3

# Source data paths (populated by fetch_sources.sh)
SOURCES_DIR = sources
TAGNT_MAT_JHN = $(SOURCES_DIR)/tagnt_mat_jhn.txt
TAGNT_ACT_REV = $(SOURCES_DIR)/tagnt_act_rev.txt
BSB_SOURCE = $(SOURCES_DIR)/bsb_source.tsv
MSB_SCAFFOLD = $(SOURCES_DIR)/msb_source.tsv
LEXICON = $(SOURCES_DIR)/stepbible-tbesg.json
USJ_DIR = $(SOURCES_DIR)/bsb_strongs_full

# Input and output
INPUT_CSV = example/blb.csv
OUTPUT_DIR = output

.PHONY: all help fetch parse align emit test clean

all: $(OUTPUT_DIR)/blb_interlinear.tsv

help:
	@echo "Usage:"
	@echo "  ./fetch_sources.sh  -- download all source data (run once)"
	@echo "  make all            -- run full pipeline (parse → align → emit)"
	@echo "  make parse          -- parse TAGNT and BLB CSV"
	@echo "  make align          -- align English words to Greek words"
	@echo "  make emit           -- generate 23-column TSV output"
	@echo "  make test           -- run alignment quality tests"
	@echo "  make clean          -- remove generated output files"
	@echo ""
	@echo "Input:    $(INPUT_CSV) (Berean Literal Bible)"
	@echo "Scaffold: $(MSB_SCAFFOLD) (Majority Standard Bible)"
	@echo "Output:   $(OUTPUT_DIR)/blb_interlinear.tsv (23-column interlinear)"

# Fetch sources (delegates to fetch_sources.sh)
fetch:
	./fetch_sources.sh

# Ensure output directory exists
$(OUTPUT_DIR):
	mkdir -p $(OUTPUT_DIR)

# Check that sources exist
$(TAGNT_MAT_JHN) $(TAGNT_ACT_REV) $(BSB_SOURCE) $(MSB_SCAFFOLD) $(LEXICON):
	@echo "Error: $@ not found. Run './fetch_sources.sh' first." && exit 1

# Parse TAGNT into structured data
$(OUTPUT_DIR)/tagnt_parsed.json: $(TAGNT_MAT_JHN) $(TAGNT_ACT_REV) | $(OUTPUT_DIR)
	@echo "Parsing TAGNT files..."
	$(PYTHON) parse_tagnt.py $(TAGNT_MAT_JHN) $(TAGNT_ACT_REV) -o $@

# Parse BLB CSV
$(OUTPUT_DIR)/blb_parsed.json: $(INPUT_CSV) | $(OUTPUT_DIR)
	@echo "Parsing BLB CSV..."
	$(PYTHON) parse_csv.py $(INPUT_CSV) -o $@

# Parse data
parse: $(OUTPUT_DIR)/tagnt_parsed.json $(OUTPUT_DIR)/blb_parsed.json
	@echo "Parsing complete."

# Align English words to Greek words
$(OUTPUT_DIR)/aligned.json: $(OUTPUT_DIR)/tagnt_parsed.json $(OUTPUT_DIR)/blb_parsed.json $(BSB_SOURCE) $(LEXICON)
	@echo "Aligning English to Greek..."
	$(PYTHON) align.py $(OUTPUT_DIR)/tagnt_parsed.json $(OUTPUT_DIR)/blb_parsed.json $(BSB_SOURCE) -o $@ --lexicon $(LEXICON) --usj-dir $(USJ_DIR)

align: $(OUTPUT_DIR)/aligned.json
	@echo "Alignment complete."

# Generate final TSV output using MSB scaffold
$(OUTPUT_DIR)/blb_interlinear.tsv: $(OUTPUT_DIR)/aligned.json $(MSB_SCAFFOLD) $(OUTPUT_DIR)/tagnt_parsed.json $(OUTPUT_DIR)/blb_parsed.json
	@echo "Generating output TSV..."
	$(PYTHON) emit_tsv.py $(OUTPUT_DIR)/aligned.json -o $@ --scaffold $(MSB_SCAFFOLD) --tagnt $(OUTPUT_DIR)/tagnt_parsed.json --blb $(OUTPUT_DIR)/blb_parsed.json
	@echo "Pipeline complete! Output: $@"

emit: $(OUTPUT_DIR)/blb_interlinear.tsv

# Test alignment quality
test: $(OUTPUT_DIR)/aligned.json
	@echo "Running alignment tests..."
	$(PYTHON) test_alignment.py

# Clean generated files
clean:
	rm -rf $(OUTPUT_DIR)
