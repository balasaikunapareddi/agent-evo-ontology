import pytest
from pydantic import ValidationError

from agent_evo_ontology.models import (
    EvalResult,
    EvolutionLogEntry,
    OntologyLayer,
    OntologyTerm,
    Proposal,
    Question,
    Relationship,
)


def test_bad_term_rejected_empty_name():
    with pytest.raises(ValidationError):
        OntologyTerm(name="", definition="x")


def test_bad_term_rejected_empty_definition():
    with pytest.raises(ValidationError):
        OntologyTerm(name="revenue", definition="")


def test_term_defaults():
    term = OntologyTerm(name="revenue", definition="Total sales.")
    assert term.mapping is None
    assert term.aliases == []


def test_proposal_requires_term_for_mapping_fix():
    with pytest.raises(ValidationError):
        Proposal(id="p1", description="x", kind="fix_mapping")


def test_proposal_relationship_kind_needs_no_term():
    proposal = Proposal(
        id="p2", description="x", kind="add_relationship",
        relationship=Relationship(source="orders", target="payments",
                                  join_on="orders.id = payments.order_id"))
    assert proposal.term_name is None


def test_question_split_must_be_dev_or_validation():
    with pytest.raises(ValidationError):
        Question(id="q", question="?", gold_sql="SELECT 1",
                 expected_rows=[[1]], split="test")


def test_layer_term_names():
    layer = OntologyLayer(version="ontology_v0", terms=[
        OntologyTerm(name="revenue", definition="Total sales.")])
    assert layer.term_names() == ["revenue"]


def test_eval_result_model():
    result = EvalResult(version="ontology_v0", split="dev", accuracy=0.5,
                        correct=4, total=8, per_question={"d1": True})
    assert result.accuracy == 0.5


def test_log_entry_model():
    entry = EvolutionLogEntry(
        proposal_id="fix-revenue-mapping", description="fix revenue",
        parent_version="ontology_v0", candidate_version="ontology_v1",
        parent_accuracy=0.25, candidate_accuracy=0.5, b=2, c=0,
        p_value=None, decision="keep", reason="margin fallback")
    assert entry.decision == "keep"
    assert entry.newly_won == []
