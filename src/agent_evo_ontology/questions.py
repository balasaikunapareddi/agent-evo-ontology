"""Load the 16 text-to-SQL questions from data/questions.json."""
from __future__ import annotations

import json
from pathlib import Path

from .models import Question

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO_ROOT / "data" / "questions.json"


def load_questions(path: str | Path = DEFAULT_PATH) -> list[Question]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [Question(**item) for item in raw]


def split_questions(questions: list[Question], split: str) -> list[Question]:
    return [q for q in questions if q.split == split]
