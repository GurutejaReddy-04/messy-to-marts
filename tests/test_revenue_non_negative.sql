/*
Custom singular test: test_revenue_non_negative

Validation rule:
- Asserts that daily total_revenue and average_order_value in fct_revenue_trends are never negative.
- Catches accidental inclusion of negative order glitches, improper refunds, or aggregation errors.
*/

select
    order_date,
    total_revenue,
    average_order_value
from {{ ref('fct_revenue_trends') }}
where total_revenue < 0
   or average_order_value < 0
