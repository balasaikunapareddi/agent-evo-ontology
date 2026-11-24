import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from agent_evo_ontology.ontology import build_initial_ontology  # noqa: E402
from agent_evo_ontology.questions import load_questions  # noqa: E402
from agent_evo_ontology.store import build_db  # noqa: E402


@pytest.fixture()
def db_path(tmp_path):
    return build_db(tmp_path / "harbor-pine.db")


@pytest.fixture()
def questions():
    return load_questions()


@pytest.fixture()
def v0():
    return build_initial_ontology()
