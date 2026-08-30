/*
Asserts session duration is between 0 and 86,400 seconds.
If a session lasts more than 24 hours, either the user fell asleep at their desk or tracking broke.
*/

select
    session_id,
    user_id,
    session_start_at,
    session_end_at,
    session_duration_seconds
from {{ ref('int_sessionized_events') }}
where session_duration_seconds > 86400
   or session_duration_seconds < 0
