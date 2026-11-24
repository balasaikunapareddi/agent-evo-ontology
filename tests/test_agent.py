from agent_evo_ontology.agent import TextToSqlAgent, classify_intent
from agent_evo_ontology.evolution import EvolutionLoop
from agent_evo_ontology.mcp_server import OntologyClient
from agent_evo_ontology.ontology import (
    build_empty_ontology,
    build_initial_ontology,
)
from agent_evo_ontology.questions import split_questions
from agent_evo_ontology.store import normalize_rows, rows_match


def _agent(layer, db_path):
    return TextToSqlAgent(OntologyClient(layer), db_path, backend="stub")


def test_intent_classification():
    assert classify_intent("What is our total revenue?") == "revenue"
    assert classify_intent("How many web orders?") == "web_orders"
    assert classify_intent("What is our best-selling product?") == "best_seller"
    assert classify_intent("How many active customers?") == "active_customers"
    assert classify_intent("What is the average order value?") == "avg_order_value"
    assert classify_intent("Who is our top customer by total spending?") == "top_customer"
    assert classify_intent("List our VIP customers.") == "vip_customers"
    assert classify_intent("How many customers do we have?") == "count_customers"


def test_execution_accuracy_is_order_and_type_insensitive():
    assert rows_match([(1, "a"), (2, "b")], [("2", "b"), ("1", "a")])
    assert not rows_match([(1,)], [(2,)])
    assert normalize_rows([(2,), (1,)]) == normalize_rows([(1,), (2,)])


def test_stub_revenue_depends_on_ontology(db_path, v0):
    naive = _agent(build_empty_ontology(), db_path).generate_sql(
        "What is our total revenue?")
    assert naive == "SELECT SUM(total_cents) FROM orders"
    wrong = _agent(v0, db_path).generate_sql("What is our total revenue?")
    assert wrong == "SELECT SUM(total_cents) FROM orders"


def test_stub_web_orders_wrong_without_alias(db_path, v0):
    sql = _agent(v0, db_path).generate_sql("How many web orders did we receive?")
    assert "channel = 'web'" in sql


def test_agent_never_gets_raw_schema(db_path, v0):
    agent = _agent(v0, db_path)
    # The agent holds a client and a db path for execution — no schema.
    assert not hasattr(agent, "schema")
    assert hasattr(agent, "client")


def test_accuracy_ordering_evolved_ge_initial_ge_no_ontology(db_path, questions, v0):
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")
    no_acc = _agent(build_empty_ontology(), db_path).evaluate(questions).accuracy
    v0_acc = _agent(v0, db_path).evaluate(questions).accuracy
    loop = EvolutionLoop(db_path, backend="stub")
    evolved, _log = loop.run(v0, dev, validation)
    evo_acc = _agent(evolved, db_path).evaluate(questions).accuracy
    assert evo_acc >= v0_acc >= no_acc
    assert evo_acc > v0_acc  # the loop actually improves the stub


def test_exact_stub_accuracies(db_path, questions, v0):
    dev = split_questions(questions, "dev")
    validation = split_questions(questions, "validation")
    no_all = _agent(build_empty_ontology(), db_path).evaluate(questions)
    v0_all = _agent(v0, db_path).evaluate(questions)
    loop = EvolutionLoop(db_path, backend="stub")
    evolved, _log = loop.run(v0, dev, validation)
    evo_all = _agent(evolved, db_path).evaluate(questions)
    assert (no_all.correct, no_all.total) == (3, 16)
    assert (v0_all.correct, v0_all.total) == (4, 16)
    assert (evo_all.correct, evo_all.total) == (13, 16)
