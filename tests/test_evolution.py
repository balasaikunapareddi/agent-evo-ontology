from agent_evo_ontology.evolution import (
    EvolutionLoop,
    diagnose_failures,
    save_run_log,
)
from agent_evo_ontology.ontology import lookup_term
from agent_evo_ontology.questions import split_questions


def test_diagnose_maps_each_dev_failure_to_one_patch(questions):
    dev = split_questions(questions, "dev")
    # Simulate the v0 dev failures: d1..d6 fail, d7/d8 pass.
    failures = [q for q in dev if q.id in ("d1", "d2", "d3", "d4", "d5", "d6")]
    proposals = diagnose_failures(failures)
    ids = [p.id for p in proposals]
    assert ids == [
        "fix-revenue-mapping",
        "add-web-alias",
        "fix-best-seller-mapping",
        "fix-active-customer-definition",
        "fix-avg-order-value-mapping",
        "add-orders-payments-relationship",
        "add-shopper-alias",
    ]


def test_evolution_keeps_three_and_rejects_four(db_path, questions, v0):
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")
    loop = EvolutionLoop(db_path, backend="stub")
    evolved, log = loop.run(v0, dev, validation)
    kept = [e.proposal_id for e in log if e.decision == "keep"]
    rejected = [e.proposal_id for e in log if e.decision == "reject"]
    assert kept == ["fix-revenue-mapping", "add-web-alias",
                    "fix-best-seller-mapping"]
    assert rejected == ["fix-active-customer-definition",
                        "fix-avg-order-value-mapping",
                        "add-orders-payments-relationship",
                        "add-shopper-alias"]
    assert evolved.version == "ontology_v3"


def test_neutral_shopper_patch_rejected(db_path, questions, v0):
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")
    _evolved, log = EvolutionLoop(db_path, backend="stub").run(v0, dev, validation)
    entry = next(e for e in log if e.proposal_id == "add-shopper-alias")
    assert entry.decision == "reject"
    assert entry.b == 0 and entry.c == 0


def test_evolved_layer_has_fixed_mappings(db_path, questions, v0):
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")
    evolved, _log = EvolutionLoop(db_path, backend="stub").run(v0, dev, validation)
    assert "/100" in lookup_term(evolved, "revenue").mapping
    assert "paid" in lookup_term(evolved, "revenue").mapping
    assert "web" in lookup_term(evolved, "web orders").aliases
    assert "SUM" in lookup_term(evolved, "best-selling product").mapping
    # Rejected patches really did not land.
    assert "90 days" in lookup_term(evolved, "active customer").definition
    assert "/100" not in (lookup_term(evolved, "average order value").mapping or "")


def test_annotation_flag_raised_for_newly_won(db_path, questions, v0):
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")
    _evolved, log = EvolutionLoop(db_path, backend="stub").run(v0, dev, validation)
    kept = [e for e in log if e.decision == "keep"]
    assert kept
    assert kept[0].newly_won  # revenue fix wins v1 and v2
    assert any("Wretblad" in flag for e in kept for flag in e.flags)
    assert any("gold SQL" in flag for e in kept for flag in e.flags)


def test_kept_log_entries_record_the_judged_parent(db_path, questions, v0):
    """Regression: the log used to record the post-keep layer as the
    parent (parent_version == candidate_version, "50% -> 50%") because
    parent_val was re-measured before the entry was appended."""
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")
    _evolved, log = EvolutionLoop(db_path, backend="stub").run(v0, dev, validation)
    kept = [e for e in log if e.decision == "keep"]
    assert [(e.parent_version, e.parent_accuracy,
             e.candidate_version, e.candidate_accuracy) for e in kept] == [
        ("ontology_v0", 0.25, "ontology_v1", 0.5),
        ("ontology_v1", 0.5, "ontology_v2", 0.75),
        ("ontology_v2", 0.75, "ontology_v3", 1.0),
    ]


def test_annotation_flag_shows_evaluation_time_sql(
        db_path, questions, v0, monkeypatch):
    """Regression: the flag used to re-answer after the keep, which
    re-rolls a live model — the SQL shown could differ from the SQL
    that actually won. The flag must show the SQL recorded during
    the candidate evaluation. The counting stub returns the real SQL
    for the first three calls per question, then 'SELECT 1': a flag
    re-answer (a 4th+ call) would show 'SELECT 1' under the old code.
    """
    from agent_evo_ontology.llm import StubBackend

    original = StubBackend.sql_for
    calls: dict[str, int] = {}

    @staticmethod
    def counting_sql_for(intent, question, lookups, relationships):
        n = calls.get(question, 0) + 1
        calls[question] = n
        if n > 3:
            return "SELECT 1"
        return original(intent, question, lookups, relationships)

    monkeypatch.setattr(StubBackend, "sql_for", counting_sql_for)
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")
    _evolved, log = EvolutionLoop(db_path, backend="stub").run(v0, dev, validation)
    kept = [e for e in log if e.decision == "keep"]
    assert kept, "revenue fix should still be kept under the counting stub"
    flag = next(f for e in kept for f in e.flags if f.startswith("v1:"))
    assert "SELECT 1" not in flag
    assert "SUM(o.total_cents)/100.0" in flag


def test_save_run_log_writes_json(tmp_path, db_path, questions, v0):
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")
    _evolved, log = EvolutionLoop(db_path, backend="stub").run(v0, dev, validation)
    path = save_run_log(log, tmp_path / "log.json")
    assert path.exists()
    assert len(log) == 7
