# Default recipe: show available commands
_default:
    @echo ""
    @just --list
    @echo ""

# Show help information
help:
    @echo ""
    @clear
    @echo ""
    @printf "%b\n" "\033[0;34m=== minirag ===\033[0m"
    @echo ""
    @echo "Available commands:"
    @just --list
    @echo ""

# Initialize the development environment
[group('lifecycle')]
init:
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Initializing Development Environment ===\033[0m"
    mkdir -p reports/coverage
    mkdir -p reports/security
    mkdir -p reports/pyright
    mkdir -p reports/deptry
    mkdir -p scripts
    echo "Installing Python dependencies..."
    uv sync
    if [ ! -f config.yaml ]; then
        cp config.yaml.template config.yaml
        echo "Copied config.yaml.template to config.yaml"
    fi
    DATA_DIR=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['data']['data_dir'])")
    MODEL_NAME=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['index']['embeddings']['model_name'])")
    for dir in "${DATA_DIR}/models" "${DATA_DIR}/storage" "${DATA_DIR}/index"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            echo "Created directory: $dir"
        else
            echo "Directory already exists: $dir"
        fi
    done
    DEFAULT_CORPUS="test"
    for dir in "${DATA_DIR}/input/${DEFAULT_CORPUS}/md" "${DATA_DIR}/input/${DEFAULT_CORPUS}/txt"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            echo "Created directory: $dir"
        else
            echo "Directory already exists: $dir"
        fi
    done
    CORPORA=$(find "${DATA_DIR}/storage" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
    if [ -n "$CORPORA" ]; then
        echo ""
        echo "Existing corpora:"
        for corpus_dir in $CORPORA; do
            echo "  - $(basename "$corpus_dir")"
        done
    fi
    MODEL_PATH="${DATA_DIR}/models/${MODEL_NAME}"
    if [ ! -f "$MODEL_PATH" ]; then
        echo "Downloading FastText model..."
        MODEL_URL="https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.en.300.bin.gz"
        MODEL_TMP_GZ="${MODEL_PATH}.gz"
        if command -v wget >/dev/null 2>&1; then
            wget -O "$MODEL_TMP_GZ" "$MODEL_URL"
        elif command -v curl >/dev/null 2>&1; then
            curl -L "$MODEL_URL" -o "$MODEL_TMP_GZ"
        else
            echo "Neither wget nor curl is available"
            exit 1
        fi
        mkdir -p "${DATA_DIR}/models"
        gunzip -c "$MODEL_TMP_GZ" > "$MODEL_PATH"
        rm -f "$MODEL_TMP_GZ"
    else
        echo "FastText model already exists at ${MODEL_PATH}"
    fi
    printf "%b\n" "\033[0;32m✓ Development environment ready\033[0m"
    echo ""

# Start the mini-rag service
[group('lifecycle')]
start:
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Starting mini-rag Service ===\033[0m"
    SERVICE_HOST=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['host'])")
    SERVICE_PORT=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['port'])")
    if curl -fsS "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/health" >/dev/null 2>&1; then
        printf "%b\n" "\033[0;33m⚠ Service is already running on ${SERVICE_HOST}:${SERVICE_PORT}\033[0m"
        exit 1
    fi
    uv run src/main.py
    echo ""

# Stop the running service
[group('lifecycle')]
stop:
    #!/usr/bin/env bash
    set -e
    echo ""
    SERVICE_HOST=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['host'])")
    SERVICE_PORT=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['port'])")
    curl -sS -X POST "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/shutdown" -H "Content-Type: application/json"
    echo ""

# Check service status and show config
[group('lifecycle')]
status:
    #!/usr/bin/env bash
    set -e
    echo ""
    SERVICE_HOST=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['host'])")
    SERVICE_PORT=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['port'])")
    if curl -fsS "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/health" >/dev/null 2>&1; then
        curl -fsS "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/info" | uv run python -c "import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))"
    else
        echo "service is not running"
    fi
    echo ""

# Convert markdown files to plain text
[group('tools')]
md2txt:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Converting Markdown to Text ===\033[0m"
    @uv run scripts/md2txt.py
    @echo ""

# Destroy and re-ingest all .txt files into a corpus
[group('corpus')]
ingest corpus="":
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Ingesting Documents ===\033[0m"
    SERVICE_HOST=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['host'])")
    SERVICE_PORT=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['port'])")
    if ! curl -fsS "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/health" >/dev/null 2>&1; then
        printf "%b\n" "\033[0;31m✗ Service is not running. Start it first with: just start\033[0m"
        exit 1
    fi
    CORPUS="{{corpus}}"
    if [ -z "$CORPUS" ]; then
        printf "Enter corpus name: "
        read CORPUS
    fi
    uv run scripts/ingest.py --corpus "$CORPUS"
    echo ""

