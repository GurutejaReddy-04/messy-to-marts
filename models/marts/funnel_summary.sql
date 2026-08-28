/*
Mart model computing website conversion funnel metrics.

Business rationale:
- Measures traffic conversion progression across key visitor journey milestones:
  Step 1 (Page Views) -> Step 2 (Add to Cart) -> Step 3 (Purchase Checkout).
- Calculates both step-to-step conversion efficiencies and top-of-funnel overall conversion rates
  to highlight drop-off bottlenecks in the user purchase flow.
*/

with session_base as (
    select
        session_id,
        has_cart_add,
        has_purchase
    from {{ ref('int_sessionized_events') }}
),

funnel_counts as (
    select
        count(session_id) as total_page_view_sessions,
        count(session_id) filter (where has_cart_add = true) as total_cart_sessions,
        count(session_id) filter (where has_purchase = true) as total_purchase_sessions
    from session_base
),

unpivoted_funnel as (
    select
        1 as funnel_step_order,
        'page_view' as funnel_step,
        total_page_view_sessions as session_count,
        total_page_view_sessions as previous_step_count,
        total_page_view_sessions as top_step_count
    from funnel_counts

    union all

    select
        2 as funnel_step_order,
        'add_to_cart' as funnel_step,
        total_cart_sessions as session_count,
        total_page_view_sessions as previous_step_count,
        total_page_view_sessions as top_step_count
    from funnel_counts

    union all

    select
        3 as funnel_step_order,
        'purchase' as funnel_step,
        total_purchase_sessions as session_count,
        total_cart_sessions as previous_step_count,
        total_page_view_sessions as top_step_count
    from funnel_counts
),

funnel_metrics as (
    select
        funnel_step_order,
        funnel_step,
        session_count,
        -- Step-over-step conversion efficiency
        round(
            case
                when previous_step_count = 0 then 0.00
                else (session_count::numeric / previous_step_count::numeric) * 100.0
            end,
            2
        ) as step_conversion_pct,
        -- Overall conversion relative to top-of-funnel visitors
        round(
            case
                when top_step_count = 0 then 0.00
                else (session_count::numeric / top_step_count::numeric) * 100.0
            end,
            2
        ) as overall_conversion_pct
    from unpivoted_funnel
)

select
    funnel_step_order,
    funnel_step,
    session_count,
    step_conversion_pct,
    overall_conversion_pct
from funnel_metrics
order by
    funnel_step_order asc
