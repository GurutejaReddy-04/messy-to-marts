{{
    config(
        materialized='incremental',
        unique_key='order_date',
        incremental_strategy='merge'
    )
}}

/*
Incremental Fact Mart: fct_revenue_trends

Business rationale:
- Aggregates daily transactional gross revenue, transaction counts, active purchasing customer counts,
  and average order value (AOV) over time.
- Configured as an incremental model using a merge strategy on 'order_date' to avoid full table rebuilds
  as new transactional batches arrive, demonstrating production data engineering scalability.
*/

with orders as (
    select
        order_id,
        user_id,
        order_date,
        order_value,
        order_status
    from {{ ref('stg_orders') }}
    {% if is_incremental() %}
    -- Incrementally process only dates that meet or exceed the highest date in the existing fact table
    where order_date >= (select max(order_date) from {{ this }})
    {% endif %}
),

daily_revenue_aggregated as (
    select
        order_date,
        round(sum(order_value), 2) as total_revenue,
        count(order_id) as order_count,
        count(distinct user_id) as distinct_user_count,
        round(avg(order_value), 2) as average_order_value
    from orders
    group by
        order_date
)

select
    order_date,
    total_revenue,
    order_count,
    distinct_user_count,
    average_order_value
from daily_revenue_aggregated
