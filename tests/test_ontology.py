from agent_evo_ontology.models import Proposal
from agent_evo_ontology.ontology import (
    apply_proposal,
    build_empty_ontology,
    build_initial_ontology,
    copy_layer,
    get_manifest,
    list_relationships,
    lookup_term,
    search_ontology,
)


def test_v0_has_the_deliberately_wrong_revenue_mapping(v0):
    term = lookup_term(v0, "revenue")
    assert term is not None
    assert term.mapping == "SUM(orders.total_cents)"


def test_v0_web_orders_alias_missing(v0):
    term = lookup_term(v0, "web orders")
    assert term is not None
    assert term.aliases == []
    assert "'online'" not in (term.mapping or "")


def test_v0_best_seller_uses_count(v0):
    term = lookup_term(v0, "best-selling product")
    assert "COUNT" in (term.mapping or "")


def test_v0_active_customer_is_recency_proxy(v0):
    term = lookup_term(v0, "active customer")
    assert "90 days" in term.definition


def test_v0_avg_missing_division(v0):
    term = lookup_term(v0, "average order value")
    assert "/100" not in (term.mapping or "")


def test_v0_missing_orders_payments_relationship(v0):
    pairs = {(r.source, r.target) for r in list_relationships(v0)}
    assert ("orders", "payments") not in pairs
    assert ("orders", "customers") in pairs


def test_v0_correct_terms_present(v0):
    for name in ["customer", "order", "product", "payment", "total orders",
                 "VIP customer", "discontinued product"]:
        assert lookup_term(v0, name) is not None, name


def test_lookup_is_case_insensitive_and_alias_aware(v0):
    assert lookup_term(v0, "REVENUE") is not None
    assert lookup_term(v0, "no such term") is None


def test_search_ontology(v0):
    hits = search_ontology(v0, "revenue")
    assert "revenue" in hits
    assert search_ontology(v0, "zzz-no-match") == []


def test_manifest_lists_version_and_terms(v0):
    manifest = get_manifest(v0)
    assert manifest["version"] == "ontology_v0"
    assert "revenue" in manifest["terms"]
    assert len(manifest["relationships"]) == 3


def test_apply_proposal_does_not_mutate_parent(v0):
    proposal = Proposal(id="p", description="fix revenue", kind="fix_mapping",
                        term_name="revenue", new_mapping="SUM(x)/100.0")
    new = apply_proposal(v0, proposal)
    assert lookup_term(new, "revenue").mapping == "SUM(x)/100.0"
    assert lookup_term(v0, "revenue").mapping == "SUM(orders.total_cents)"


def test_apply_alias_fix(v0):
    proposal = Proposal(id="p", description="web alias", kind="add_alias",
                        term_name="web orders", alias_key="web",
                        alias_value="online")
    new = apply_proposal(v0, proposal)
    assert "web" in lookup_term(new, "web orders").aliases
    assert "'online'" in lookup_term(new, "web orders").mapping
    assert lookup_term(new, "web") is not None  # alias resolves


def test_copy_layer_is_independent(v0):
    copied = copy_layer(v0)
    copied.terms[0].mapping = "CHANGED"
    assert lookup_term(v0, "revenue").mapping == "SUM(orders.total_cents)"


def test_empty_ontology_has_no_terms():
    layer = build_empty_ontology()
    assert layer.terms == []
    assert lookup_term(layer, "revenue") is None
