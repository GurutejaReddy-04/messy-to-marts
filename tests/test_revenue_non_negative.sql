/*
Asserts daily total_revenue and average_order_value are non-negative.
*/

select
    order_date,
    total_revenue,
    average_order_value
from {{ ref('fct_revenue_trends') }}
where total_revenue < 0
   or average_order_value < 0
