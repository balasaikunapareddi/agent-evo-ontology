"""Live test: run the real-LLM loop end to end via LiteLLM.

Reads LLM_MODEL (default gemini/gemini-3.5-flash-lite). If no API key
is set, it falls back to the stub and says so — the demo already
covers the stub path, so this script is for the real-model check.

Must not crash on Gemini 503: a ServiceUnavailableError is caught,
the blocked step is printed plainly, and the script exits non-zero
with an honest message. Report goes to
.runs/live/attempt-N/report.json (N = next free integer).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_evo_ontology.agent import TextToSqlAgent  # noqa: E402
from agent_evo_ontology.demo import RUNS_DIR  # noqa: E402
from agent_evo_ontology.evolution import EvolutionLoop  # noqa: E402
from agent_evo_ontology.mcp_server import OntologyClient  # noqa: E402
from agent_evo_ontology.ontology import (  # noqa: E402
    build_empty_ontology,
    build_initial_ontology,
)
from agent_evo_ontology.questions import (  # noqa: E402
    REPO_ROOT,
    load_questions,
    split_questions,
)
from agent_evo_ontology.store import build_db  # noqa: E402

LIVE_DIR = REPO_ROOT / ".runs" / "live"


def next_attempt_dir() -> Path:
    n = 1
    while (LIVE_DIR / f"attempt-{n}").exists():
        n += 1
    path = LIVE_DIR / f"attempt-{n}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def main() -> int:
    model = os.environ.get("LLM_MODEL", "gemini/gemini-3.5-flash-lite")
    has_key = bool(os.environ.get("GEMINI_API_KEY")
                   or os.environ.get("LLM_API_KEY"))
    backend = "llm" if has_key else "stub"
    if not has_key:
        print("NOTE: no GEMINI_API_KEY (or LLM_API_KEY) set — running in "
              "stub mode. Set the key to run the real-Gemini loop.")
    else:
        print(f"Live test with model {model}")

    attempt_dir = next_attempt_dir()
    db_path = attempt_dir / "harbor-pine.db"
    build_db(db_path)
    questions = load_questions()
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")

    report: dict = {"model": model, "backend": backend, "versions": {}}
    try:
        no_agent = TextToSqlAgent(OntologyClient(build_empty_ontology()),
                                  db_path, backend=backend, model=model)
        v0_agent = TextToSqlAgent(OntologyClient(build_initial_ontology()),
                                  db_path, backend=backend, model=model)
        report["versions"]["no-ontology"] = no_agent.evaluate(questions).model_dump()
        report["versions"]["initial"] = v0_agent.evaluate(questions).model_dump()

        loop = EvolutionLoop(db_path, backend=backend, model=model)
        evolved, log = loop.run(build_initial_ontology(), dev, validation)
        evo_agent = TextToSqlAgent(OntologyClient(evolved), db_path,
                                   backend=backend, model=model)
        report["versions"]["evolved"] = evo_agent.evaluate(questions).model_dump()
        report["versions"]["evolved_version"] = evolved.version
        report["log"] = [entry.model_dump() for entry in log]
    except Exception as exc:  # noqa: BLE001 - report the block honestly
        from litellm.exceptions import RateLimitError, ServiceUnavailableError

        if isinstance(exc, (ServiceUnavailableError, RateLimitError)):
            kind = ("503 (ServiceUnavailableError)" if isinstance(
                exc, ServiceUnavailableError) else "429 (RateLimitError)")
            print(f"BLOCKED by Gemini {kind} during the live run: {exc}")
            print("Live test did not complete — the model endpoint was "
                  "unavailable or rate-limited. Retry when Gemini calms down.")
            report["blocked"] = f"{type(exc).__name__}: {exc}"
            with open(attempt_dir / "report.json", "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            return 1
        raise

    for name, result in report["versions"].items():
        if isinstance(result, dict) and "correct" in result:
            print(f"  {name}: {result['correct']}/{result['total']} "
                  f"({result['accuracy']:.1%})")
    print("Gate decisions:")
    for entry in report["log"]:
        print(f"  [{entry['decision'].upper()}] {entry['proposal_id']}: "
              f"{entry['parent_accuracy']:.0%} -> "
              f"{entry['candidate_accuracy']:.0%} "
              f"(b={entry['b']}, c={entry['c']}) — {entry['reason']}")
        for flag in entry["flags"]:
            print(f"      {flag}")
    with open(attempt_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to {attempt_dir / 'report.json'}")
    _ = RUNS_DIR
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
