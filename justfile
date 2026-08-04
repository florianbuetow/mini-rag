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
    @printf "%b\n" "\033[0;34mCorpus commands usage:\033[0m"
    @echo "  just ingest <corpus>              Ingest text files into a corpus"
    @echo "  just search <corpus>              Interactive search on a corpus"
    @echo "  just evaluate <corpus>            Evaluate retrieval quality"
    @echo "  just delete <corpus>              Delete a corpus index"
    @echo "  just citation <corpus> <key>...   Fetch citation metadata"
    @echo "  just inspect <corpus> <doc_id>    Inspect document chunks"
    @echo ""
    @echo "  If <corpus> is omitted, available corpora will be listed."
    @echo ""
    @printf "%b\n" "\033[0;34mExamples:\033[0m"
    @echo "  just ingest test"
    @echo "  just search llmevals"
    @echo "  just citation test my_doc_key"
    @echo "  just inspect test 1"
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

# Start the mini-rag service (logs to logs/minirag.log)
[group('lifecycle')]
start:
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Starting mini-rag Service ===\033[0m"
    SERVICE_HOST=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['host'])")
    SERVICE_PORT=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['port'])")
    if curl -fsS "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/health" >/dev/null 2>&1; then
        printf "%b\n" "\033[0;33m⚠ Service is already running on ${SERVICE_HOST}:${SERVICE_PORT} — stopping it first\033[0m"
        curl -sS -X POST "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/shutdown" -H "Content-Type: application/json" >/dev/null 2>&1 || true
        # Wait for the port to be released
        for i in $(seq 1 30); do
            if ! curl -fsS "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/health" >/dev/null 2>&1; then
                break
            fi
            sleep 0.5
        done
        if curl -fsS "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/health" >/dev/null 2>&1; then
            printf "%b\n" "\033[0;31m✗ Failed to stop existing service\033[0m"
            exit 1
        fi
        printf "%b\n" "\033[0;32m✓ Previous instance stopped\033[0m"
    fi
    mkdir -p logs
    LOGFILE="logs/minirag.log"
    printf "%b\n" "\033[0;32m✓ Logging to ${LOGFILE}\033[0m"
    echo ""
    uv run src/main.py 2>&1 | tee "$LOGFILE"

# Stop the running service
[group('lifecycle')]
stop-service:
    #!/usr/bin/env bash
    set -e
    echo ""
    SERVICE_HOST=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['host'])")
    SERVICE_PORT=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['port'])")
    curl -sS -X POST "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/shutdown" -H "Content-Type: application/json"
    echo ""

# Check service status and show the UI and API endpoints
[group('lifecycle')]
status:
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== mini-rag Status ===\033[0m"
    echo ""
    SERVICE_HOST=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['host'])")
    SERVICE_PORT=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['port'])")
    BASE_URL="http://${SERVICE_HOST}:${SERVICE_PORT}"
    if curl -fsS "${BASE_URL}/v1/health" >/dev/null 2>&1; then
        RUNNING=1
        STATUS_LABEL="\033[0;32m✓ UP\033[0m"
    else
        RUNNING=0
        STATUS_LABEL="\033[0;31m✗ DOWN\033[0m"
    fi
    printf "  %-10s %b\n" "Service:" "$STATUS_LABEL"
    printf "  %-10s %s\n" "Host:" "${SERVICE_HOST}"
    printf "  %-10s %s\n" "Port:" "${SERVICE_PORT}"
    echo ""
    if [ "$RUNNING" -eq 1 ]; then
        printf "  %-10s %s\n" "Chat UI:" "${BASE_URL}/"
        printf "  %-10s %s\n" "API docs:" "${BASE_URL}/docs"
        printf "  %-10s %s\n" "OpenAPI:" "${BASE_URL}/openapi.json"
        printf "  %-10s %s\n" "Health:" "${BASE_URL}/v1/health"
    else
        printf "%b\n" "\033[0;33m⚠ Service is not running. Start it with: just start\033[0m"
    fi
    echo ""

