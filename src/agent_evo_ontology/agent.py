"""The text-to-SQL agent.

TextToSqlAgent answers a question by (1) looking terms up through the
ontology (MCP tools, in-process), (2) turning the lookups into SQL —
via the deterministic stub, or via a real LLM through LiteLLM — and
(3) executing the SQL against SQLite.

The agent NEVER sees the raw schema. It takes an OntologyClient, not
the DB schema; the DB handle is only used to execute SQL. The only
schema knowledge it can use is what the ontology tools returned.
"""
from __future__ import annotations

from pathlib import Path

from .llm import LiteLLMBackend, StubBackend, backend_for_env, extract_sql
from .models import EvalResult, Question
from .prompts import SYSTEM_PROMPT
from .store import execute_sql, rows_match

# Which ontology terms each intent needs to look up first.
INTENT_TERMS: dict[str, list[str]] = {
    "revenue": ["revenue"],
    "web_orders": ["web orders"],
    "best_seller": ["best-selling product"],
    "active_customers": ["active customer"],
    "avg_order_value": ["average order value"],
    "top_customer": [],
    "vip_customers": ["VIP customer"],
    "discontinued_products": ["discontinued product"],
    "discontinued_buyers": ["VIP customer", "discontinued product"],
    "count_customers": [],
    "total_orders": [],
    "orders_in_period": [],
    "list_products": [],
}


def classify_intent(question: str) -> str:
    """Small keyword classifier. The question text is the only input;
    gold SQL and question ids are never consulted."""
    q = question.lower()
    if "revenue" in q:
        return "revenue"
    if "web order" in q:
        return "web_orders"
    if "best-selling" in q or "most units" in q:
        return "best_seller"
    if "active customer" in q:
        return "active_customers"
    if "average order value" in q:
        return "avg_order_value"
    if "top customer" in q:
        return "top_customer"
    if "discontinued" in q and "customer" in q:
        return "discontinued_buyers"
    if "discontinued" in q:
        return "discontinued_products"
    if "vip" in q:
        return "vip_customers"
    if "how many customers" in q:
        return "count_customers"
    if "orders were placed" in q:
        return "orders_in_period"
    if "how many orders" in q:
        return "total_orders"
    if "list" in q and "product" in q:
        return "list_products"
    return "unknown"


class TextToSqlAgent:
    """Question -> ontology lookups -> SQL -> executed rows."""

    def __init__(self, client, db_path: str | Path,
                 backend: str | None = None, model: str | None = None):
        self.client = client  # OntologyClient: the agent's only schema view
        self.db_path = str(db_path)
        self.backend = backend or backend_for_env()
        self._llm = LiteLLMBackend(model) if self.backend == "llm" else None

    def generate_sql(self, question: str) -> str:
        intent = classify_intent(question)
        term_names = INTENT_TERMS.get(intent, [])
        lookups = {name: self.client.lookup_term(name) for name in term_names}
        if self.backend == "stub":
            relationships = self.client.list_relationships()
            return StubBackend.sql_for(intent, question, lookups, relationships)
        # Real LLM: ontology lookup results go into the prompt; the
        # model never sees the raw schema.
        context_lines = []
        for name, term in lookups.items():
            if term is None:
                context_lines.append(f"- {name}: NOT IN ONTOLOGY")
            else:
                context_lines.append(
                    f"- {name}: {term.definition} Mapping: {term.mapping} "
                    f"Aliases: {', '.join(term.aliases) or 'none'}")
        rels = self.client.list_relationships()
        context_lines.append("Relationships: " + "; ".join(
            f"{r.source} -> {r.target} ON {r.join_on}" for r in rels))
        prompt = SYSTEM_PROMPT.format(
            ontology_context="\n".join(context_lines), question=question)
        return extract_sql(self._llm.generate(prompt))

    def answer(self, question: str) -> tuple[str, list[tuple]]:
        """Return (sql, rows) for *question*."""
        sql = self.generate_sql(question)
        rows = execute_sql(self.db_path, sql)
        return sql, rows

    def evaluate(self, questions: list[Question]) -> EvalResult:
        """Execution accuracy (BIRD-style EX) over *questions*."""
        per_question: dict[str, bool] = {}
        correct = 0
        for q in questions:
            _sql, rows = self.answer(q.question)
            ok = rows_match(rows, [tuple(r) for r in q.expected_rows])
            per_question[q.id] = ok
            correct += int(ok)
        total = len(questions)
        return EvalResult(
            version=self.client.layer.version,
            split=questions[0].split if questions else "",
            accuracy=(correct / total) if total else 0.0,
            correct=correct,
            total=total,
            per_question=per_question,
        )
