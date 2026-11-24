"""One-command demo: no-ontology vs initial vs evolved, same 16 questions.

`python -m agent_evo_ontology demo` — works with no API key (stub).
"""
from __future__ import annotations

from pathlib import Path

from .agent import TextToSqlAgent
from .evolution import EvolutionLoop, save_run_log
from .mcp_server import OntologyClient
from .models import EvalResult
from .ontology import build_empty_ontology, build_initial_ontology
from .questions import REPO_ROOT, load_questions, split_questions
from .store import build_db

RUNS_DIR = REPO_ROOT / ".runs" / "demo"


def _fmt(result: EvalResult) -> str:
    return f"{result.correct}/{result.total} ({result.accuracy:.1%})"


def run_demo(backend: str = "stub", model: str | None = None) -> dict:
    """Run the three versions side by side; return the numbers."""
    db_path = RUNS_DIR / "harbor-pine.db"
    build_db(db_path)
    questions = load_questions()
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")

    no_layer = build_empty_ontology()
    v0 = build_initial_ontology()
    no_agent = TextToSqlAgent(OntologyClient(no_layer), db_path, backend=backend, model=model)
    v0_agent = TextToSqlAgent(OntologyClient(v0), db_path, backend=backend, model=model)
    no_all = no_agent.evaluate(questions)
    no_val = no_agent.evaluate(validation)
    v0_all = v0_agent.evaluate(questions)
    v0_val = v0_agent.evaluate(validation)

    loop = EvolutionLoop(db_path, backend=backend, model=model)
    evolved, log = loop.run(v0, dev, validation)
    evo_agent = TextToSqlAgent(OntologyClient(evolved), db_path, backend=backend, model=model)
    evo_all = evo_agent.evaluate(questions)
    evo_val = evo_agent.evaluate(validation)
    save_run_log(log, RUNS_DIR / "evolution-log.json")

    print("agent-evo-ontology — demo (stub agent, same 16 questions)")
    print(f"  no-ontology      overall {_fmt(no_all)}   validation {_fmt(no_val)}")
    print(f"  initial (v0)     overall {_fmt(v0_all)}   validation {_fmt(v0_val)}")
    print(f"  evolved ({evolved.version})  overall {_fmt(evo_all)}   validation {_fmt(evo_val)}")
    print()
    print("Evolution log (paired gate on the validation split only):")
    for entry in log:
        mark = "KEPT    " if entry.decision == "keep" else "REJECTED"
        p = f", p={entry.p_value:.4f}" if entry.p_value is not None else ""
        print(f"  [{mark}] {entry.proposal_id}: "
              f"{entry.parent_accuracy:.0%} -> {entry.candidate_accuracy:.0%} "
              f"(b={entry.b}, c={entry.c}{p}) — {entry.reason}")
        for flag in entry.flags:
            print(f"          {flag}")
    print()
    print(f"Evolution log saved to {RUNS_DIR / 'evolution-log.json'}")
    return {
        "no_ontology": {"overall": no_all.model_dump(),
                        "validation": no_val.model_dump()},
        "initial": {"overall": v0_all.model_dump(),
                    "validation": v0_val.model_dump()},
        "evolved": {"overall": evo_all.model_dump(),
                    "validation": evo_val.model_dump(),
                    "version": evolved.version},
        "log": [entry.model_dump() for entry in log],
    }


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()
