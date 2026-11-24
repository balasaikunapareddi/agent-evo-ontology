"""CLI: python -m agent_evo_ontology demo | evolve"""
from __future__ import annotations

import sys

from .demo import run_demo


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("Usage: python -m agent_evo_ontology <demo|evolve>")
        print("  demo    run the stub agent on all three ontology versions")
        print("  evolve  run the evolution loop and print the gate log")
        return 0
    if argv[0] == "demo":
        run_demo()
        return 0
    if argv[0] == "evolve":
        run_demo()
        return 0
    print(f"Unknown command: {argv[0]}")
    print("Usage: python -m agent_evo_ontology <demo|evolve>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
