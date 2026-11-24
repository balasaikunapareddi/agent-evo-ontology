"""The versioned ontology layer: build it, look things up, patch it.

The layer is deliberately imperfect at v0 — that is the point. It was
built from the schema and the seed docs, and several of its mappings
are wrong in exactly the ways a first-pass semantic layer is wrong:
cents mistaken for dollars, a missing alias, a count where a sum
belongs, a recency proxy for a behavioural definition, and a missing
join. The evolution loop (evolution.py) fixes what the paired gate
lets through and nothing else.
"""
from __future__ import annotations

import copy

from .models import OntologyLayer, OntologyTerm, Proposal, Relationship

CORRECT_REVENUE_MAPPING = (
    "SUM(orders.total_cents)/100.0 joined to payments "
    "with payments.status='paid'"
)
CORRECT_BEST_SELLER_MAPPING = "product with the highest SUM(order_items.qty)"
CORRECT_ACTIVE_DEFINITION = "a customer with at least one paid order"
CORRECT_AVG_MAPPING = "AVG(orders.total_cents)/100.0 over paid orders"


def build_initial_ontology() -> OntologyLayer:
    """Build ontology v0 from the schema + seed docs (deliberately imperfect)."""
    terms = [
        OntologyTerm(
            name="revenue",
            definition="Total sales revenue.",
            # WRONG: cents, and no paid-only filter.
            mapping="SUM(orders.total_cents)",
        ),
        OntologyTerm(
            name="web orders",
            definition="Orders placed on the website.",
            mapping="orders with channel='web'",
            # NOTE: the alias "web" -> channel 'online' is MISSING.
            aliases=[],
        ),
        OntologyTerm(
            name="best-selling product",
            definition="The product that sells the most.",
            # WRONG: most orders (COUNT), not most units (SUM qty).
            mapping="product with the most orders (COUNT)",
        ),
        OntologyTerm(
            name="active customer",
            # WRONG: recency proxy, not behaviour.
            definition="A customer who signed up in the last 90 days.",
            mapping="customers with signup_date in the last 90 days",
        ),
        OntologyTerm(
            name="average order value",
            definition="The average value of an order.",
            # WRONG: missing /100.
            mapping="AVG(orders.total_cents)",
        ),
        OntologyTerm(name="customer", definition="A person who shops with us.",
                     mapping="customers table"),
        OntologyTerm(name="order", definition="A purchase placed by a customer.",
                     mapping="orders table"),
        OntologyTerm(name="product", definition="An item the shop sells.",
                     mapping="products table"),
        OntologyTerm(name="payment", definition="A payment for an order.",
                     mapping="payments table"),
        OntologyTerm(name="total orders", definition="The number of orders.",
                     mapping="COUNT(orders)"),
        OntologyTerm(name="VIP customer", definition="A very important customer.",
                     mapping="customers with is_vip=1"),
        OntologyTerm(name="discontinued product",
                     definition="A product the shop no longer sells.",
                     mapping="products with discontinued=1"),
    ]
    # NOTE: the orders -> payments relationship is MISSING at v0.
    relationships = [
        Relationship(source="orders", target="customers",
                     join_on="orders.customer_id = customers.id",
                     description="Each order belongs to one customer."),
        Relationship(source="order_items", target="orders",
                     join_on="order_items.order_id = orders.id",
                     description="Each order item belongs to one order."),
        Relationship(source="order_items", target="products",
                     join_on="order_items.product_id = products.id",
                     description="Each order item is one product."),
    ]
    return OntologyLayer(version="ontology_v0", terms=terms,
                         relationships=relationships)


def build_empty_ontology() -> OntologyLayer:
    """The no-ontology baseline: the agent sees no terms at all."""
    return OntologyLayer(version="no-ontology", terms=[], relationships=[])


def lookup_term(layer: OntologyLayer, term: str) -> OntologyTerm | None:
    """Find a term by name or alias (case-insensitive). Plain function,
    shared by the in-process client and the MCP server tools."""
    needle = term.strip().lower()
    for t in layer.terms:
        if t.name.lower() == needle:
            return t
        if any(a.lower() == needle for a in t.aliases):
            return t
    return None


def search_ontology(layer: OntologyLayer, query: str) -> list[str]:
    """Return the names of terms whose name, definition, or aliases
    contain the query (case-insensitive substring)."""
    needle = query.strip().lower()
    hits = []
    for t in layer.terms:
        hay = " ".join([t.name, t.definition, t.mapping or ""] + t.aliases).lower()
        if needle in hay:
            hits.append(t.name)
    return hits


def list_relationships(layer: OntologyLayer) -> list[Relationship]:
    return list(layer.relationships)


def get_manifest(layer: OntologyLayer) -> dict:
    """Session manifest: version + term inventory, as the MCP tool returns."""
    return {
        "version": layer.version,
        "terms": [t.name for t in layer.terms],
        "relationships": [
            f"{r.source} -> {r.target} ON {r.join_on}"
            for r in layer.relationships
        ],
    }


def copy_layer(layer: OntologyLayer) -> OntologyLayer:
    return copy.deepcopy(layer)


def apply_proposal(layer: OntologyLayer, proposal: Proposal) -> OntologyLayer:
    """Apply *proposal* to a COPY of *layer* and return the copy.
    The copy keeps the parent's version; the evolution loop assigns
    the new version number when (and only when) the gate keeps it."""
    new = copy.deepcopy(layer)
    if proposal.kind == "fix_mapping" and proposal.term_name:
        term = lookup_term(new, proposal.term_name)
        if term is not None and proposal.new_mapping is not None:
            term.mapping = proposal.new_mapping
    elif proposal.kind == "fix_definition" and proposal.term_name:
        term = lookup_term(new, proposal.term_name)
        if term is not None and proposal.new_definition is not None:
            term.definition = proposal.new_definition
            if proposal.new_mapping is not None:
                term.mapping = proposal.new_mapping
    elif proposal.kind == "add_alias" and proposal.term_name:
        term = lookup_term(new, proposal.term_name)
        if term is not None and proposal.alias_key:
            if proposal.alias_key not in term.aliases:
                term.aliases.append(proposal.alias_key)
            if proposal.alias_value:
                # The alias records the real channel value, e.g. "web" -> "online".
                term.mapping = term.mapping.replace(
                    "channel='web'", f"channel='{proposal.alias_value}'"
                ) if term.mapping else term.mapping
    elif proposal.kind == "add_relationship" and proposal.relationship is not None:
        if not any(r.source == proposal.relationship.source
                   and r.target == proposal.relationship.target
                   for r in new.relationships):
            new.relationships.append(proposal.relationship)
    # kind == "neutral": deliberately changes nothing the agent can use.
    return new