# Delete a corpus index and storage
[group('corpus')]
delete corpus="":
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Deleting Corpus ===\033[0m"
    SERVICE_HOST=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['host'])")
    SERVICE_PORT=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['port'])")
    if ! curl -fsS "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/health" >/dev/null 2>&1; then
        printf "%b\n" "\033[0;31m✗ Service is not running. Start it first with: just start\033[0m"
        exit 1
    fi
    CORPUS="{{corpus}}"
    if [ -z "$CORPUS" ]; then
        printf "Enter corpus name: "
        read CORPUS
    fi
    if ! echo "$CORPUS" | grep -qE '^[a-zA-Z][a-zA-Z0-9_-]*$'; then
        printf "%b\n" "\033[0;31m✗ Invalid corpus name: ${CORPUS}\033[0m"
        exit 1
    fi
    printf "Are you sure you want to delete corpus '%s'? [y/N] " "$CORPUS"
    read CONFIRM
    if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
        echo "Aborted."
        exit 0
    fi
    HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/corpus/${CORPUS}/index")
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        printf "%b\n" "\033[0;32m✓ Corpus '${CORPUS}' deleted\033[0m"
    else
        printf "%b\n" "\033[0;31m✗ Failed to delete corpus '${CORPUS}' (HTTP ${HTTP_CODE})\033[0m"
        exit 1
    fi
    echo ""

# Evaluate retrieval quality for a corpus
[group('corpus')]
evaluate corpus="":
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Evaluating Corpus ===\033[0m"
    SERVICE_HOST=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['host'])")
    SERVICE_PORT=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['port'])")
    if ! curl -fsS "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/health" >/dev/null 2>&1; then
        printf "%b\n" "\033[0;31m✗ Service is not running. Start it first with: just start\033[0m"
        exit 1
    fi
    CORPUS="{{corpus}}"
    if [ -z "$CORPUS" ]; then
        printf "Enter corpus name: "
        read CORPUS
    fi
    uv run scripts/evaluate.py --corpus "$CORPUS"
    echo ""

