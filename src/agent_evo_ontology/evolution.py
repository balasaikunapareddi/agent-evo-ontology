"""The evolution loop: Build -> Use -> Evolve -> Evaluate -> Publish-or-reject.

Evaluate the parent layer on the dev set, collect failures, diagnose
each failure with small deterministic rules mapping the failure's
intent to one candidate patch (deduped), then for each candidate:
apply it to a COPY of the layer, run a PAIRED evaluation parent vs
candidate on the VALIDATION split only, and let the gate
(gate.py) decide keep/reject. A candidate is published — the layer
version bumps — only when the paired evaluation shows a reproducible
improvement over its parent.
"""
from __future__ import annotations

import json
from pathlib import Path

from .agent import TextToSqlAgent, classify_intent
from .gate import decide_gate
from .mcp_server import OntologyClient
from .models import (
    EvolutionLogEntry,
    OntologyLayer,
    Proposal,
    Question,
    Relationship,
)
from .ontology import (
    CORRECT_ACTIVE_DEFINITION,
    CORRECT_AVG_MAPPING,
    CORRECT_BEST_SELLER_MAPPING,
    CORRECT_REVENUE_MAPPING,
    apply_proposal,
    copy_layer,
)

REVIEW_NOTE = (
    "REVIEW: check gold query — could be a learned annotation error "
    "(cf. Wretblad et al, arXiv 2402.12243: 20.7% of BIRD financial dev "
    "gold SQL wrong). In this fictional dataset gold is verified by "
    "construction (tests assert every gold SQL returns its expected "
    "rows), so this flag is precautionary."
)

# intent -> candidate patch. One patch per failure type, deduped.
PATCHES: dict[str, Proposal] = {
    "revenue": Proposal(
        id="fix-revenue-mapping",
        description="Fix revenue mapping: SUM(total_cents)/100.0 over paid orders only",
        kind="fix_mapping", term_name="revenue",
        new_mapping=CORRECT_REVENUE_MAPPING),
    "web_orders": Proposal(
        id="add-web-alias",
        description="Add alias 'web' -> channel 'online' for web orders",
        kind="add_alias", term_name="web orders",
        alias_key="web", alias_value="online"),
    "best_seller": Proposal(
        id="fix-best-seller-mapping",
        description="Fix best-seller mapping: highest SUM(order_items.qty), not most orders",
        kind="fix_mapping", term_name="best-selling product",
        new_mapping=CORRECT_BEST_SELLER_MAPPING),
    "active_customers": Proposal(
        id="fix-active-customer-definition",
        description="Fix active-customer definition: >=1 paid order, not signed up in last 90 days",
        kind="fix_definition", term_name="active customer",
        new_definition=CORRECT_ACTIVE_DEFINITION,
        new_mapping="customers with at least one paid order"),
    "avg_order_value": Proposal(
        id="fix-avg-order-value-mapping",
        description="Fix average-order-value mapping: AVG(total_cents)/100.0 over paid orders",
        kind="fix_mapping", term_name="average order value",
        new_mapping=CORRECT_AVG_MAPPING),
    "top_customer": Proposal(
        id="add-orders-payments-relationship",
        description="Add relationship orders -> payments on order_id",
        kind="add_relationship",
        relationship=Relationship(
            source="orders", target="payments",
            join_on="orders.id = payments.order_id",
            description="Each order has one payment.")),
}

NEUTRAL_PATCH = Proposal(
    id="add-shopper-alias",
    description="Add alias 'shopper' -> customer (neutral: changes nothing the agent uses)",
    kind="neutral", term_name="customer",
    alias_key="shopper", alias_value="customer")


def diagnose_failures(dev_failures: list[Question]) -> list[Proposal]:
    """Map each dev failure's intent to its candidate patch (deduped),
    then append the deliberately neutral patch so the gate has
    something to reject honestly."""
    seen: set[str] = set()
    proposals: list[Proposal] = []
    for q in dev_failures:
        intent = q.intent or classify_intent(q.question)
        if intent in PATCHES and intent not in seen:
            seen.add(intent)
            proposals.append(PATCHES[intent])
    proposals.append(NEUTRAL_PATCH)
    return proposals


