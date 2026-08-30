/*
Asserts funnel conversion counts are monotonically non-increasing:
purchase_sessions <= cart_sessions <= page_view_sessions.
*/

with funnel_steps as (
    select
        max(case when funnel_step = 'page_view' then session_count end) as page_view_sessions,
        max(case when funnel_step = 'add_to_cart' then session_count end) as cart_sessions,
        max(case when funnel_step = 'purchase' then session_count end) as purchase_sessions
    from {{ ref('funnel_summary') }}
)

select
    page_view_sessions,
    cart_sessions,
    purchase_sessions
from funnel_steps
where cart_sessions > page_view_sessions
   or purchase_sessions > cart_sessions
