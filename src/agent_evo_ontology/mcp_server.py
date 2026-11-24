"""MCP server for the ontology layer (official MCP Python SDK, MCPServer).

Two ways to use it:
  * In-process: OntologyClient wraps an OntologyLayer and calls the
    same plain functions the tools call — this is what the agent uses.
  * Over stdio: `python -m agent_evo_ontology.mcp_server` exposes the
    same four tools (lookup_term, list_relationships, search_ontology,
    get_manifest) to any MCP client.

The tool logic lives in plain functions (ontology.py) so both paths
stay identical by construction.
"""
from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from .models import OntologyLayer, OntologyTerm, Relationship
from .ontology import (
    build_initial_ontology,
    get_manifest as _manifest,
    list_relationships as _relationships,
    lookup_term as _lookup,
    search_ontology as _search,
)

mcp = MCPServer("agent-evo-ontology")

# The layer this server process serves. A fresh process serves v0;
# the evolution loop works on in-process copies, not on this global.
_LAYER = build_initial_ontology()


class OntologyClient:
    """Direct (in-process) client: the agent's only view of the schema."""

    def __init__(self, layer: OntologyLayer):
        self.layer = layer

    def lookup_term(self, term: str) -> OntologyTerm | None:
        return _lookup(self.layer, term)

    def list_relationships(self) -> list[Relationship]:
        return _relationships(self.layer)

    def search_ontology(self, query: str) -> list[str]:
        return _search(self.layer, query)

    def get_manifest(self) -> dict:
        return _manifest(self.layer)


@mcp.tool()
def lookup_term(term: str) -> str:
    """Look up one business term in the ontology layer."""
    found = _lookup(_LAYER, term)
    if found is None:
        return json.dumps({"found": False, "term": term})
    return found.model_dump_json()


@mcp.tool()
def list_relationships() -> str:
    """List the join paths the ontology layer knows about."""
    return json.dumps([r.model_dump() for r in _relationships(_LAYER)])


@mcp.tool()
def search_ontology(query: str) -> str:
    """Search term names, definitions, mappings, and aliases."""
    return json.dumps({"matches": _search(_LAYER, query)})


@mcp.tool()
def get_manifest() -> str:
    """Return the session manifest: layer version + term inventory."""
    return json.dumps(_manifest(_LAYER))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
