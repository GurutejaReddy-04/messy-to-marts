# Test Plan

Only test things that could plausibly break or matter for trust in the numbers. Do not add a test to every column — that reads as auto-generated coverage-maximizing, not intentional QA thinking.

## Staging layer
- `unique` + `not_null` on primary keys (`user_id`, `order_id`) — standard, expected
- `not_null` on fields the pipeline depends on downstream (e.g., `signup_date` in stg_users, since cohorting depends on it)
- No test needed on fields nothing downstream depends on (e.g., a raw notes/comment field, if one exists) — explicitly skip these and note why in schema.yml if asked

## Intermediate layer
- Custom test: session duration never exceeds a sane bound (e.g., 24 hours) — catches sessionization logic bugs
- Custom test: `first_purchase_date` is never earlier than `signup_date` — catches join/logic errors

## Marts layer
- `accepted_values` on any categorical/status field (e.g., funnel step names)
- Custom test: `revenue_trends.total_revenue` is never negative
- Custom test: `monthly_cohort_retention.retention_pct` is always between 0 and 100
- Custom test: `funnel_summary` conversion rates are monotonically non-increasing across funnel steps (can't have more purchases than add-to-carts)

## What NOT to test
- Don't add `not_null` tests on optional/nullable-by-design fields (e.g., `country` if it's allowed to be missing) — that's testing against the data spec itself
- Don't duplicate the same uniqueness test at multiple layers if it's already guaranteed upstream

## Proof point for README
- Deliberately break one test once (e.g., temporarily allow a negative revenue value through) and show the CI run failing, then fix it and show it passing. Screenshot both. This is stronger evidence of real testing than a passing test suite alone.
