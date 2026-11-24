import asyncio
import json
import os
import sys
from pathlib import Path

from agent_evo_ontology.mcp_server import OntologyClient
from agent_evo_ontology.ontology import build_initial_ontology

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"


def test_client_direct_lookup(v0):
    client = OntologyClient(v0)
    term = client.lookup_term("revenue")
    assert term is not None
    assert term.mapping == "SUM(orders.total_cents)"
    assert client.lookup_term("nope") is None


def test_client_direct_manifest(v0):
    client = OntologyClient(v0)
    manifest = client.get_manifest()
    assert manifest["version"] == "ontology_v0"
    assert "revenue" in manifest["terms"]


def test_client_direct_search_and_relationships(v0):
    client = OntologyClient(v0)
    assert "revenue" in client.search_ontology("revenue")
    pairs = {(r.source, r.target) for r in client.list_relationships()}
    assert ("orders", "customers") in pairs


def test_stdio_server_lookup_term():
    """Spawn the real stdio server subprocess and call lookup_term
    through a real MCP ClientSession."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def _run():
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "agent_evo_ontology.mcp_server"],
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "lookup_term", {"term": "revenue"})
                return result

    result = asyncio.run(_run())
    text = result.content[0].text
    payload = json.loads(text)
    assert payload["name"] == "revenue"
    assert payload["mapping"] == "SUM(orders.total_cents)"


def test_stdio_server_manifest():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def _run():
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "agent_evo_ontology.mcp_server"],
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("get_manifest", {})
                return result

    result = asyncio.run(_run())
    payload = json.loads(result.content[0].text)
    assert payload["version"] == "ontology_v0"
