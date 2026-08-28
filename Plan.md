# Project 5: End-to-End Analytics Pipeline with SQL, dbt & BI Dashboard

## 1. Project Description

A complete analytics engineering pipeline that takes raw, messy transactional/event data, transforms it into clean, well-modeled tables using SQL-based transformations (dbt), loads it into a proper data warehouse structure, and presents real business metrics (retention, funnels, revenue trends) through an interactive BI dashboard, scheduled and CI-tested like a real production pipeline. This mirrors exactly what a Data Analyst or junior Data Engineer does day-to-day at a real company — not a one-off notebook analysis, but a maintained, testable, documented, and automated data pipeline.

**Key features:**
- Realistic raw dataset (simulated e-commerce or app usage events) with intentional, non-trivial messiness (typo-variant duplicates, mismatched timezones, late-arriving dimensions) to clean
- SQL transformation layer built with dbt (staging → intermediate → mart layers)
- At least one incremental model (not full-rebuild-only), reflecting how real fact tables are handled at scale
- Automated data quality tests — both generic (`unique`, `not_null`) and custom business-logic tests (e.g., "retention % must be between 0 and 100")
- A proper star-schema-style data model for analytics
- A basic CI pipeline (GitHub Actions) that runs `dbt build`/lint on every push
- A simple scheduled run (cron or GitHub Actions schedule) so the pipeline isn't manually triggered
- An interactive BI dashboard (Metabase) showing cohort retention, conversion funnels, and revenue trends
- Documentation of every model (what each table means, how it's built) — dbt auto-generates this
- A live "maintenance-flow" demo proving the layered architecture actually isolates change

## 2. Problem Statement

Businesses generate raw data constantly, but raw data is rarely usable directly — it's scattered across tables, has duplicates and errors, and doesn't answer business questions on its own ("did retention improve after our last release?" requires real transformation work first). Data Analyst and junior Data Engineer roles are tested heavily on exactly this: can you take messy data and turn it into a trustworthy, well-modeled answer to a real business question, using SQL fluently, and can you run that pipeline reliably rather than by hand. Most student projects skip this entirely and go straight to a polished dataset and a chart — which doesn't prove you can handle the messy, real, and operational parts of the job. This project builds the full, realistic pipeline: mess-in, trustworthy-insight-out, running on its own.

## 3. Project Architecture

### Chosen architecture: Layered dbt transformation model (staging → intermediate → marts) + CI + lightweight scheduling + BI layer

```
Raw Data (simulated: orders, users, events — intentionally messy)
        │
   Loaded into warehouse (PostgreSQL, acting as the warehouse)
        │
   dbt: Staging Layer (1:1 with raw tables, light cleaning: types, renaming, deduplication)
        │
   dbt: Intermediate Layer (joins, business logic — e.g., "first purchase date per user")
        │
   dbt: Marts Layer (final, analysis-ready tables; revenue_trends built as an incremental model)
        │
   dbt tests (generic + custom, run automatically on every build)
        │
   GitHub Actions CI (runs dbt build/lint on every push)
        │
   Scheduled run (cron / GH Actions schedule — pipeline runs without manual trigger)
        │
   BI Dashboard (Metabase) reading from Marts layer only
```

### Alternative architectures considered

**A. Direct SQL queries against raw data, no transformation layer (write one big query per chart)**
- *Pros:* Fastest to get a dashboard up
- *Cons:* Every chart re-implements the same cleaning/joining logic, no reusability, no tests, no documentation, breaks the moment raw data format changes — does not reflect how real analytics teams work at all, and won't hold up if an interviewer asks "how do you keep your metrics consistent across dashboards?"
- *Verdict: Rejected — this is the "generic tutorial" version of this project.*

**B. Full data engineering stack with Spark/Airflow for orchestration (treat this as a big-data pipeline)**
- *Pros:* Sounds impressive, uses "big data" tools
- *Cons:* Massive overkill for a dataset that doesn't require distributed processing (Spark solves a scale problem you don't have), and full Airflow adds real infra complexity for near-zero benefit at this project's scale — risks weeks lost to infra rather than analytics skill
- *Verdict: Rejected — wrong tool for the actual problem size. A lightweight cron/GitHub Actions schedule gets you 90% of the "this runs on its own" credibility for a fraction of the setup cost.*

**C. Layered dbt transformation model + lightweight CI/scheduling + BI dashboard (chosen)**
- *Pros:* dbt's staging → intermediate → marts pattern is the actual industry-standard approach used at real companies, naturally forces clean, tested, documented SQL, and produces genuinely reusable, demonstrable artifacts (dbt docs site, tests, CI runs, final dashboard). Adding CI and scheduling closes the "how does this run without you" gap without the cost of full orchestration tooling.
- *Cons:* dbt has a learning curve if you've never used it — mitigated by strong documentation and a gentle on-ramp; CI/cron adds a small amount of setup time
- *Verdict: Selected.*

