{{
    config(
        materialized='incremental',
        unique_key='order_date',
        incremental_strategy='merge'
    )
}}

/*
Marts: Daily Revenue Fact Table (Incremental)
Rolls up daily revenue, order count, and AOV for completed orders.
Uses a rolling lookback window to absorb late-arriving orders and reconciles
dates where all orders have been cancelled, refunded, or deleted back to zero.

Operational deletion handling:
- Deletions within lookback window (default 7 days): dates_in_scope unions dates from {{ this }}
  with stg_orders, ensuring dates whose source records were completely removed are reprocessed
  and updated to 0.00 revenue and 0 orders.
- Historical deletions older than the lookback SLA: repaired via full refresh backfill
  (dbt run --full-refresh --select fct_revenue_trends).
*/

{% set lookback_days = var('revenue_lookback_days', 7) %}

with target_lookback as (
    {% if is_incremental() %}
        select (coalesce(max(order_date), '1970-01-01'::date) - interval '{{ lookback_days }} days')::date as lookback_start_date
        from {{ this }}
    {% else %}
        select '1970-01-01'::date as lookback_start_date
    {% endif %}
),

dates_in_scope as (
    select distinct order_date
    from {{ ref('stg_orders') }}
    {% if is_incremental() %}
        where order_date >= (select lookback_start_date from target_lookback)
        union
        select distinct order_date
        from {{ this }}
        where order_date >= (select lookback_start_date from target_lookback)
    {% endif %}
),

completed_orders as (
    select
        order_id,
        user_id,
        order_date,
        order_value
    from {{ ref('stg_orders') }}
    where
        order_status = 'completed'
        {% if is_incremental() %}
            and order_date >= (select lookback_start_date from target_lookback)
        {% endif %}
),

daily_revenue_aggregated as (
    select
        d.order_date,
        coalesce(round(sum(c.order_value), 2), 0.00) as total_revenue,
        count(c.order_id) as order_count,
        count(distinct c.user_id) as distinct_user_count,
        coalesce(round(avg(c.order_value), 2), 0.00) as average_order_value
    from dates_in_scope as d
    left join completed_orders as c
        on d.order_date = c.order_date
    group by
        d.order_date
)

select
    order_date,
    total_revenue,
    order_count,
    distinct_user_count,
    average_order_value
from daily_revenue_aggregated
