/*
Custom singular test: test_session_duration_24h

Validation rule:
- Asserts that session duration calculated in int_sessionized_events never exceeds
  a sane upper bound of 24 hours (86,400 seconds) and is non-negative.
- Catches sessionization logic bugs, inverted timestamps, or cross-session timestamp contamination.
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
