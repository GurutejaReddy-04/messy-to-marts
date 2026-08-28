/*
Intermediate model computing initial purchase conversion and customer order aggregations.

Business rationale:
- Computes each customer's first purchase timestamp and date to serve as the baseline
  for downstream cohort retention modeling in the marts layer.
- Enriches user dimension with lifetime order counts and lifetime gross merchandise value (GMV).
- Inner joins to stg_users to anchor metrics to validated user accounts, naturally isolating
  orphaned raw orders until account resolution occurs.
*/

with users as (
    select
        user_id,
        signup_at,
        signup_date
    from {{ ref('stg_users') }}
),

orders as (
    select
        order_id,
        user_id,
        ordered_at,
        order_date,
        order_value,
        order_status
    from {{ ref('stg_orders') }}
),

user_orders_ranked as (
    select
        user_id,
        order_id,
        ordered_at,
        order_date,
        order_value,
        -- Rank orders chronologically to isolate the first purchase event
        row_number() over (
            partition by user_id
            order by
                ordered_at asc,
                order_id asc
        ) as order_sequence_number
    from orders
),

user_order_aggregates as (
    select
        user_id,
        count(order_id) as total_orders_count,
        sum(order_value) as total_lifetime_value,
        min(ordered_at) as first_purchase_at,
        min(order_date) as first_purchase_date
    from orders
    group by
        user_id
),

first_orders as (
    select
        user_id,
        order_id as first_purchase_order_id,
        order_value as first_purchase_value
    from user_orders_ranked
    where order_sequence_number = 1
),

joined_user_purchase_metrics as (
    select
        users.user_id,
        users.signup_at,
        users.signup_date,
        aggregates.first_purchase_at,
        aggregates.first_purchase_date,
        first_orders.first_purchase_order_id,
        first_orders.first_purchase_value,
        coalesce(aggregates.total_orders_count, 0) as total_orders_count,
        coalesce(aggregates.total_lifetime_value, 0.00) as total_lifetime_value,
        aggregates.first_purchase_at is not null as has_purchased
    from users
    left join user_order_aggregates as aggregates
        on users.user_id = aggregates.user_id
    left join first_orders
        on users.user_id = first_orders.user_id
)

select
    user_id,
    signup_at,
    signup_date,
    first_purchase_at,
    first_purchase_date,
    first_purchase_order_id,
    first_purchase_value,
    total_orders_count,
    total_lifetime_value,
    has_purchased
from joined_user_purchase_metrics
