/*
Intermediate: Sessionized Clickstream Events

Business rationale:
- Collapse raw event pings into distinct user sessions.
- Compute session duration and deepest funnel milestone achieved.
*/

with events as (
    select
        event_id,
        user_id,
        session_id,
        event_name,
        event_at,
        event_date,
        device_type,
        page_url
    from {{ ref('stg_events') }}
),

session_aggregates as (
    select
        session_id,
        user_id,
        min(device_type) as device_type,
        min(event_at) as session_start_at,
        max(event_at) as session_end_at,
        min(event_date) as session_date,
        count(event_id) as total_events_count,
        sum(case when event_name = 'page_view' then 1 else 0 end) as page_view_count,
        sum(case when event_name = 'add_to_cart' then 1 else 0 end) as add_to_cart_count,
        sum(case when event_name = 'purchase' then 1 else 0 end) as purchase_count
    from events
    group by
        session_id,
        user_id
),

session_metrics as (
    select
        session_id,
        user_id,
        device_type,
        session_date,
        session_start_at,
        session_end_at,
        extract(epoch from (session_end_at - session_start_at))::int as session_duration_seconds,
        total_events_count,
        page_view_count,
        add_to_cart_count,
        purchase_count,
        add_to_cart_count > 0 as has_cart_add,
        purchase_count > 0 as has_purchase,
        case
            when purchase_count > 0 then 'purchase'
            when add_to_cart_count > 0 then 'add_to_cart'
            else 'page_view'
        end as furthest_funnel_step
    from session_aggregates
)

select
    session_id,
    user_id,
    device_type,
    session_date,
    session_start_at,
    session_end_at,
    session_duration_seconds,
    total_events_count,
    page_view_count,
    add_to_cart_count,
    purchase_count,
    has_cart_add,
    has_purchase,
    furthest_funnel_step
from session_metrics