## 4. Technology Stack & Skill Set

| Category | Technology | Skill Required |
|---|---|---|
| Database/warehouse | PostgreSQL | SQL (joins, window functions, CTEs, aggregations) |
| Transformation | dbt (data build tool) | Writing modular SQL models, incremental models, dbt tests, dbt docs |
| Data generation | Python (Faker library) | Scripting realistic, intentionally messy synthetic data |
| CI | GitHub Actions | Basic YAML workflow, running `dbt build`/`sqlfluff` on push |
| Scheduling | Cron or GitHub Actions schedule | Triggering pipeline runs without manual intervention |
| BI/dashboard | Metabase | Connecting to a warehouse, building charts/dashboards |
| Version control | Git | Managing dbt project as code |

## 5. Role of Each Technology

- **PostgreSQL**: Acts as your data warehouse — holds both the raw loaded data and every transformed table dbt produces. Chosen because it's free, well-understood, and exactly mirrors how a real (if smaller-scale) analytics warehouse works.
- **dbt**: The core transformation engine — you write SQL `SELECT` statements defining each model (table/view), and dbt handles building them in the right dependency order, testing them, and documenting them. Using at least one incremental model shows you understand how real fact tables avoid full rebuilds as data grows. This is the tool that turns "a folder of SQL scripts" into "a maintainable analytics codebase" — exactly the skill gap between a hobbyist and a hireable analyst.
- **Python (Faker)**: Used only to generate your realistic raw dataset — simulating real-world messiness (typo-variant duplicate signups, missing fields, inconsistent timezones/date formats, orphaned foreign keys) on purpose, so your cleaning/transformation work in dbt has something genuine to solve, rather than starting from an already-clean CSV.
- **GitHub Actions (CI)**: Runs `dbt build` (and optionally `sqlfluff lint`) automatically on every push, so broken models or failing tests are caught before they'd ever reach a dashboard — this is the difference between "I wrote some SQL" and "I have a tested pipeline."
- **Cron / GitHub Actions schedule**: Triggers the pipeline to run on its own (e.g., nightly), so the project isn't "something I run by hand when I remember to" — a small addition that answers a very commonly asked interview question.
- **Metabase**: Connects directly to your PostgreSQL warehouse and lets you build and share interactive dashboards without writing frontend code — used here to present your final marts-layer tables as real, business-readable charts (retention curves, funnels) that you can screenshot or demo live.
- **Git**: Your entire dbt project (all SQL models, tests, configs, CI workflow) lives in version control, exactly as it would at a real company — this is also what makes the project reviewable/shareable on GitHub.

## 6. Detailed Implementation Plan

### Phase 1: Generate Realistic Raw Data (Days 1-3)
*(budgeted a day longer than a first pass suggests — this phase is fiddlier than it looks)*
- Use Python + Faker to generate three raw tables: `users`, `orders`, `events` (e.g., page views, add-to-cart, purchase)
- Deliberately inject realistic, *non-trivial* messiness — go beyond generic nulls/duplicates so the cleaning logic is actually worth discussing in an interview:
  - Duplicate user signups with slightly different emails (typo variants, not exact duplicates — harder to detect)
  - Inconsistent timezone/date formats across the three tables (e.g., `orders` in UTC, `events` in local time)
  - Orders referencing user IDs that don't exist yet in the `users` table (a late-arriving-dimension problem, common in real pipelines)
  - A few missing/null fields and a handful of negative/zero-value orders (data entry errors)
- Load this raw data into PostgreSQL as your "raw" schema

### Phase 2: dbt Project Setup (Day 4)
- Initialize a dbt project, connect it to your PostgreSQL instance
- Set up the folder structure: `models/staging`, `models/intermediate`, `models/marts`
- Initialize Git repo; set up `.gitignore` for dbt/Python artifacts

### Phase 3: Staging Layer (Days 5-6)
- Write staging models: one per raw table, doing light cleaning only — correct types, consistent column naming, deduplication, basic null handling
- Add dbt tests here: e.g., `unique` and `not_null` tests on primary keys

### Phase 4: Intermediate Layer (Days 7-9)
- Build models that join staging tables and compute reusable business logic — e.g., `first_purchase_date` per user, `sessionized` events (grouping raw events into sessions)
- This layer exists so the final marts don't repeat complex logic — a core dbt best practice worth understanding and explaining

### Phase 5: Marts Layer (Days 10-12)
- Build the final analysis-ready tables:
  - `monthly_cohort_retention` — for each signup month cohort, what % of users were still active in month 1, 2, 3...
  - `funnel_summary` — conversion rates between key steps (viewed product → added to cart → purchased)
  - `revenue_trends` — daily/monthly revenue, average order value over time — **build this one as an incremental model**, so you can speak to how dbt avoids full-table rebuilds as data grows
