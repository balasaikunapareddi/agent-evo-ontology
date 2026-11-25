# agent-evo-ontology

Semantic layers go stale. You build one carefully — "revenue means this",
"a web order is that" — and six months later the business has moved on,
the agent is still guessing from the old definitions, and nobody notices
until a report is wrong. The usual fix is another round of hand-editing
the layer and hoping it helped. This repo is a small, working version of
a better loop: build the ontology from data, let the agent query it
through MCP without ever seeing the raw schema, and after a run, let the
tool propose a change — then keep the change **only** when a paired test
against the previous version shows it actually got better.

It mirrors [EvoOntology](https://github.com/ruc-datalab/EvoOntology)
(Renmin University of China). Their idea, their numbers where quoted;
this repo is a from-scratch mirror on a fictional shop, not a port of
their code.

## The shop

Harbor & Pine Supply Co. is fictional: 12 customers, 31 orders, 61 order
items, 10 products, 31 payments, data through 2026-10-31, in SQLite.
It is small on purpose, and it is rigged with the traps a real semantic
layer has to survive:

- `orders.total_cents` is **integer cents**, not dollars.
- `payments.status` is `paid`, `refunded`, or `failed` — revenue only
  counts when it was actually paid.
- `orders.channel` is `online`, `phone`, or `in-store` — there is no
  channel called `web`, even though everyone says "web orders".
- Best-selling means most **units** (`SUM(qty)`), not most orders.
- An active customer is one with at least one **paid order**, not one
  who signed up recently.
- Average order value is in dollars, over paid orders.

Sixteen questions (8 dev, 8 validation) sit on top of it in
`data/questions.json`, each with gold SQL that the test suite verifies
against the seeded database.

## How it works

**Build.** The ontology layer v0 is built from the schema and three short
seed documents (`data/seed_docs.md`). It is deliberately imperfect —
the same ways a first-pass layer is imperfect in real life. Revenue maps
to `SUM(orders.total_cents)` (cents, no paid-only filter). The "web"
alias is missing. Best-selling maps to a count. Active customer maps to 'signed up in the last 90 days'. Average order value is missing the
`/100`. The orders → payments relationship is missing. A few terms are
right (VIP customer, discontinued product, total orders), because a
first-pass layer is never all wrong.

**Use.** The agent (`TextToSqlAgent` in `src/agent_evo_ontology/agent.py`)
answers a question by looking terms up through MCP tools
(`lookup_term`, `list_relationships`, `search_ontology`, `get_manifest`)
and then writing SQL. It never sees the raw schema — it takes an
`OntologyClient`, not the database schema, and the database handle is
only used to execute SQL. The MCP server is the official MCP Python SDK
(`mcp==2.3.0`, `MCPServer` — FastMCP was renamed in 2.x) and runs over
stdio with `python -m agent_evo_ontology.mcp_server`, so any MCP client
can query the layer. The same tool logic is plain Python functions, so
the agent can also call them in-process.

**Evolve.** The loop evaluates the parent layer on the dev set, diagnoses
each failure with small deterministic rules (one candidate patch per
failure type), and for each candidate applies it to a **copy** of the
layer and runs a paired evaluation — parent vs candidate — on the
validation split only.

**Evaluate / publish-or-reject.** The gate (`gate.py`) is McNemar on the
discordant pairs: b = parent wrong & candidate right, c = parent right &
candidate wrong. With 10+ discordant pairs it uses the exact two-sided
binomial test (implemented with `math.comb`, no scipy) and keeps only if
p < 0.05, b > c, and accuracy improved. Below 10 pairs it falls back to
a margin rule: keep only if b − c ≥ 2 and accuracy improved. A candidate
is published — the layer version bumps, `ontology_v0` → `v1` → … — only
when the gate keeps it. Every decision is logged (`EvolutionLogEntry`),
printed, and saved to `.runs/` as JSON.

One candidate is deliberately neutral — an alias "shopper" → customer
that changes nothing the agent can use — so the gate has something to
reject honestly. It does.

**The annotation-error flag.** After an accepted edit, every validation
question the edit newly won is flagged for gold-query review: its gold
SQL is printed next to the agent's SQL with a note citing Wretblad et al.
(arXiv 2402.12243), who re-annotated BIRD's 106 financial dev questions
and found wrong gold SQL in 20.7% of them. A fix that "wins" by matching
a wrong gold answer is a learned annotation error, not an improvement.
In this fictional dataset gold is verified by construction (the tests
assert every gold SQL returns its expected rows), so the flag here is
precautionary — but the habit is the point.

## What it actually scores

These are **this repo's own numbers**, from the deterministic stub agent
(`python -m agent_evo_ontology demo`), same 16 questions, all three
versions side by side:

| version | overall | validation |
| --- | --- | --- |
| no-ontology | 3/16 (18.8%) | 2/8 (25.0%) |
| initial (v0) | 4/16 (25.0%) | 2/8 (25.0%) |
| evolved (ontology_v3) | 13/16 (81.2%) | 8/8 (100.0%) |

The gate kept 3 of 7 candidates and rejected 4:

- **Kept:** fix revenue mapping, add "web" → `online` alias, fix
  best-seller mapping (each won 2 validation questions, b=2, c=0).
- **Rejected:** fix active-customer definition, fix average-order-value
  mapping, add orders → payments relationship — all three are real
  fixes for real dev failures, but none of them wins a validation
  question (b=0, c=0), so the margin gate holds them back. That is the
  gate being conservative, not the fixes being wrong: with only 8
  validation questions there is no evidence either way, and the loop
  refuses to ship on no evidence. The neutral "shopper" alias was
  rejected too, as it should be.

So the evolved layer still carries the wrong average-order-value mapping
and the wrong active-customer definition. That is an honest result, and
it is the result the gate is designed to produce on a dataset this small.
A bigger validation set would settle those three.

### Live test with real Gemini

`scripts/live_test.py` runs the same loop with a real model
(`gemini/gemini-3.5-flash-lite`, via LiteLLM), same 16 questions:

| version | overall |
| --- | --- |
| no-ontology | 2/16 (12.5%) |
| initial (v0) | 2/16 (12.5%) |
| evolved (ontology_v1) | 6/16 (37.5%) |

The gate kept 1 of 7 candidates live (fix best-seller mapping, b=2,
c=0; newly-won v5/v6 flagged for gold-query review) and rejected 6 —
including the revenue fix, which improved validation 25% → 38% but only
won one question (b=1, c=0), below the margin-fallback bar of b − c ≥ 2.
The full report is in `.runs/live/attempt-4/report.json`.

Two things the live run taught me that the stub could not. First, the
real model is worse than the stub with no ontology (2/16 vs 3/16): it
invents columns (`c.customer_name`) and joins that do not exist, and
those score as wrong — which is also why the agent now catches SQL
errors instead of crashing on them. Second, the ontology still helps
the real model (2 → 6), but the initial ontology helped it not at all
(2 → 2): a small model does not reliably use the layer it is given, and
only the evolved layer's corrections moved the needle. The live numbers
are lower across the board than the stub's — that is the gap between a
rule-based harness and a real model on a 16-question toy set, and it is
exactly why the stub numbers above are labelled as the stub's.

## The paper's numbers (theirs, not this repo's)

EvoOntology (Chong et al., arXiv 2609.15779) reports, on the paper's
four-model subset (GPT-5.5, GPT-5.6-sol, Claude-Sonnet-5, Claude-Opus-4.8),
BIRD execution accuracy of **63.6 with no ontology, 68.7 with the initial
ontology, and 72.4 evolved** — +8.8 total, of which the loop itself adds
3.7. On their other benchmarks: **DDR-Bench 69.5 → 81.8 → 89.5** and
**InsightBench 53.2 → 54.0 → 54.2**. Their design is a versioned ontology
layer over MCP (`browse_semantics`, `resolve_semantics`, plus a session
manifest), a Content layer (Terms, Mappings, Constraints, Evidence), and
the lifecycle Build → Use → Evolve → Evaluate → Publish-or-reject, where
a candidate is published only when a paired evaluation shows a
reproducible improvement over its parent. This repo mirrors that shape
at toy scale; it does not reproduce their benchmarks.

## Why plain Python + LiteLLM + the MCP SDK

No agent framework was needed. This is a single-purpose loop — look a
term up, write SQL, run it, compare — and a framework would have added
moving parts without adding anything the loop needs. LiteLLM keeps the
live layer provider-agnostic: the model comes from `LLM_MODEL`
(default `gemini/gemini-3.5-flash-lite`) and swaps by config, so the
same agent runs against any provider LiteLLM supports. The official MCP
SDK is used instead of a hand-rolled protocol so any MCP client can
query the layer without this repo in the middle.

## Honest limits

- **Small fictional dataset, not BIRD.** Sixteen questions on a toy shop
  prove the loop works end to end; they say nothing about how it would
  do on a real benchmark.
- **The stub agent is rule-based.** It builds SQL from ontology lookups
  plus small intent handlers. Without an ontology it has to guess
  literals (`is_vip = 'yes'`, `channel = 'web'`), which is why
  no-ontology scores 3/16. The live run showed the real model scoring
  2/16 with no ontology — worse than the stub, because it invents
  columns and joins. The stub exists to make the three versions differ
  deterministically, not to stand in for a model.
- **McNemar on 8 validation questions is weak.** With 8 questions the
  discordant count never reaches 10, so the exact test never fires and
  every decision runs on the margin fallback (b − c ≥ 2). That is
  documented in `gate.py`, and it is why three real fixes were held back.
- **An ontology does not travel across backbones.** The paper reports
  term-set overlap ≤ 0.62 between layers evolved under different models
  and a ≥ 5.7-point DDR-Bench drop when a layer is reused across
  backbones. The layer here was evolved under the stub; do not assume it
  would help a different model the same way.
- **The live parent baseline is a single re-rolled sample.** After a
  keep, the parent is re-measured with a fresh model sample, and the
  two samples can disagree: live, the best-seller layer scored 0.5 as
  the candidate and 0.375 when re-measured as the new parent. The gate
  compares one candidate sample against one parent sample, so a live
  keep/reject is noisier than the stub's deterministic verdicts.
- **Gold is verified by construction here.** The annotation-error flag is
  precautionary in this repo. On a real dataset it would be load-bearing.

## How this differs

- **vs agent-graph-rag:** that repo builds a knowledge graph for
  multi-hop question answering over documents. This one builds an
  ontology layer for text-to-SQL — and, more importantly, the ontology
  **evolves** under a paired gate that decides whether each edit ships.
- **vs agent-eval-levels:** that repo diagnoses a failed session on
  three levels (session, exchange, tool call). This one does not diagnose
  sessions at all — it is a gate that decides whether an ontology **edit**
  ships, based on paired before/after evidence.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
.venv/bin/python -m agent_evo_ontology demo     # no API key needed
.venv/bin/python -m agent_evo_ontology evolve   # same run, gate log
.venv/bin/python -m pytest tests/ -q            # 71 tests, stub only
.venv/bin/python -m agent_evo_ontology.mcp_server  # stdio MCP server
```

For the live loop, copy `.env.example` to `.env`, set `GEMINI_API_KEY`,
and run `python scripts/live_test.py`. It runs the real-Gemini loop end
to end and saves a report to `.runs/live/attempt-N/report.json`. If
Gemini answers 503, the script catches it, prints which step was
blocked, and exits non-zero instead of pretending the run happened.
With no key set it runs in stub mode and says so.

## Layout

```
src/agent_evo_ontology/
  prompts.py      system prompt — the ONLY place it lives, never inline
  models.py       Pydantic: OntologyTerm, Relationship, OntologyLayer,
                  Question, Proposal, EvalResult, EvolutionLogEntry
  ontology.py     build v0, lookups, apply-proposal, versioning
  store.py        SQLite dataset (Harbor & Pine Supply Co.)
  questions.py    loader for data/questions.json
  mcp_server.py   official MCP SDK server + in-process OntologyClient
  agent.py        TextToSqlAgent — question -> ontology -> SQL -> rows
  llm.py          LiteLLM wrapper + deterministic stub
  evolution.py    EvolutionLoop: diagnose -> propose -> paired evaluate
  gate.py         McNemar gate (exact binomial + margin fallback)
  demo.py         one-command three-version comparison
  cli.py          python -m agent_evo_ontology demo | evolve
data/
  seed_docs.md    the loose business notes v0 was built from
  questions.json  16 questions with verified gold SQL
scripts/live_test.py
tests/            71 tests, deterministic stub, no API key
```

## Citations

- Chong et al., "EvoOntology: An Evolving Ontology Layer for LLM Agents
  over MCP", arXiv:2609.15779. Code:
  https://github.com/ruc-datalab/EvoOntology (MIT).
- Wretblad et al., "BIRD's-Eye View: On the (In)validity of Text-to-SQL
  Benchmarks", arXiv:2402.12243 — 20.7% of BIRD's 106 financial dev
  gold SQL queries were wrong on re-annotation.

## License

MIT. See `LICENSE`.
