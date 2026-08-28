# End-to-End Analytics Pipeline with SQL, dbt & BI Dashboard

A production-style analytics engineering pipeline that extracts raw, intentionally messy transactional and behavioral clickstream data, standardizes and transforms it through a layered dbt architecture in PostgreSQL, enforces automated data quality tests, runs automated continuous integration (CI) and nightly scheduled builds, and serves clean marts models to an interactive BI layer.

---

## Architecture

The pipeline implements a three-tier layered dbt transformation architecture:

```text
Raw Synthetic Data (users.csv, orders.csv, events.csv with deliberate messiness)
         │
         ▼
PostgreSQL Warehouse (`raw` schema: raw.users, raw.orders, raw.events)
         │
         ▼
dbt Staging Layer (`public_staging`)
  ├── stg_users   : Typo-variant email deduplication, null filtering, date parsing
  ├── stg_orders  : Order retry deduplication, negative value filtering, UTC timestamp parsing
  └── stg_events  : Session validation, local timestamp parsing (timezone mismatch noted)
         │
         ▼
dbt Intermediate Layer (`public_intermediate`)
  ├── int_user_first_purchase : First purchase date, lifetime orders, cumulative customer spend
  └── int_sessionized_events  : Event aggregation, session duration, deepest funnel step
         │
         ▼
dbt Marts Layer (`public_marts`)
  ├── monthly_cohort_retention : Acquisition cohort retention matrices across elapsed months
  ├── funnel_summary           : Step-to-step and overall funnel conversion rates
  └── fct_revenue_trends       : Daily revenue, transaction volume, and AOV (Incremental Model)
         │
         ├──► dbt Tests (62 generic and custom singular tests executed automatically)
         ├──► GitHub Actions CI (Automated build, test, and sqlfluff lint on push/PR)
         ├──► GitHub Actions Schedule (Nightly unattended execution at 05:00 UTC)
         └──► Metabase BI Dashboard (Direct queries against marts layer only)
```

---

## Tech Stack

| Component | Tool / Technology | Purpose |
| :--- | :--- | :--- |
| **Data Warehouse** | PostgreSQL 16 | Relational data warehouse hosting `raw`, `staging`, `intermediate`, and `marts` schemas |
| **Transformation** | dbt-core / dbt-postgres (v1.12.3) | Modular SQL modeling, incremental processing, documentation, and data testing |
| **Synthetic Data Generator** | Python 3.11, Faker, psycopg2 | Generation of realistic datasets with non-uniform distributions and deliberate messiness |
| **Linter** | SQLFluff | Automated SQL syntax, CTE structure, and formatting enforcement |
| **Continuous Integration** | GitHub Actions | Automated end-to-end execution against an ephemeral PostgreSQL service container |
| **Scheduling** | GitHub Actions Cron | Unattended nightly pipeline execution (`0 5 * * *`) |
| **BI Dashboard** | Metabase | Business metric visualization (retention curves, funnels, revenue trends) |

---

## Synthetic Data Specification & Messiness Audit

The raw dataset reflects multi-year transactional and clickstream behaviors generated with non-uniform seasonal and day-of-week patterns:

| Table | Row Count | Injected Messiness / Characteristic | Injected Rate / Actual Count |
| :--- | :--- | :--- | :--- |
| **`users`** | 1,000 | Typo-variant duplicate registrations (dot omissions, domain typos like `@gmial.com`, transposed characters) | 40 rows (4.0%) |
| | | Null `signup_date` | 15 rows (1.5%) |
| | | Null `country` (nullable by design) | 15 rows (1.5%) |
| | | Signup Date Distribution | Clustered non-uniformly with acquisition peaks in Jan (124) and Nov/Dec (285) |
| **`orders`** | 3,500 | Orphaned `user_id` (late-arriving customer dimensions) | 51 rows (1.46%) |
| | | Negative or zero `order_value` | 38 rows (1.09%)\* |
| | | Duplicate `order_id` pairs with conflicting status/value/date (retry bugs) | 35 pairs (1.00%) |
| | | Timestamp standard | UTC ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`) |
| | | Day of Week Distribution | Weekend elevated: Mon (411), Tue (410), Wed (467), Thu (472), Fri (503), Sat (607), Sun (630) |
| **`events`** | 15,000 | Orphaned `user_id` | 172 rows (1.15%) |
| | | Funnel progression | `page_view` (11,997), `add_to_cart` (2,422), `purchase` (581) |
| | | Timestamp standard | Local time (`YYYY-MM-DD HH:MM:SS`), unadjusted for UTC |

\* *Data spec note: The 1.09% negative/zero order rate resulted from an intentional interaction between the base entry glitch generator (28 rows / 0.80%) and duplicate retry cancellations setting order_value to $0.00 (10 rows).*

---

## Setup Instructions

### 1. Environment Setup

Create and activate the dedicated Conda environment:

```bash
# Create conda environment from specification
conda env create -f environment.yml

# Activate environment
conda activate analytics-pipeline
```

Alternatively, install dependencies via `pip`:

```bash
pip install dbt-postgres psycopg2-binary sqlfluff Faker pytest pyyaml
```

### 2. Database & Raw Data Ingestion

Ensure PostgreSQL is running locally, then initialize the database and load the raw CSV files:

```bash
python load_raw_data.py
```

Connection parameters can be customized via environment variables (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`).