- Add tests here too:
  - Generic: `accepted_values`, `not_null`
  - Custom singular tests, e.g.: "revenue should never be negative," "retention percentage must be between 0 and 100," "no session should exceed 24 hours"

### Phase 6: CI Setup (Day 13)
- Add a GitHub Actions workflow that runs `dbt build` (and optionally `sqlfluff lint`) on every push to the repo
- Confirm it fails loudly on a broken model or failing test (test this deliberately once, then fix it, and note it in the README)

### Phase 7: Scheduling (Day 13, same day as CI)
- Add a simple scheduled trigger — either a GitHub Actions `schedule` (cron syntax) or a local cron job — that re-runs the pipeline on a fixed cadence (e.g., nightly)
- This doesn't need to be sophisticated; the point is demonstrating the pipeline runs unattended, not building an orchestrator

### Phase 8: Documentation (Day 14)
- Add descriptions to every model and column in dbt's YAML config files
- Generate and review the dbt docs site (auto-built from your project) — this becomes a genuinely impressive artifact to link/screenshot for your resume

### Phase 9: BI Dashboard (Days 15-16)
- Connect Metabase to your PostgreSQL warehouse, pointed at the marts layer only (not raw data — this is intentional, matches real practice of only exposing clean, documented tables to dashboards)
- Build 3-4 key visualizations: cohort retention curve, funnel chart, revenue trend line, and one more of your choice
- Arrange into a single dashboard view

### Phase 10: Prove the Maintenance-Flow Claim, Live (Day 17)
- This project's core differentiator (vs. the rejected direct-SQL approach) is that only the staging layer needs updating when raw data changes. Don't just claim this — demonstrate it: after the full pipeline is built and working, add a new column to the raw `orders` table, then show that only the corresponding staging model needs a change, while intermediate/marts models and the dashboard continue working unaffected
- Record this as a short before/after in your README — this single demo is your strongest evidence of understanding *why* layered dbt architecture is used, not just how to write it

### Phase 11: Write-up (Day 18)
- Write a README explaining:
  - The business questions each dashboard answers
  - Key findings from your synthetic data (e.g., "cohort retention drops sharply after month 2")
  - The pipeline architecture (include the dbt lineage graph screenshot)
  - Why an incremental model was used for `revenue_trends`
  - The CI setup and what it catches
  - The scheduling setup
  - The maintenance-flow demo (Phase 10), with before/after
- Include screenshots of the dashboard, the dbt docs/lineage graph, and a green CI run

## 7. Project Workflow

**Data transformation flow:**
Raw messy data lands in PostgreSQL → dbt staging models clean and standardize it (types, dedup, naming) → dbt intermediate models join and compute reusable business logic (session grouping, first-purchase dates) → dbt marts models produce final, analysis-ready tables (cohort retention, funnels, revenue, with revenue built incrementally) → dbt tests (generic + custom) run automatically at each layer, catching data quality issues before they reach the dashboard.

**Automation flow:**
Every push to Git triggers CI, which runs `dbt build` and fails loudly on any broken model or test → a scheduled job (cron/GitHub Actions) re-runs the full pipeline on a fixed cadence without manual intervention → this is what separates "a working script" from "a pipeline."

**Dashboard flow:**
Metabase connects only to the marts layer (never raw data directly) → dashboard queries pull from these clean, tested, documented tables → charts render cohort retention, funnel conversion rates, and revenue trends → a stakeholder (or interviewer) can trust these numbers because they're backed by a tested, documented, automated, reproducible pipeline, not an ad hoc query.

**Maintenance flow (the story you can tell in an interview):**
If new raw data format changes (e.g., a new column added to the `orders` table), only the staging model touching that table needs updating — the intermediate and marts layers, and the dashboard, continue working unaffected, because of the layered design. This demonstrates you understand *why* professional analytics pipelines are built this way, not just how to write a working SQL query once.

## 8. Resume/Interview Talking Points (what this project should let you say)

- "I built a layered dbt pipeline (staging/intermediate/marts) on top of intentionally messy synthetic data, including hard-to-detect issues like typo-variant duplicate accounts and late-arriving foreign keys."
- "I used an incremental model for the revenue mart to avoid full-table rebuilds, and wrote custom dbt tests beyond the defaults — e.g., asserting retention percentages stay within valid bounds."
- "The pipeline runs in CI on every push and on a schedule, so it's not something I run by hand — GitHub Actions catches broken models before they'd reach the dashboard."
- "I can demonstrate live that adding a column to raw source data only requires a one-line change in the staging layer — the intermediate layer, marts, and dashboard are unaffected. That's the actual reason this architecture is used."
