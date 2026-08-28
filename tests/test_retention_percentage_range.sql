/*
Asserts retention_pct strictly falls within [0.00, 100.00]%.
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
