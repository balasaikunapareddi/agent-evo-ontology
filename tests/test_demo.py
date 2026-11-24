from agent_evo_ontology.demo import run_demo


def test_demo_runs_and_prints_all_three_versions(capsys):
    result = run_demo()
    out = capsys.readouterr().out
    assert "no-ontology" in out
    assert "initial (v0)" in out
    assert "evolved (ontology_v3)" in out
    assert "KEPT" in out
    assert "REJECTED" in out
    assert result["no_ontology"]["overall"]["correct"] == 3
    assert result["initial"]["overall"]["correct"] == 4
    assert result["evolved"]["overall"]["correct"] == 13
    assert result["no_ontology"]["validation"]["correct"] == 2
    assert result["initial"]["validation"]["correct"] == 2
    assert result["evolved"]["validation"]["correct"] == 8
    assert result["evolved"]["version"] == "ontology_v3"
    kept = [e for e in result["log"] if e["decision"] == "keep"]
    assert len(kept) == 3


def test_demo_log_has_seven_entries():
    result = run_demo()
    assert len(result["log"]) == 7
