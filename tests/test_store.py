"""SQL safety: generated SQL must never mutate the dataset.

A text-to-SQL agent executes model output. Before this guard,
``DROP TABLE orders`` succeeded through execute_sql (verified by
hand) and would have corrupted the shared DB for every later
question in the run. The dataset is opened read-only and only
SELECT/WITH statements are accepted.
"""
import sqlite3

import pytest

from agent_evo_ontology.store import execute_sql


def test_drop_table_rejected_and_db_intact(db_path):
    with pytest.raises(sqlite3.OperationalError):
        execute_sql(db_path, "DROP TABLE orders")
    assert execute_sql(db_path, "SELECT COUNT(*) FROM orders") == [(31,)]


def test_delete_update_insert_rejected(db_path):
    for sql in (
        "DELETE FROM orders WHERE id = 1",
        "UPDATE orders SET total_cents = 0 WHERE id = 1",
        "INSERT INTO orders VALUES (99, 1, '2026-10-01', 'online', 100, NULL)",
    ):
        with pytest.raises(sqlite3.OperationalError):
            execute_sql(db_path, sql)
    assert execute_sql(db_path, "SELECT COUNT(*) FROM orders") == [(31,)]


def test_comment_smuggled_write_rejected(db_path):
    # A leading comment must not smuggle a write past the check.
    with pytest.raises(sqlite3.OperationalError):
        execute_sql(db_path, "-- harmless comment\nDROP TABLE orders")
    with pytest.raises(sqlite3.OperationalError):
        execute_sql(db_path, "/* note */ DELETE FROM orders")
    assert execute_sql(db_path, "SELECT COUNT(*) FROM orders") == [(31,)]


def test_select_and_with_still_work(db_path):
    assert execute_sql(db_path, "SELECT COUNT(*) FROM orders") == [(31,)]
    rows = execute_sql(
        db_path,
        "WITH x AS (SELECT COUNT(*) AS n FROM orders) SELECT n FROM x")
    assert rows == [(31,)]


def test_agent_scores_destructive_sql_wrong_not_crash(db_path, v0):
    from agent_evo_ontology.agent import TextToSqlAgent
    from agent_evo_ontology.mcp_server import OntologyClient

    agent = TextToSqlAgent(OntologyClient(v0), db_path, backend="stub")
    agent.generate_sql = lambda q: "DROP TABLE orders"
    _sql, rows = agent.answer("What is our total revenue?")
    assert rows == []
    # The table survived the attempt.
    assert execute_sql(db_path, "SELECT COUNT(*) FROM orders") == [(31,)]


def test_agent_scores_multi_statement_sql_wrong_not_crash(db_path, v0):
    from agent_evo_ontology.agent import TextToSqlAgent
    from agent_evo_ontology.mcp_server import OntologyClient

    agent = TextToSqlAgent(OntologyClient(v0), db_path, backend="stub")
    agent.generate_sql = lambda q: "SELECT 1; DROP TABLE orders"
    _sql, rows = agent.answer("What is our total revenue?")
    assert rows == []
    assert execute_sql(db_path, "SELECT COUNT(*) FROM orders") == [(31,)]
