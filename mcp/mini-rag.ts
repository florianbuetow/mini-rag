import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const REST_BASE = process.env.REST_BASE ?? "http://127.0.0.1:9191";
const HEALTH_TIMEOUT_MS = 3000;
const REQUEST_TIMEOUT_MS = 5000;
const MAX_ERROR_BODY_CHARS = 400;

function parseJsonBody(text: string): unknown {
  if (text.trim() === "") {
    return null;
  }
  return JSON.parse(text);
}

function extractErrorMessage(text: string, status: number): string {
  if (text.trim() === "") {
    return `HTTP ${status}`;
  }
  try {
    const parsed = JSON.parse(text) as { error?: unknown };
    if (typeof parsed?.error === "string") {
      return parsed.error;
    }
  } catch {
    return text.slice(0, MAX_ERROR_BODY_CHARS);
  }
  return `HTTP ${status}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const server = new McpServer({
  name: "minirag",
  version: "0.1.0",
});

server.tool(
  "search",
  "Search a mini-rag corpus using hybrid search (dense + sparse)",
  {
    corpus: z.string().regex(/^[a-zA-Z][a-zA-Z0-9_-]*$/, "must start with a letter, then alphanumeric, underscore, or dash").describe("Name of the corpus to search"),
    query: z.string().describe("Search query text"),
    top_k: z.number().int().positive().default(10).describe("Number of results to return"),
  },
  async ({ corpus, query, top_k }) => {
    console.error(`[minirag] search: corpus=${corpus} query="${query}" top_k=${top_k}`);
    try {
      const healthResponse = await fetch(`${REST_BASE}/v1/health`, {
        signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
      });
      if (!healthResponse.ok) {
        return { content: [{ type: "text", text: `Search system health check failed: HTTP ${healthResponse.status}` }], isError: true };
      }
      const healthBodyText = await healthResponse.text();
      const healthData = parseJsonBody(healthBodyText) as { data?: { status?: string } } | null;
      if (healthData?.data?.status !== "healthy") {
        return { content: [{ type: "text", text: "Search system is currently offline." }], isError: true };
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Search system is unreachable: ${detail}` }], isError: true };
    }

    try {
      const response = await fetch(`${REST_BASE}/v1/corpus/${encodeURIComponent(corpus)}/query/hybrid`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k }),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      const bodyText = await response.text();
      if (!response.ok) {
        const errorMsg = extractErrorMessage(bodyText, response.status);
        return { content: [{ type: "text", text: `Search failed: ${errorMsg}` }], isError: true };
      }
      try {
        const data = parseJsonBody(bodyText);
        return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        return { content: [{ type: "text", text: `Search failed to parse JSON response: ${detail}` }], isError: true };
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Error: ${message}` }], isError: true };
    }
  },
);

server.tool(
  "get_citation",
  "Get citation/source metadata for a document by its citation key",
  {
    corpus: z.string().regex(/^[a-zA-Z][a-zA-Z0-9_-]*$/, "must start with a letter, then alphanumeric, underscore, or dash").describe("Name of the corpus"),
    citation_key: z.string().describe("Citation key from search results"),
  },
  async ({ corpus, citation_key }) => {
    console.error(`[minirag] get_citation: corpus=${corpus} citation_key="${citation_key}"`);
    try {
      const healthResponse = await fetch(`${REST_BASE}/v1/health`, {
        signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
      });
      if (!healthResponse.ok) {
        return { content: [{ type: "text", text: `Search system health check failed: HTTP ${healthResponse.status}` }], isError: true };
      }
      const healthBodyText = await healthResponse.text();
      const healthData = parseJsonBody(healthBodyText) as { data?: { status?: string } } | null;
      if (healthData?.data?.status !== "healthy") {
        return { content: [{ type: "text", text: "Search system is currently offline." }], isError: true };
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Search system is unreachable: ${detail}` }], isError: true };
    }

    try {
      const response = await fetch(`${REST_BASE}/v1/corpus/${encodeURIComponent(corpus)}/citation/${encodeURIComponent(citation_key)}`, {
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      const bodyText = await response.text();
      if (response.status === 404) {
        return { content: [{ type: "text", text: `No citation found for key: ${citation_key}` }], isError: true };
      }
      if (!response.ok) {
        const errorMsg = extractErrorMessage(bodyText, response.status);
        return { content: [{ type: "text", text: `Citation lookup failed: ${errorMsg}` }], isError: true };
      }
      try {
        const data = parseJsonBody(bodyText);
        return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        return { content: [{ type: "text", text: `Citation lookup failed to parse JSON response: ${detail}` }], isError: true };
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Error: ${message}` }], isError: true };
    }
  },
);

server.tool(
  "get_chunk",
  "Get a chunk with its source provenance (source file path, char span, line range) by chunk ID from search results",
  {
    corpus: z.string().regex(/^[a-zA-Z][a-zA-Z0-9_-]*$/, "must start with a letter, then alphanumeric, underscore, or dash").describe("Name of the corpus"),
    chunk_id: z.number().int().positive().describe("Chunk ID from search results"),
  },
  async ({ corpus, chunk_id }) => {
    console.error(`[minirag] get_chunk: corpus=${corpus} chunk_id=${chunk_id}`);
    try {
      const healthResponse = await fetch(`${REST_BASE}/v1/health`, {
        signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
      });
      if (!healthResponse.ok) {
        return { content: [{ type: "text", text: `Search system health check failed: HTTP ${healthResponse.status}` }], isError: true };
      }
      const healthBodyText = await healthResponse.text();
      const healthData = parseJsonBody(healthBodyText) as { data?: { status?: string } } | null;
      if (healthData?.data?.status !== "healthy") {
        return { content: [{ type: "text", text: "Search system is currently offline." }], isError: true };
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Search system is unreachable: ${detail}` }], isError: true };
    }

    try {
      const response = await fetch(`${REST_BASE}/v1/corpus/${encodeURIComponent(corpus)}/chunk/${chunk_id}`, {
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      const bodyText = await response.text();
      if (!response.ok) {
        const errorMsg = extractErrorMessage(bodyText, response.status);
        return { content: [{ type: "text", text: `Chunk lookup failed: ${errorMsg}` }], isError: true };
      }
      try {
        const data = parseJsonBody(bodyText);
        return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        return { content: [{ type: "text", text: `Chunk lookup failed to parse JSON response: ${detail}` }], isError: true };
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Error: ${message}` }], isError: true };
    }
  },
);

server.tool(
  "get_chunk_source",
  "Get the exact original text slice a chunk was created from, read from the corpus input folder, by chunk ID",
  {
    corpus: z.string().regex(/^[a-zA-Z][a-zA-Z0-9_-]*$/, "must start with a letter, then alphanumeric, underscore, or dash").describe("Name of the corpus"),
    chunk_id: z.number().int().positive().describe("Chunk ID from search results"),
  },
  async ({ corpus, chunk_id }) => {
    console.error(`[minirag] get_chunk_source: corpus=${corpus} chunk_id=${chunk_id}`);
    try {
      const healthResponse = await fetch(`${REST_BASE}/v1/health`, {
        signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
      });
      if (!healthResponse.ok) {
        return { content: [{ type: "text", text: `Search system health check failed: HTTP ${healthResponse.status}` }], isError: true };
      }
      const healthBodyText = await healthResponse.text();
      const healthData = parseJsonBody(healthBodyText) as { data?: { status?: string } } | null;
      if (healthData?.data?.status !== "healthy") {
        return { content: [{ type: "text", text: "Search system is currently offline." }], isError: true };
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Search system is unreachable: ${detail}` }], isError: true };
    }

    try {
      const response = await fetch(`${REST_BASE}/v1/corpus/${encodeURIComponent(corpus)}/chunk/${chunk_id}/source`, {
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      const bodyText = await response.text();
      if (!response.ok) {
        const errorMsg = extractErrorMessage(bodyText, response.status);
        return { content: [{ type: "text", text: `Chunk source lookup failed: ${errorMsg}` }], isError: true };
      }
      try {
        const data = parseJsonBody(bodyText);
        return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        return { content: [{ type: "text", text: `Chunk source lookup failed to parse JSON response: ${detail}` }], isError: true };
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Error: ${message}` }], isError: true };
    }
  },
);

server.tool(
  "list_corpora",
  "List all available corpora that can be searched",
  {},
  async () => {
    console.error("[minirag] list_corpora");
    try {
      const healthResponse = await fetch(`${REST_BASE}/v1/health`, {
        signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
      });
      if (!healthResponse.ok) {
        return { content: [{ type: "text", text: `Search system health check failed: HTTP ${healthResponse.status}` }], isError: true };
      }
      const healthBodyText = await healthResponse.text();
      const healthData = parseJsonBody(healthBodyText) as { data?: { status?: string } } | null;
      if (healthData?.data?.status !== "healthy") {
        return { content: [{ type: "text", text: "Search system is currently offline." }], isError: true };
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Search system is unreachable: ${detail}` }], isError: true };
    }

    try {
      const response = await fetch(`${REST_BASE}/v1/corpora`, {
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      const bodyText = await response.text();
      if (!response.ok) {
        const errorMsg = extractErrorMessage(bodyText, response.status);
        return { content: [{ type: "text", text: `Failed to list corpora: ${errorMsg}` }], isError: true };
      }
      let data: unknown = null;
      try {
        data = parseJsonBody(bodyText);
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        return { content: [{ type: "text", text: `Failed to parse corpora response: ${detail}` }], isError: true };
      }

      if (!isRecord(data) || !isRecord(data.data)) {
        return { content: [{ type: "text", text: "Invalid corpora response: expected response envelope with data object" }], isError: true };
      }

      const corpora = data.data.corpora;
      const descriptions = data.data.descriptions;
      if (!Array.isArray(corpora) || !corpora.every((name) => typeof name === "string")) {
        return { content: [{ type: "text", text: "Invalid corpora response: expected data.corpora to be a string array" }], isError: true };
      }
      if (!isRecord(descriptions)) {
        return { content: [{ type: "text", text: "Invalid corpora response: expected data.descriptions to be an object" }], isError: true };
      }
      for (const corpus of corpora) {
        if (typeof descriptions[corpus] !== "string") {
          return { content: [{ type: "text", text: `Invalid corpora response: missing string description for corpus ${corpus}` }], isError: true };
        }
      }

      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Error: ${message}` }], isError: true };
    }
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