# Interactive search query loop for a corpus
[group('corpus')]
search corpus="":
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Interactive Search ===\033[0m"
    CORPUS="{{corpus}}"
    if [ -z "$CORPUS" ]; then
        printf "Enter corpus name: "
        read CORPUS
    fi
    uv run scripts/search.py --corpus "$CORPUS"
    echo ""

# Inspect document chunks across all stores for a corpus
[group('corpus')]
inspect corpus="" document_id="":
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Inspecting Document ===\033[0m"
    CORPUS="{{corpus}}"
    if [ -z "$CORPUS" ]; then
        printf "Enter corpus name: "
        read CORPUS
    fi
    DOC_ID="{{document_id}}"
    if [ -z "$DOC_ID" ]; then
        printf "Enter document ID: "
        read DOC_ID
    fi
    uv run scripts/export_chunks.py --corpus "$CORPUS" "$DOC_ID"
    echo ""

# Destroy the virtual environment
[group('lifecycle')]
destroy:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Destroying Virtual Environment ===\033[0m"
    @rm -rf .venv
    @printf "%b\n" "\033[0;32m✓ Virtual environment removed\033[0m"
    @echo ""

# Check code style and formatting (read-only)
[group('code quality')]
code-style:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Checking Code Style ===\033[0m"
    @uv run ruff check .
    @echo ""
    @uv run ruff format --check .
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Style checks passed\033[0m"
    @echo ""

# Auto-fix code style and formatting
[group('code quality')]
code-format:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Formatting Code ===\033[0m"
    @uv run ruff check . --fix
    @echo ""
    @uv run ruff format .
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Code formatted\033[0m"
    @echo ""

# Run static type checking with mypy
[group('code quality')]
code-typecheck:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running Type Checks ===\033[0m"
    @uv run mypy src/
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Type checks passed\033[0m"
    @echo ""

# Run strict type checking with Pyright (LSP-based)
[group('code quality')]
code-lspchecks:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running Pyright Type Checks ===\033[0m"
    @mkdir -p reports/pyright
    @uv run pyright --project pyrightconfig.json > reports/pyright/pyright.txt 2>&1 || true
    @uv run pyright --project pyrightconfig.json
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Pyright checks passed\033[0m"
    @echo "  Report: reports/pyright/pyright.txt"
    @echo ""

# Run security checks with bandit
[group('code quality')]
code-security:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running Security Checks ===\033[0m"
    @mkdir -p reports/security
    @uv run bandit -c pyproject.toml -r src -f txt -o reports/security/bandit.txt || true
    @uv run bandit -c pyproject.toml -r src
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Security checks passed\033[0m"
    @echo ""

# Check dependency hygiene with deptry
[group('code quality')]
code-deptry:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Checking Dependencies ===\033[0m"
    @mkdir -p reports/deptry
    @uv run deptry src
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Dependency checks passed\033[0m"
    @echo ""

# Generate code statistics with pygount
[group('code quality')]
code-stats:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Code Statistics ===\033[0m"
    @mkdir -p reports
    @uv run pygount src/ tests/ scripts/ *.md *.toml --suffix=py,md,txt,toml,yaml,yml --format=summary
    @echo ""
    @uv run pygount src/ tests/ scripts/ *.md *.toml --suffix=py,md,txt,toml,yaml,yml --format=summary > reports/code-stats.txt
    @printf "%b\n" "\033[0;32m✓ Report saved to reports/code-stats.txt\033[0m"
    @echo ""

# Check spelling in code and documentation
[group('code quality')]
code-spell:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Checking Spelling ===\033[0m"
    @uv run codespell src tests tests_integration tests_e2e tests_mcp scripts *.md *.toml
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Spelling checks passed\033[0m"
    @echo ""

# Scan dependencies for known vulnerabilities
[group('code quality')]
code-audit:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Scanning Dependencies for Vulnerabilities ===\033[0m"
    @uv run pip-audit
    @echo ""
    @printf "%b\n" "\033[0;32m✓ No known vulnerabilities found\033[0m"
    @echo ""

# Run Semgrep static analysis
[group('code quality')]
code-semgrep:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running Semgrep Static Analysis ===\033[0m"
    @uv run semgrep --config config/semgrep/ --error src
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Semgrep checks passed\033[0m"
    @echo ""

# Detect unused dead code
[group('code quality')]
code-deadcode:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Detecting Dead Code ===\033[0m"
    @uv run deadcode src tests tests_integration tests_e2e tests_mcp scripts
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Dead code checks passed\033[0m"
    @echo ""

# Run unit tests only (fast)
[group('testing')]
test:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running Unit Tests ===\033[0m"
    @uv run pytest tests/ -v
    @echo ""

# Run integration tests (in-process, requires FastText model)
[group('testing')]
test-integration:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running Integration Tests ===\033[0m"
    @uv run pytest tests_integration/ -v --timeout=300 -p no:randomly
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Integration tests passed\033[0m"
    @echo ""

# Run end-to-end lifecycle tests (starts service, ingests, evaluates)
[group('testing')]
test-e2e:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running End-to-End Tests ===\033[0m"
    @uv run pytest tests_e2e/ -v -s --timeout=30 -p no:randomly
    @echo ""
    @printf "%b\n" "\033[0;32m✓ End-to-end tests passed\033[0m"
    @echo ""

# Run MCP server end-to-end tests (requires Node.js)
[group('testing')]
test-mcp:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running MCP Tests ===\033[0m"
    @uv run pytest tests_mcp/ -v -s --timeout=60 -p no:randomly
    @echo ""
    @printf "%b\n" "\033[0;32m✓ MCP tests passed\033[0m"
    @echo ""

# Run unit tests with coverage report and threshold check
[group('testing')]
test-coverage: init
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running Unit Tests with Coverage ===\033[0m"
    @uv run pytest tests/ -v \
        --cov=src \
        --cov-report=html:reports/coverage/html \
        --cov-report=term \
        --cov-report=xml:reports/coverage/coverage.xml \
        --cov-fail-under=80
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Coverage threshold met\033[0m"
    @echo "  HTML: reports/coverage/html/index.html"
    @echo ""

# Run ALL validation checks (verbose)
[group('testing')]
ci:
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Running CI Checks ===\033[0m"
    echo ""
    just init
    just code-format
    just code-style
    just code-typecheck
    just code-security
    just code-deptry
    just code-spell
    just code-semgrep
    just code-deadcode
    just code-audit
    just test
    just test-integration
    just test-e2e
    just test-mcp
    just code-lspchecks
    echo ""
    printf "%b\n" "\033[0;32m✓ All CI checks passed\033[0m"
    echo ""

# Run ALL validation checks silently (only show output on errors)
[group('testing')]
ci-quiet:
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Running CI Checks (Quiet Mode) ===\033[0m"
    TMPFILE=$(mktemp)
    trap "rm -f $TMPFILE" EXIT

    just init > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Init failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Init passed\033[0m"

    just code-format > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Code-format failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Code-format passed\033[0m"

    just code-style > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Code-style failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Code-style passed\033[0m"

    just code-typecheck > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Code-typecheck failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Code-typecheck passed\033[0m"

    just code-security > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Code-security failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Code-security passed\033[0m"

    just code-deptry > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Code-deptry failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Code-deptry passed\033[0m"

    just code-spell > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Code-spell failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Code-spell passed\033[0m"

    just code-semgrep > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Code-semgrep failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Code-semgrep passed\033[0m"

    just code-deadcode > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Code-deadcode failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Code-deadcode passed\033[0m"

    just code-audit > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Code-audit failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Code-audit passed\033[0m"

    just test > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Test failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Test passed\033[0m"

    just test-integration > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Test-integration failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Test-integration passed\033[0m"

    just test-e2e > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Test-e2e failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Test-e2e passed\033[0m"

    just test-mcp > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Test-mcp failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Test-mcp passed\033[0m"

    just code-lspchecks > $TMPFILE 2>&1 || { printf "%b\n" "\033[0;31m✗ Code-lspchecks failed\033[0m"; cat $TMPFILE; exit 1; }
    printf "%b\n" "\033[0;32m✓ Code-lspchecks passed\033[0m"

    echo ""
    printf "%b\n" "\033[0;32m✓ All CI checks passed\033[0m"
    echo ""
