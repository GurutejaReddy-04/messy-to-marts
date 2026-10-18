/*
Asserts that fct_revenue_trends exactly matches all completed order aggregates from stg_orders.
Returns any dates where the mart's total_revenue, order_count, distinct_user_count, or
average_order_value differs from completed order aggregates.
Zero-completed order dates in the mart are reconciled against 0.00 expected revenue, 0 expected orders,
0 distinct users, and 0.00 average order value.
*/

with completed_orders_daily as (
    select
        order_date,
        round(sum(order_value), 2) as expected_revenue,
        count(order_id) as expected_order_count,
        count(distinct user_id) as expected_distinct_user_count,
        coalesce(round(avg(order_value), 2), 0.00) as expected_average_order_value
    from {{ ref('stg_orders') }}
    where order_status = 'completed'
    group by
        order_date
),

mart_daily as (
    select
        order_date,
        total_revenue,
        order_count,
        distinct_user_count,
        average_order_value
    from {{ ref('fct_revenue_trends') }}
),

all_dates as (
    select order_date from mart_daily
    union
    select order_date from completed_orders_daily
),

reconciled_daily as (
    select
        all_dates.order_date,
        coalesce(mart.total_revenue, 0.00) as total_revenue,
        coalesce(expected.expected_revenue, 0.00) as expected_revenue,
        coalesce(mart.order_count, 0) as order_count,
        coalesce(expected.expected_order_count, 0) as expected_order_count,
        coalesce(mart.distinct_user_count, 0) as distinct_user_count,
        coalesce(expected.expected_distinct_user_count, 0) as expected_distinct_user_count,
        coalesce(mart.average_order_value, 0.00) as average_order_value,
        coalesce(expected.expected_average_order_value, 0.00) as expected_average_order_value
    from all_dates
    left join mart_daily as mart
        on all_dates.order_date = mart.order_date
    left join completed_orders_daily as expected
        on all_dates.order_date = expected.order_date
),

mismatches as (
    select
        order_date,
        total_revenue,
        expected_revenue,
        order_count,
        expected_order_count,
        distinct_user_count,
        expected_distinct_user_count,
        average_order_value,
        expected_average_order_value
    from reconciled_daily
    where
        total_revenue != expected_revenue
        or order_count != expected_order_count
        or distinct_user_count != expected_distinct_user_count
        or average_order_value != expected_average_order_value
)

select
    order_date,
    total_revenue,
    expected_revenue,
    order_count,
    expected_order_count,
    distinct_user_count,
    expected_distinct_user_count,
    average_order_value,
    expected_average_order_value
from mismatches