class EvolutionLoop:
    """Runs the Evolve -> Evaluate -> Publish-or-reject cycle."""

    def __init__(self, db_path: str | Path, backend: str = "stub",
                 model: str | None = None):
        self.db_path = str(db_path)
        self.backend = backend
        self.model = model

    def _agent_for(self, layer: OntologyLayer) -> TextToSqlAgent:
        return TextToSqlAgent(OntologyClient(layer), self.db_path,
                              backend=self.backend, model=self.model)

    def run(self, parent: OntologyLayer, dev: list[Question],
            validation: list[Question]) -> tuple[OntologyLayer, list[EvolutionLogEntry]]:
        current = copy_layer(parent)
        version_n = 0
        try:
            version_n = int(current.version.rsplit("v", 1)[1])
        except (IndexError, ValueError):
            version_n = 0
        log: list[EvolutionLogEntry] = []

        parent_eval = self._agent_for(current).evaluate(dev)
        dev_failures = [q for q in dev if not parent_eval.per_question.get(q.id, False)]
        proposals = diagnose_failures(dev_failures)

        # The parent validation result is computed once per layer
        # version and reused across proposals — re-evaluating the same
        # layer would only re-roll the same (non-deterministic) model
        # and burn rate-limit budget. It is recomputed after a keep,
        # when the layer actually changes.
        parent_val = self._agent_for(current).evaluate(validation)
        for proposal in proposals:
            candidate = apply_proposal(current, proposal)
            cand_val = self._agent_for(candidate).evaluate(validation)
            b = sum(1 for q in validation
                    if not parent_val.per_question.get(q.id, False)
                    and cand_val.per_question.get(q.id, False))
            c = sum(1 for q in validation
                    if parent_val.per_question.get(q.id, False)
                    and not cand_val.per_question.get(q.id, False))
            decision, reason, p = decide_gate(
                b, c, parent_val.accuracy, cand_val.accuracy)
            # Snapshot the parent the gate actually judged. Below, a
            # keep re-measures parent_val against the NEW layer, so
            # these must be recorded before that reassignment —
            # otherwise the log claims parent and candidate were the
            # same version at the same accuracy (e.g. "50% -> 50%").
            log_parent_version = current.version
            log_parent_accuracy = parent_val.accuracy
            newly_won = [q.id for q in validation
                         if not parent_val.per_question.get(q.id, False)
                         and cand_val.per_question.get(q.id, False)]
            flags: list[str] = []
            if decision == "keep":
                version_n += 1
                candidate.version = f"ontology_v{version_n}"
                current = candidate
                # Layer changed: the parent baseline must be re-measured
                # before the next candidate is judged against it.
                parent_val = self._agent_for(current).evaluate(validation)
                # Annotation-error flag: every newly-won validation
                # question gets its gold SQL printed next to the
                # agent's SQL for review. The agent SQL is the one
                # recorded during the candidate evaluation itself —
                # re-answering here would re-roll a live model and
                # could show a different (possibly wrong) SQL next to
                # a question the candidate actually won.
                for q in validation:
                    if q.id in newly_won:
                        agent_sql = cand_val.sql_by_question.get(q.id, "")
                        flags.append(
                            f"{q.id}: agent SQL: {agent_sql} | "
                            f"gold SQL: {q.gold_sql} | {REVIEW_NOTE}")
            log.append(EvolutionLogEntry(
                proposal_id=proposal.id,
                description=proposal.description,
                parent_version=log_parent_version,
                candidate_version=candidate.version,
                parent_accuracy=log_parent_accuracy,
                candidate_accuracy=cand_val.accuracy,
                b=b, c=c, p_value=p,
                decision=decision, reason=reason,
                newly_won=newly_won if decision == "keep" else [],
                flags=flags,
            ))
        return current, log


def save_run_log(log: list[EvolutionLogEntry], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([entry.model_dump() for entry in log], f, indent=2)
    return path
