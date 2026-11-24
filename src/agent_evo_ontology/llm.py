"""LLM backends: a deterministic stub for offline runs, and LiteLLM
for the real model. The stub is rule-based on purpose — it is the
harness that makes the three ontology versions score differently.
The live layer stays provider-agnostic through LiteLLM (model from
LLM_MODEL, default gemini/gemini-3.5-flash-lite).
"""
from __future__ import annotations

import os
import re

OCT_FILTER = "order_date BETWEEN '2026-10-01' AND '2026-10-31'"


class StubBackend:
    """Deterministic stub: builds SQL from ontology lookups + intent.

    The output MUST depend on ontology content — that is what makes
    no-ontology, initial, and evolved score differently. A wrong
    mapping produces wrong SQL; a missing alias produces a wrong
    literal; a missing relationship produces a wrong join.
    """

    @staticmethod
    def sql_for(intent: str, question: str, lookups: dict,
                relationships: list) -> str:
        q = question.lower()
        october = "october" in q

        if intent == "revenue":
            term = lookups.get("revenue")
            if term is not None and term.mapping \
                    and "/100" in term.mapping and "paid" in term.mapping:
                where = "p.status = 'paid'"
                if october:
                    where += f" AND o.{OCT_FILTER}"
                return ("SELECT SUM(o.total_cents)/100.0 FROM orders o "
                        f"JOIN payments p ON p.order_id = o.id WHERE {where}")
            # Wrong mapping (v0) or no ontology: naive cents, no paid filter.
            if october:
                return ("SELECT SUM(total_cents) FROM orders "
                        f"WHERE {OCT_FILTER}")
            return "SELECT SUM(total_cents) FROM orders"

        if intent == "web_orders":
            term = lookups.get("web orders")
            channel = "online" if (term is not None and term.mapping
                                   and "'online'" in term.mapping) else "web"
            where = f"channel = '{channel}'"
            if october:
                where += f" AND {OCT_FILTER}"
            if "list" in q:
                return f"SELECT id FROM orders WHERE {where} ORDER BY id"
            return f"SELECT COUNT(*) FROM orders WHERE {where}"

        if intent == "best_seller":
            term = lookups.get("best-selling product")
            if term is not None and term.mapping \
                    and "SUM" in term.mapping and "qty" in term.mapping:
                if october:
                    return ("SELECT p.name FROM order_items oi "
                            "JOIN products p ON p.id = oi.product_id "
                            "JOIN orders o ON o.id = oi.order_id "
                            f"WHERE o.{OCT_FILTER} GROUP BY p.id "
                            "ORDER BY SUM(oi.qty) DESC LIMIT 1")
                return ("SELECT p.name FROM order_items oi "
                        "JOIN products p ON p.id = oi.product_id "
                        "GROUP BY p.id ORDER BY SUM(oi.qty) DESC LIMIT 1")
            # Wrong mapping (v0): most orders, not most units.
            return ("SELECT p.name FROM order_items oi "
                    "JOIN products p ON p.id = oi.product_id "
                    "GROUP BY p.id ORDER BY COUNT(DISTINCT oi.order_id) "
                    "DESC LIMIT 1")

        if intent == "active_customers":
            term = lookups.get("active customer")
            text = ((term.definition if term else "") + " "
                    + (term.mapping if term else "")).lower()
            if term is not None and "paid order" in text:
                cond = ("EXISTS (SELECT 1 FROM orders o "
                        "JOIN payments p ON p.order_id = o.id "
                        "WHERE o.customer_id = c.id AND p.status = 'paid')")
                if "how many" in q:
                    return f"SELECT COUNT(*) FROM customers c WHERE {cond}"
                return (f"SELECT c.name FROM customers c WHERE {cond} "
                        "ORDER BY c.name")
            # Wrong definition (v0) or no ontology: recency proxy.
            if "how many" in q:
                return ("SELECT COUNT(*) FROM customers WHERE signup_date >= "
                        "date('2026-10-31','-90 days')")
            return ("SELECT name FROM customers WHERE signup_date >= "
                    "date('2026-10-31','-90 days') ORDER BY name")

        if intent == "avg_order_value":
            term = lookups.get("average order value")
            if term is not None and term.mapping and "/100" in term.mapping:
                return ("SELECT AVG(o.total_cents)/100.0 FROM orders o "
                        "JOIN payments p ON p.order_id = o.id "
                        "WHERE p.status = 'paid'")
            return "SELECT AVG(total_cents) FROM orders"

        if intent == "top_customer":
            has_rel = any(
                getattr(r, "source", "") == "orders"
                and getattr(r, "target", "") == "payments"
                for r in relationships
            )
            if has_rel:
                return ("SELECT c.name FROM orders o "
                        "JOIN customers c ON c.id = o.customer_id "
                        "JOIN payments p ON p.order_id = o.id "
                        "WHERE p.status = 'paid' GROUP BY c.id "
                        "ORDER BY SUM(o.total_cents) DESC LIMIT 1")
            # No orders->payments relationship: falls back to raw totals.
            return ("SELECT c.name FROM orders o "
                    "JOIN customers c ON c.id = o.customer_id "
                    "GROUP BY c.id ORDER BY SUM(o.total_cents) DESC LIMIT 1")

        if intent == "vip_customers":
            term = lookups.get("VIP customer")
            if term is not None:
                return "SELECT name FROM customers WHERE is_vip = 1 ORDER BY name"
            return "SELECT name FROM customers WHERE is_vip = 'yes' ORDER BY name"

        if intent == "discontinued_products":
            term = lookups.get("discontinued product")
            if term is not None:
                return "SELECT name FROM products WHERE discontinued = 1 ORDER BY name"
            return "SELECT name FROM products WHERE discontinued = 'yes' ORDER BY name"

        if intent == "discontinued_buyers":
            vip = lookups.get("VIP customer")
            disc = lookups.get("discontinued product")
            if vip is not None and disc is not None:
                return ("SELECT DISTINCT c.name FROM customers c "
                        "JOIN orders o ON o.customer_id = c.id "
                        "JOIN order_items oi ON oi.order_id = o.id "
                        "JOIN products p ON p.id = oi.product_id "
                        "WHERE c.is_vip = 1 AND p.discontinued = 1 "
                        "ORDER BY c.name")
            return ("SELECT DISTINCT c.name FROM customers c "
                    "JOIN orders o ON o.customer_id = c.id "
                    "JOIN order_items oi ON oi.order_id = o.id "
                    "JOIN products p ON p.id = oi.product_id "
                    "WHERE c.is_vip = 'yes' AND p.discontinued = 'yes' "
                    "ORDER BY c.name")

        if intent == "count_customers":
            return "SELECT COUNT(*) FROM customers"

        if intent == "total_orders":
            return "SELECT COUNT(*) FROM orders"

        if intent == "orders_in_period":
            return f"SELECT COUNT(*) FROM orders WHERE {OCT_FILTER}"

        if intent == "list_products":
            return "SELECT name FROM products ORDER BY name"

        # Unknown intent: the stub has no handler, so it guesses.
        return "SELECT 1"


def extract_sql(text: str) -> str:
    """Pull the SQL out of a ```sql fence, or use the raw text."""
    match = re.search(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


class LiteLLMBackend:
    """Real LLM through LiteLLM. Model from LLM_MODEL, default
    gemini/gemini-3.5-flash-lite. Raises the underlying litellm
    error (e.g. ServiceUnavailableError on Gemini 503) so callers
    can report it honestly instead of hiding it."""

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get(
            "LLM_MODEL", "gemini/gemini-3.5-flash-lite")

    def generate(self, prompt: str) -> str:
        import litellm  # imported lazily: stub runs never need it

        response = litellm.completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


def backend_for_env() -> str:
    """'llm' only when a key is plausibly present, else the stub."""
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY"):
        return "llm"
    return "stub"