### 3. Verify Connection

```bash
dbt debug --profiles-dir .
```

---

## Running the Pipeline

Execute the full transformation pipeline and test suite:

```bash
# Build all staging, intermediate, and marts models and execute tests
dbt build --profiles-dir .

# Run models only
dbt run --profiles-dir .

# Execute data quality test suite only (62 tests)
dbt test --profiles-dir .

# Lint SQL models against style rules
sqlfluff lint models/
```

### Generating and Viewing dbt Documentation

```bash
# Generate documentation catalog and lineage graphs
dbt docs generate --profiles-dir .

# Serve documentation locally on http://localhost:8080
dbt docs serve
```

---

## Testing Strategy

The test suite enforces 62 data validation tests defined in [`TEST_PLAN.md`](TEST_PLAN.md):

1. **Staging Layer (19 generic tests):**
   - Primary key uniqueness and not-null constraints on `stg_users.user_id`, `stg_orders.order_id`, and `stg_events.event_id`.
   - Not-null validation on downstream dependencies (`signup_date`, `order_date`, `session_id`, `event_at`).
   - Missing fields allowed by design (`country`) are intentionally not asserted as not-null.
2. **Intermediate Layer (23 generic + 2 custom singular tests):**
   - [`tests/test_session_duration_24h.sql`](tests/test_session_duration_24h.sql): Asserts session duration in `int_sessionized_events` is non-negative and $\le 86,400$ seconds (24 hours).
   - [`tests/test_first_purchase_after_signup.sql`](tests/test_first_purchase_after_signup.sql): Asserts that `first_purchase_date` in `int_user_first_purchase` is never earlier than the customer's `signup_date`.
3. **Marts Layer (15 generic + 3 custom singular tests):**
   - [`tests/test_revenue_non_negative.sql`](tests/test_revenue_non_negative.sql): Asserts `total_revenue` and `average_order_value` in `fct_revenue_trends` are non-negative.
   - [`tests/test_retention_percentage_range.sql`](tests/test_retention_percentage_range.sql): Asserts `retention_pct` in `monthly_cohort_retention` falls within $[0.00, 100.00]\%$.
   - [`tests/test_funnel_monotonic.sql`](tests/test_funnel_monotonic.sql): Asserts conversion counts are monotonically non-increasing ($\text{purchases} \le \text{cart additions} \le \text{page views}$).
   - `accepted_values` on `funnel_summary.funnel_step` (`['page_view', 'add_to_cart', 'purchase']`).

---

## Automation & CI/CD

- **GitHub Actions CI Workflow ([`.github/workflows/dbt_ci.yml`](.github/workflows/dbt_ci.yml)):**
  - Triggers on every `push` and `pull_request` to `main`/`master`.
  - Spins up a clean PostgreSQL 16 service container.
  - Ingests raw data via `load_raw_data.py`.
  - Executes `dbt debug`, `dbt build`, and `sqlfluff lint models/`.
- **Nightly Scheduled Workflow ([`.github/workflows/dbt_scheduled.yml`](.github/workflows/dbt_scheduled.yml)):**
  - Triggers automatically via cron daily at 05:00 UTC (`0 5 * * *`).
  - Re-executes the transformation build and test assertions unattended.

---

## Key Data Findings

Key metrics extracted directly from the marts tables:

1. **Conversion Funnel Metrics (`funnel_summary`):**
   - **Top-of-Funnel Sessions:** 4,672 visitor sessions.
   - **Add-to-Cart Conversion:** 1,512 sessions added items to cart (32.36% step conversion rate).
   - **Purchase Checkout Conversion:** 581 sessions completed an order (38.43% step conversion from cart; 12.44% overall conversion from page view).
2. **Cohort Retention Patterns (`monthly_cohort_retention`):**
   - January 2023 Cohort ($N = 124$): Month 0 retention is 41.13%, rising to a repeat purchase peak of 61.29% in Month 1, gradually tapering to 36.29% in Month 3, 25.00% in Month 4, and 4.03% by Month 8.
3. **Revenue Trends & Incremental Scaling (`fct_revenue_trends`):**
   - Daily gross revenue shows steady baseline performance with elevated transaction volume on weekends (Saturday/Sunday averaging 17.3% and 18.0% of weekly volume) and Q4 holiday peaks.

---

## BI Dashboard (Metabase)

*(Placeholder for Phase 9: Metabase connection details, queries, and dashboard screenshots).*

---

## Maintenance Flow Demonstration

*(Placeholder for Phase 10: Live proof demonstrating schema modification isolation in the staging layer).*

---

## Project Documentation & Guidelines

- [`CONVENTIONS.md`](CONVENTIONS.md) — SQL style rules, naming standards, and architectural conventions.
- [`DATA_SPEC.md`](DATA_SPEC.md) — Raw synthetic data schema, messiness rates, and distribution guidelines.
- [`TEST_PLAN.md`](TEST_PLAN.md) — Testing philosophy and validation bounds across layers.
- [`Plan.md`](Plan.md) — Complete 11-phase project execution roadmap.
