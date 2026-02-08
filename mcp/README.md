# minirag MCP Server

A lightweight [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes mini-rag's hybrid search as an MCP tool. Uses stdio transport.

## Prerequisites

- **Node.js 18+**
- **mini-rag service** running (see the [project README](../README.md))

## Install

```bash
cd mcp
npm install
```

## Run

```bash
npm start
```

By default the server connects to the mini-rag service at `http://127.0.0.1:7001`. Override with the `REST_BASE` environment variable:

```bash
REST_BASE=http://localhost:9000 npm start
```

## Tool

The server exposes a single tool:

### `search`

Search the mini-rag document index using hybrid search (dense + sparse).

| Parameter | Type    | Required | Default | Description                    |
|-----------|---------|----------|---------|--------------------------------|
| `query`   | string  | yes      |         | Search query text              |
| `top_k`   | integer | no       | 10      | Number of results to return    |

Before each search, the server checks the mini-rag health endpoint with a 3-second timeout. If the service is unreachable or unhealthy, the tool returns: "Search system is currently offline."

## MCP Client Configuration

Replace `/absolute/path/to/mcp/mini-rag.ts` with the actual path on your system in all examples below.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "minirag": {
      "command": "npx",
      "args": ["tsx", "/absolute/path/to/mcp/mini-rag.ts"]
    }
  }
}
```

Restart Claude Desktop to pick up the change.

### Claude Code (CLI)

Add to the global config at `~/.claude/settings.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "minirag": {
      "command": "npx",
      "args": ["tsx", "/absolute/path/to/mcp/mini-rag.ts"]
    }
  }
}
```

Or via the CLI:

```bash
claude mcp add --scope user minirag -- npx tsx /absolute/path/to/mcp/mini-rag.ts
```

### Codex CLI / Codex Desktop App

The CLI and desktop app share the same configuration. Edit `~/.codex/config.toml` (global) or `.codex/config.toml` (project-scoped):

```toml
[mcp_servers.minirag]
command = "npx"
args = ["tsx", "/absolute/path/to/mcp/mini-rag.ts"]
```

Or via the CLI:

```bash
codex mcp add minirag -- npx tsx /absolute/path/to/mcp/mini-rag.ts
```

To point at a non-default mini-rag host:

```toml
[mcp_servers.minirag]
command = "npx"
args = ["tsx", "/absolute/path/to/mcp/mini-rag.ts"]

[mcp_servers.minirag.env]
REST_BASE = "http://localhost:9000"
```

Verify in the Codex TUI with `/mcp`.

### Cursor

Edit `.cursor/mcp.json` in your project root (project-scoped) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "minirag": {
      "command": "npx",
      "args": ["tsx", "/absolute/path/to/mcp/mini-rag.ts"]
    }
  }
}
```

## Testing

Test interactively with the MCP Inspector:

```bash
npm run inspect
```

Test from the command line (service offline):

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search","arguments":{"query":"test"}}}\n' | timeout 10 npm start
```

Test with the mini-rag service running:

```bash
# Terminal 1
just start

# Terminal 2
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search","arguments":{"query":"example search","top_k":3}}}\n' | timeout 10 npm start
```
