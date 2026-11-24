import pytest

from agent_evo_ontology.gate import decide_gate, mcnemar_p_value


def test_mcnemar_b8_c0_significant():
    p = mcnemar_p_value(8, 0)
    assert p == pytest.approx(0.0078, abs=0.0001)


def test_mcnemar_b7_c1_not_significant():
    p = mcnemar_p_value(7, 1)
    assert p == pytest.approx(0.0703, abs=0.0001)


def test_mcnemar_b9_c1_significant():
    p = mcnemar_p_value(9, 1)
    assert p == pytest.approx(0.0215, abs=0.0001)


def test_mcnemar_no_discordant_pairs_is_one():
    assert mcnemar_p_value(0, 0) == 1.0


def test_gate_mcnemar_path_keeps():
    decision, _reason, p = decide_gate(10, 0, 0.5, 0.9)
    assert decision == "keep"
    assert p is not None and p < 0.05


def test_gate_mcnemar_path_rejects_weak():
    decision, _reason, p = decide_gate(8, 2, 0.5, 0.6)
    assert decision == "reject"
    assert p is not None and p > 0.05


def test_margin_fallback_b3_c0_keeps():
    decision, _reason, p = decide_gate(3, 0, 0.25, 0.625)
    assert decision == "keep"
    assert p is None


def test_margin_fallback_b2_c1_rejects():
    decision, _reason, _p = decide_gate(2, 1, 0.25, 0.375)
    assert decision == "reject"


def test_margin_fallback_b1_c1_rejects():
    decision, _reason, _p = decide_gate(1, 1, 0.5, 0.5)
    assert decision == "reject"


def test_margin_fallback_b0_c0_rejects():
    decision, _reason, _p = decide_gate(0, 0, 0.5, 0.5)
    assert decision == "reject"


def test_margin_fallback_needs_higher_accuracy():
    # b-c = 2 but candidate accuracy did not improve: reject.
    decision, _reason, _p = decide_gate(2, 0, 0.5, 0.5)
    assert decision == "reject"
