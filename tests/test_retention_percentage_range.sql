/*
Custom singular test: test_retention_percentage_range

Validation rule:
- Asserts that retention_pct in monthly_cohort_retention strictly falls between 0 and 100 inclusive.
- Catches cohort calculation bugs, duplicate active user counts, or ratio formula invert errors.
*/

select
    cohort_month,
    cohort_size,
    month_number,
    active_users,
    retention_pct
from {{ ref('monthly_cohort_retention') }}
where retention_pct < 0.00
   or retention_pct > 100.00
