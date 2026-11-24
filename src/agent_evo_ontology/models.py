"""Pydantic models for agent-evo-ontology."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class OntologyTerm(BaseModel):
    """One business term in the ontology layer.

    ``mapping`` is the term's SQL meaning — how the agent should turn the
    term into SQL. ``aliases`` are other words that mean the same term
    (e.g. "web" -> the "web orders" term, which maps to channel='online').
    """

    name: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    mapping: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)


class Relationship(BaseModel):
    """A join path between two tables that the agent may use."""

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    join_on: str = Field(min_length=1)
    description: str = ""


class OntologyLayer(BaseModel):
    """A versioned ontology layer: the only schema the agent ever sees."""

    version: str = Field(min_length=1)
    terms: list[OntologyTerm] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)

    def term_names(self) -> list[str]:
        return [t.name for t in self.terms]


class Question(BaseModel):
    """One text-to-SQL question with verified gold SQL."""

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    gold_sql: str = Field(min_length=1)
    expected_rows: list[list[Any]]
    split: Literal["dev", "validation"]
    intent: str = "unknown"


class Proposal(BaseModel):
    """A candidate edit to the ontology layer."""

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    kind: Literal["fix_mapping", "add_alias", "fix_definition",
                  "add_relationship", "neutral"]
    term_name: Optional[str] = Field(default=None, validate_default=True)
    new_mapping: Optional[str] = None
    new_definition: Optional[str] = None
    alias_key: Optional[str] = None
    alias_value: Optional[str] = None
    relationship: Optional[Relationship] = None

    @field_validator("term_name")
    @classmethod
    def _term_required_unless_relationship(cls, v, info):
        if info.data.get("kind") in ("fix_mapping", "add_alias", "fix_definition") and not v:
            raise ValueError("term_name is required for this proposal kind")
        return v


class EvalResult(BaseModel):
    """Execution-accuracy result for one layer version on one split."""

    version: str
    split: str
    accuracy: float
    correct: int
    total: int
    per_question: dict[str, bool] = Field(default_factory=dict)


class EvolutionLogEntry(BaseModel):
    """One gate decision, kept in memory, printed, and saved to .runs/."""

    proposal_id: str
    description: str
    parent_version: str
    candidate_version: str
    parent_accuracy: float
    candidate_accuracy: float
    b: int
    c: int
    p_value: Optional[float] = None
    decision: Literal["keep", "reject"]
    reason: str
    newly_won: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
