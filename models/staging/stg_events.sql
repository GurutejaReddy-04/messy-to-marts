/*
Staging: Clickstream Events

Cleaning logic:
- Raw timestamps are recorded in local client time (unadjusted for UTC).
- Discard tracking pings missing user_id or session_id.
*/

with raw_events as (
    select
        event_id,
        user_id,
        session_id,
        event_name,
        event_timestamp,
        device_type,
        page_url
    from {{ source('raw', 'events') }}
),

staged_events as (
    select
        event_id,
        user_id,
        session_id,
        lower(trim(event_name)) as event_name,
        -- Local time formatting mismatch against UTC orders preserved intentionally
        event_timestamp::timestamp as event_at,
        event_timestamp::date as event_date,
        lower(trim(device_type)) as device_type,
        page_url
    from raw_events
    where
        user_id is not null
        and session_id is not null
)

select
    event_id,
    user_id,
    session_id,
    event_name,
    event_at,
    event_date,
    device_type,
    page_url
from staged_events
