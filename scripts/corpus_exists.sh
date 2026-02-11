#!/usr/bin/env bash
# Resolve and validate a corpus name.
#
# Usage: resolve_corpus.sh [corpus_name]
#
# If corpus_name is provided, validates it exists and prints it.
# If omitted, lists available corpora, prompts for input, then validates.
# Exits non-zero on invalid or missing corpus.

set -e

DATA_DIR=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['data']['data_dir'])")
CORPUS="${1:-}"

if [ -z "$CORPUS" ]; then
    INPUT_DIR="${DATA_DIR}/input"
    if [ -d "$INPUT_DIR" ]; then
        CORPORA=$(find "$INPUT_DIR" -mindepth 1 -maxdepth 1 -type d ! -name '.*' 2>/dev/null | sort)
        if [ -n "$CORPORA" ]; then
            echo "" >&2
            echo "Available corpora:" >&2
            for corpus_dir in $CORPORA; do
                name=$(basename "$corpus_dir")
                txt_dir="${corpus_dir}/txt"
                if [ -d "$txt_dir" ]; then
                    count=$(find "$txt_dir" -name '*.txt' -not -name '._*' 2>/dev/null | wc -l | tr -d ' ')
                    printf "  - %s (%s txt files)\n" "$name" "$count" >&2
                else
                    printf "  - %s (no txt/ directory)\n" "$name" >&2
                fi
            done
            echo "" >&2
        else
            echo "No corpora found in ${INPUT_DIR}" >&2
        fi
    else
        echo "Input directory not found: ${INPUT_DIR}" >&2
        exit 1
    fi
    printf "Enter corpus name: " >&2
    read CORPUS
fi

if [ -z "$CORPUS" ]; then
    printf "\033[0;31m✗ No corpus name provided\033[0m\n" >&2
    exit 1
fi

if ! echo "$CORPUS" | grep -qE '^[a-zA-Z][a-zA-Z0-9_-]*$'; then
    printf "\033[0;31m✗ Invalid corpus name: %s\033[0m\n" "$CORPUS" >&2
    exit 1
fi

if [ ! -d "${DATA_DIR}/input/${CORPUS}" ]; then
    printf "\033[0;31m✗ Corpus '%s' not found in %s/input/\033[0m\n" "$CORPUS" "$DATA_DIR" >&2
    exit 1
fi

echo "$CORPUS"
