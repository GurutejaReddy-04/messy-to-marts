/*
Staging model for clickstream web behavioral events.

Cleaning & Transformation strategy:
- Raw events timestamps are stored in local client time without UTC normalization.
  This creates an intentional timezone mismatch with raw orders (UTC) that must be handled
  in downstream sessionization and attribution modeling.
- Records missing user_id or session_id are filtered out to protect downstream sessionization.
- Clean snake_case column names and standardized timestamps are projected.
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
        -- Note: event_timestamp is recorded in local time (unadjusted for UTC),
        -- which contrasts with raw orders recorded in UTC ISO 8601.
        event_timestamp::timestamp as event_at,
        event_timestamp::date as event_date,
        lower(trim(device_type)) as device_type,
        page_url
    from raw_events
    -- Guard against malformed tracking events missing user or session identifiers
    where user_id is not null
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
