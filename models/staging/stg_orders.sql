/*
Staging model for transactional orders.

Cleaning & Deduplication strategy:
- Raw orders contain ~1% conflicting duplicate order_ids caused by network retry/resend race condition bugs.
- We deduplicate order_ids by prioritizing 'completed' status, the latest timestamp, and highest order value.
- Negative and zero order_values (~1.09%) are filtered out as they represent entry glitches or invalid checkout cancellations.
- Orphaned user_ids (~1.46%) are intentionally preserved at staging so downstream fact models can track late-arriving dimensions.
- Timestamps are cast from ISO 8601 UTC strings to standard timestamp and date fields.
*/

with raw_orders as (
    select
        order_id,
        user_id,
        order_date,
        order_value,
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
    -- Filter out transaction entry glitches and non-positive order values
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
        -- Prioritize completed status and latest attempt for duplicate order retry submissions
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
