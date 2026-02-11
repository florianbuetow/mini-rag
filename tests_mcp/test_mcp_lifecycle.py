"""MCP server end-to-end lifecycle tests.

Exercises the full MCP tool lifecycle through JSON-RPC over stdio:
1. Verify tool listing.
2. Search with results.
3. Get citation for a known key.
4. Get citation for an unknown key.
5. Delete corpus via API.
6. Verify search returns empty after deletion.
7. Verify citation returns not-found after deletion.
"""

import json

import httpx

from tests_mcp.conftest import McpEnv


class TestMcpLifecycle:
    """Ordered MCP lifecycle tests — run with -p no:randomly."""

    def test_01_tools_list(self, mcp_env: McpEnv) -> None:
        tools = mcp_env.mcp_client.list_tools()
        tool_names = [t["name"] for t in tools]
        assert "search" in tool_names, f"Expected 'search' in {tool_names}"
        assert "get_citation" in tool_names, f"Expected 'get_citation' in {tool_names}"

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    def test_02_search_returns_results(self, mcp_env: McpEnv) -> None:
        result = mcp_env.mcp_client.call_tool(
            "search",
            {"corpus": mcp_env.corpus, "query": "quantum computing", "top_k": 5},
        )
        assert "isError" not in result or result["isError"] is not True

        content = result["content"]
        assert len(content) > 0
        data = json.loads(content[0]["text"])
        results = data["data"]["results"]
        assert len(results) > 0, "Expected search results after ingest"

        for item in results:
            assert "document_id" in item
            assert "citation_key" in item
            assert "text" in item
            assert "score" in item

    def test_03_get_citation_returns_data(self, mcp_env: McpEnv) -> None:
        search_result = mcp_env.mcp_client.call_tool(
            "search",
            {"corpus": mcp_env.corpus, "query": "quantum computing", "top_k": 1},
        )
        search_data = json.loads(search_result["content"][0]["text"])
        citation_key = search_data["data"]["results"][0]["citation_key"]

        citation_result = mcp_env.mcp_client.call_tool(
            "get_citation",
            {"corpus": mcp_env.corpus, "citation_key": citation_key},
        )
        assert "isError" not in citation_result or citation_result["isError"] is not True

        citation_data = json.loads(citation_result["content"][0]["text"])
        assert citation_data["data"]["citation_key"] == citation_key
        assert "source_type" in citation_data["data"]

    def test_04_get_citation_unknown_key(self, mcp_env: McpEnv) -> None:
        result = mcp_env.mcp_client.call_tool(
            "get_citation",
            {"corpus": mcp_env.corpus, "citation_key": "nonexistent"},
        )
        text = result["content"][0]["text"]
        assert "No citation found" in text
        assert result.get("isError") is not True

    def test_05_delete_corpus_via_api(self, mcp_env: McpEnv) -> None:
        resp = httpx.delete(
            f"{mcp_env.base_url}/v1/corpus/{mcp_env.corpus}/index",
            timeout=30.0,
        )
        assert resp.status_code == 200

    def test_06_search_after_delete_returns_empty(self, mcp_env: McpEnv) -> None:
        result = mcp_env.mcp_client.call_tool(
            "search",
            {"corpus": mcp_env.corpus, "query": "quantum computing", "top_k": 5},
        )
        content = result["content"]
        assert len(content) > 0
        data = json.loads(content[0]["text"])
        results = data["data"]["results"]
        assert len(results) == 0, f"Expected empty results after delete, got {len(results)}"

    def test_07_citation_after_delete(self, mcp_env: McpEnv) -> None:
        result = mcp_env.mcp_client.call_tool(
            "get_citation",
            {"corpus": mcp_env.corpus, "citation_key": "any_key"},
        )
        text = result["content"][0]["text"]
        assert "No citation found" in text
