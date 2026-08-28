{{
    config(
        materialized='incremental',
        unique_key='order_date',
        incremental_strategy='merge'
    )
}}

/*
Marts: Daily Revenue Fact Table (Incremental)

Business rationale:
- Daily revenue rollup with order count and AOV.
- Incremental merge avoids full table scans on every run.
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
        -- Only process new or updated dates
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
