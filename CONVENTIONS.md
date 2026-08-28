# Project Conventions

Follow these exactly and consistently across every file. Consistency across files matters more than any single choice below — pick one style per rule and never deviate.

## Naming
- All SQL identifiers (tables, models, columns, CTEs): `snake_case`, always. No camelCase anywhere, including in Python or config files that touch column names.
- Model file names match the table they build: `stg_orders.sql`, `int_first_purchase.sql`, `fct_revenue_trends.sql`, `dim_users.sql`.
- Prefix convention: `stg_` staging, `int_` intermediate, `fct_`/`dim_` marts (fact/dimension).
- No generic names anywhere: no `df`, `data`, `result`, `temp`, `final` as a table, CTE, or variable name. Every name should say what it holds (`orders_deduped`, `cohort_base`, `session_events`).

## SQL Style
- Use CTEs (`with x as (...)`) instead of nested subqueries. If a query needs a subquery inside a subquery, restructure it as sequential CTEs instead.
- One clause per line for anything beyond a trivial `select * from x`. Keep `select`, `from`, `where`, `group by` aligned and readable, not squeezed onto one line.
- Every CTE and every model has a purpose — no leftover/unused CTEs. Delete anything not referenced downstream before committing.
- Comments explain *why* a decision was made (e.g., "-- dedupe on email domain since typo variants share the same local part"), never *what* the SQL obviously already does (e.g., not "-- select all columns").

## Python Style
- Standard PEP8, but prioritize readability over cleverness — no one-liner list comprehensions doing three things at once.
- Config values (row counts, messiness rates, date ranges) live in a single `config.py` or top-of-file constants block — not scattered magic numbers.

## Commit History
- No single giant commits. Commit incrementally, matching the actual phases of build-out (e.g., "Add stg_users model", "Add unique/not_null tests to staging", "Fix orphaned order_id issue in stg_orders").
- Commit messages are specific and past-tense-imperative ("Add incremental logic to fct_revenue_trends"), not vague ("update", "fixes", "final version").
- Never squash the whole project history into 2-3 commits before sharing the repo — the incremental history is itself evidence of real iterative work.

## README / Docs Tone
- Write plainly and specifically. No marketing language ("robust", "cutting-edge", "seamless", "leverages"). State what the pipeline does and what decisions were made, in a factual tone.
- Any claimed result (e.g., "retention drops after month 2") must be backed by an actual number pulled from the generated data — never a generic/templated-sounding claim.

## Testing
- Don't test every column just to maximize coverage. Test what could plausibly break or matter for correctness (see TEST_PLAN.md). Uniform blanket testing on every field is itself a tell of not thinking through what actually needs validation.