# Print MCP server configuration instructions for Claude Code, Claude Desktop, Codex, and Cursor
[group('lifecycle')]
mcp-help:
    #!/usr/bin/env bash
    MCP_PATH="$(pwd)/mcp/mini-rag.ts"
    echo ""
    printf "%b\n" "\033[0;34m=== minirag MCP Server Configuration ===\033[0m"
    echo ""
    echo "MCP server script: ${MCP_PATH}"
    echo "Prerequisites:     Node.js 18+, mini-rag service running (just start)"
    echo ""
    printf "%b\n" "\033[0;34mClaude Code (CLI)\033[0m"
    echo ""
    echo "  claude mcp add --scope user minirag -- npx tsx ${MCP_PATH}"
    echo ""
    echo "  Or add to ~/.claude/settings.json:"
    echo '  {'
    echo '    "mcpServers": {'
    echo '      "minirag": {'
    echo '        "command": "npx",'
    printf '        "args": ["tsx", "%s"]\n' "${MCP_PATH}"
    echo '      }'
    echo '    }'
    echo '  }'
    echo ""
    printf "%b\n" "\033[0;34mClaude Desktop\033[0m"
    echo ""
    echo "  Edit ~/Library/Application Support/Claude/claude_desktop_config.json:"
    echo '  {'
    echo '    "mcpServers": {'
    echo '      "minirag": {'
    echo '        "command": "npx",'
    printf '        "args": ["tsx", "%s"]\n' "${MCP_PATH}"
    echo '      }'
    echo '    }'
    echo '  }'
    echo "  Then restart Claude Desktop."
    echo ""
    printf "%b\n" "\033[0;34mCodex CLI / Codex Desktop\033[0m"
    echo ""
    echo "  codex mcp add minirag -- npx tsx ${MCP_PATH}"
    echo ""
    echo "  Or edit ~/.codex/config.toml:"
    echo '  [mcp_servers.minirag]'
    echo '  command = "npx"'
    printf '  args = ["tsx", "%s"]\n' "${MCP_PATH}"
    echo ""
    printf "%b\n" "\033[0;34mCursor\033[0m"
    echo ""
    echo "  Edit .cursor/mcp.json (project) or ~/.cursor/mcp.json (global):"
    echo '  {'
    echo '    "mcpServers": {'
    echo '      "minirag": {'
    echo '        "command": "npx",'
    printf '        "args": ["tsx", "%s"]\n' "${MCP_PATH}"
    echo '      }'
    echo '    }'
    echo '  }'
    echo ""
    printf "%b\n" "\033[0;34mCustom service URL\033[0m"
    echo ""
    echo "  Set REST_BASE to point at a non-default host, e.g.:"
    echo "  REST_BASE=http://localhost:9000 npm start   (from the mcp/ directory)"
    echo ""

# Convert markdown files to plain text
[group('tools')]
md2txt:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Converting Markdown to Text ===\033[0m"
    @uv run scripts/md2txt.py
    @echo ""

# Convert PDF files to plain text using LiteParse
[group('tools')]
pdf2txt:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Converting PDFs to Text ===\033[0m"
    @uv run scripts/pdf2txt.py
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
    CORPUS=$(./scripts/corpus_exists.sh "{{corpus}}")
    printf "Full ingest destroys the existing index and ledger for corpus '%s' before re-ingesting. Continue? [y/N] " "$CORPUS"
    read CONFIRM
    if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
        echo "Aborted."
        exit 0
    fi
    uv run scripts/ingest.py --corpus "$CORPUS"
    echo ""

# Incrementally index only new .txt files into a corpus (skips already-indexed)
[group('corpus')]
update corpus="":
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Updating Index (incremental) ===\033[0m"
    SERVICE_HOST=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['host'])")
    SERVICE_PORT=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['service']['port'])")
    if ! curl -fsS "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/health" >/dev/null 2>&1; then
        printf "%b\n" "\033[0;31m✗ Service is not running. Start it first with: just start\033[0m"
        exit 1
    fi
    CORPUS=$(./scripts/corpus_exists.sh "{{corpus}}")
    uv run scripts/ingest.py --corpus "$CORPUS" --update
    echo ""

# Request a clean stop for all ingests or one corpus
[group('corpus')]
stop corpus="":
    #!/usr/bin/env bash
    set -e
    DATA_DIR=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['data']['data_dir'])")
    if [ -z "{{corpus}}" ]; then
        STOP_PATH="${DATA_DIR}/STOP"
    else
        CORPUS=$(./scripts/corpus_exists.sh "{{corpus}}")
        STOP_PATH="${DATA_DIR}/storage/${CORPUS}/STOP"
    fi
    mkdir -p "$(dirname "$STOP_PATH")"
    : > "$STOP_PATH"
    echo "STOP written: $STOP_PATH"

