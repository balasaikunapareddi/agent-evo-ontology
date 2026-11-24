"""Gold SQL verification: every gold SQL runs on the seeded DB and
returns exactly its expected rows."""
from agent_evo_ontology.questions import split_questions
from agent_evo_ontology.store import execute_sql, normalize_rows


def test_sixteen_questions_eight_per_split(questions):
    assert len(questions) == 16
    assert len(split_questions(questions, "dev")) == 8
    assert len(split_questions(questions, "validation")) == 8


def test_every_gold_sql_returns_expected_rows(db_path, questions):
    for q in questions:
        rows = execute_sql(db_path, q.gold_sql)
        assert normalize_rows(rows) == normalize_rows(
            [tuple(r) for r in q.expected_rows]), q.id


def test_seed_counts(db_path):
    assert execute_sql(db_path, "SELECT COUNT(*) FROM customers") == [(12,)]
    assert execute_sql(db_path, "SELECT COUNT(*) FROM orders") == [(31,)]
    assert execute_sql(db_path, "SELECT COUNT(*) FROM order_items") == [(61,)]
    assert execute_sql(db_path, "SELECT COUNT(*) FROM products") == [(10,)]
    assert execute_sql(db_path, "SELECT COUNT(*) FROM payments") == [(31,)]


def test_seed_discriminators(db_path):
    # Revenue: paid-only dollars differ from naive cents.
    paid = execute_sql(
        db_path,
        "SELECT SUM(o.total_cents)/100.0 FROM orders o "
        "JOIN payments p ON p.order_id = o.id WHERE p.status = 'paid'")
    naive = execute_sql(db_path, "SELECT SUM(total_cents) FROM orders")
    assert paid != naive
    # Best seller by units differs from best seller by order count.
    by_qty = execute_sql(
        db_path,
        "SELECT p.name FROM order_items oi JOIN products p "
        "ON p.id = oi.product_id GROUP BY p.id "
        "ORDER BY SUM(oi.qty) DESC LIMIT 1")
    by_count = execute_sql(
        db_path,
        "SELECT p.name FROM order_items oi JOIN products p "
        "ON p.id = oi.product_id GROUP BY p.id "
        "ORDER BY COUNT(DISTINCT oi.order_id) DESC LIMIT 1")
    assert by_qty == [("Maple Cutting Board",)]
    assert by_count == [("Pine Bookshelf",)]
    # Top customer by paid spending differs from top by raw totals.
    top_paid = execute_sql(
        db_path,
        "SELECT c.name FROM orders o JOIN customers c ON c.id = o.customer_id "
        "JOIN payments p ON p.order_id = o.id WHERE p.status = 'paid' "
        "GROUP BY c.id ORDER BY SUM(o.total_cents) DESC LIMIT 1")
    top_raw = execute_sql(
        db_path,
        "SELECT c.name FROM orders o JOIN customers c ON c.id = o.customer_id "
        "GROUP BY c.id ORDER BY SUM(o.total_cents) DESC LIMIT 1")
    assert top_paid == [("Priya Nair",)]
    assert top_raw == [("Mara Ellison",)]
