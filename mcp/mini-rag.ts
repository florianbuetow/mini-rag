import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const REST_BASE = process.env.REST_BASE ?? "http://127.0.0.1:7001";
const HEALTH_TIMEOUT_MS = 3000;
const REQUEST_TIMEOUT_MS = 5000;

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
    try {
      const healthResponse = await fetch(`${REST_BASE}/v1/health`, {
        signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
      });
      const healthData = (await healthResponse.json()) as { data?: { status?: string } };
      if (healthData.data?.status !== "healthy") {
        return { content: [{ type: "text", text: "Search system is currently offline." }], isError: true };
      }
    } catch {
      return { content: [{ type: "text", text: "Search system is currently offline." }], isError: true };
    }

    try {
      const response = await fetch(`${REST_BASE}/v1/corpus/${encodeURIComponent(corpus)}/query/hybrid`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k }),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      const data = await response.json();
      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
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
    try {
      const healthResponse = await fetch(`${REST_BASE}/v1/health`, {
        signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
      });
      const healthData = (await healthResponse.json()) as { data?: { status?: string } };
      if (healthData.data?.status !== "healthy") {
        return { content: [{ type: "text", text: "Search system is currently offline." }], isError: true };
      }
    } catch {
      return { content: [{ type: "text", text: "Search system is currently offline." }], isError: true };
    }

    try {
      const response = await fetch(`${REST_BASE}/v1/corpus/${encodeURIComponent(corpus)}/citation/${encodeURIComponent(citation_key)}`, {
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      if (response.status === 404) {
        return { content: [{ type: "text", text: `No citation found for key: ${citation_key}` }] };
      }
      const data = await response.json();
      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Error: ${message}` }], isError: true };
    }
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