# Remove a clean-stop request for all ingests or one corpus
[group('corpus')]
resume corpus="":
    #!/usr/bin/env bash
    set -e
    DATA_DIR=$(uv run python -c "import yaml; print(yaml.safe_load(open('config.yaml', encoding='utf-8'))['data']['data_dir'])")
    if [ -z "{{corpus}}" ]; then
        STOP_PATH="${DATA_DIR}/STOP"
    else
        CORPUS=$(./scripts/corpus_exists.sh "{{corpus}}")
        STOP_PATH="${DATA_DIR}/storage/${CORPUS}/STOP"
    fi
    if [ -f "$STOP_PATH" ]; then
        rm "$STOP_PATH"
        echo "STOP removed: $STOP_PATH"
    else
        echo "No STOP file present: $STOP_PATH"
    fi

# Seed the ingestion ledger from an already-indexed corpus without re-indexing (one-time migration)
[group('corpus')]
backfill-ledger corpus="":
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Backfilling Ingestion Ledger ===\033[0m"
    CORPUS=$(./scripts/corpus_exists.sh "{{corpus}}")
    uv run scripts/backfill_ledger.py --corpus "$CORPUS"
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
    CORPUS=$(./scripts/corpus_exists.sh "{{corpus}}")
    printf "Are you sure you want to delete corpus '%s'? [y/N] " "$CORPUS"
    read CONFIRM
    if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
        echo "Aborted."
        exit 0
    fi
    HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE "http://${SERVICE_HOST}:${SERVICE_PORT}/v1/corpus/${CORPUS}/index")
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        uv run python -m minirag.ingestion.ledger --corpus "$CORPUS" --clear
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
    CORPUS=$(./scripts/corpus_exists.sh "{{corpus}}")
    uv run scripts/evaluate.py --corpus "$CORPUS"
    echo ""

# Interactive search query loop for a corpus
[group('corpus')]
search corpus="":
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Interactive Search ===\033[0m"
    CORPUS=$(./scripts/corpus_exists.sh "{{corpus}}")
    uv run scripts/search.py --corpus "$CORPUS"
    echo ""

# Fetch citation metadata for one or more citation keys
[group('corpus')]
citation corpus +keys:
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Citation Lookup ===\033[0m"
    CORPUS=$(./scripts/corpus_exists.sh "{{corpus}}")
    uv run scripts/citation.py --corpus "$CORPUS" --keys-file - <<'MINIRAG_KEYS'
    {{keys}}
    MINIRAG_KEYS
    echo ""

# Inspect document chunks across all stores for a corpus
[group('corpus')]
inspect corpus="" document_id="":
    #!/usr/bin/env bash
    set -e
    echo ""
    printf "%b\n" "\033[0;34m=== Inspecting Document ===\033[0m"
    CORPUS=$(./scripts/corpus_exists.sh "{{corpus}}")
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
    @# GHSA-rrmf-rvhw-rf47 (CVE-2025-3000): torch <=2.12.0 torch.jit.script memory
    @# corruption, local-only, has NO patched release upstream, so it cannot be fixed
    @# by upgrading and is ignored here. All other flagged vulns are patched via
    @# override-dependencies in pyproject.toml.
    @uv run pip-audit --ignore-vuln GHSA-rrmf-rvhw-rf47
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

# Run end-to-end lifecycle tests (excludes real-RAG tests that need LM Studio)
[group('testing')]
test-e2e:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running End-to-End Tests ===\033[0m"
    @uv run pytest tests_e2e/ -v -s -x --timeout=120 -p no:randomly -m "not rag"
    @echo ""
    @printf "%b\n" "\033[0;32m✓ End-to-end tests passed\033[0m"
    @echo ""

# Run real-RAG end-to-end tests (requires running service, LM Studio, and seeded corpora)
[group('testing')]
test-e2e-rag:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running Real-RAG End-to-End Tests ===\033[0m"
    @uv run pytest tests_e2e/ -v -s -x --timeout=240 -p no:randomly -m "rag"
    @echo ""
    @printf "%b\n" "\033[0;32m✓ Real-RAG end-to-end tests passed\033[0m"
    @echo ""

# Run MCP server end-to-end tests (requires Node.js)
[group('testing')]
test-mcp:
    @echo ""
    @printf "%b\n" "\033[0;34m=== Running MCP Tests ===\033[0m"
    @uv run pytest tests_mcp/ -v -s --timeout=180 -p no:randomly
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
