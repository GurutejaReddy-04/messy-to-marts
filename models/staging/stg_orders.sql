/*
Staging: Orders

Cleaning logic:
- Resolve duplicate retry submissions by favoring completed status and latest attempt.
- Filter non-positive order values (entry glitches / zero-dollar test stubs).
- Preserve unmapped user_ids so downstream models can account for late-arriving accounts.
*/

with raw_orders as (
    select
        order_id,
        user_id,
        order_date,
        -- Adapt to upstream raw column rename (order_amount -> order_value)
        order_amount as order_value,
        order_status
    from {{ source('raw', 'orders') }}
),

parsed_orders as (
    select
        order_id,
        user_id,
        order_date::timestamp as ordered_at,
        order_date::date as order_date,
        order_value,
        lower(trim(order_status)) as order_status
    from raw_orders
    where order_value > 0
),

deduplicated_orders as (
    select
        order_id,
        user_id,
        ordered_at,
        order_date,
        order_value,
        order_status,
        row_number() over (
            partition by order_id
            order by
                case when order_status = 'completed' then 1 else 2 end asc,
                ordered_at desc,
                order_value desc
        ) as order_attempt_rank
    from parsed_orders
)

select
    order_id,
    user_id,
    ordered_at,
    order_date,
    order_value,
    order_status
from deduplicated_orders
where order_attempt_rank = 1
