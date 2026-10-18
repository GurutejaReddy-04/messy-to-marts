/*
Asserts that all initial purchases in int_user_first_purchase reference valid 'completed' orders.
Catches any leakage of pending, cancelled, or returned orders into first-purchase metrics.
*/

with first_purchases as (
    select
        user_id,
        first_purchase_order_id,
        first_purchase_at,
        first_purchase_value
    from {{ ref('int_user_first_purchase') }}
    where has_purchased = true
),

orders as (
    select
        order_id,
        order_status
    from {{ ref('stg_orders') }}
),

invalid_first_purchases as (
    select
        first_purchases.user_id,
        first_purchases.first_purchase_order_id,
        first_purchases.first_purchase_at,
        first_purchases.first_purchase_value,
        orders.order_status
    from first_purchases
    inner join orders
        on first_purchases.first_purchase_order_id = orders.order_id
    where orders.order_status != 'completed'
)

select
    user_id,
    first_purchase_order_id,
    first_purchase_at,
    first_purchase_value,
    order_status
from invalid_first_purchases
