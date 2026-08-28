/*
Mart model computing monthly user cohort retention.

Business rationale:
- Groups users into monthly acquisition cohorts based on their initial signup date.
- Tracks repeat purchasing activity over subsequent calendar months (month 0, month 1, month 2...).
- Calculates the percentage of cohort customers remaining active in each period,
  answering core business questions regarding product retention curves and customer lifecycle decay.
*/

with user_cohorts as (
    select
        user_id,
        signup_date,
        -- Truncate registration date to first day of signup month
        date_trunc('month', signup_date)::date as cohort_month
    from {{ ref('int_user_first_purchase') }}
),

cohort_sizes as (
    select
        cohort_month,
        count(distinct user_id) as cohort_size
    from user_cohorts
    group by
        cohort_month
),

user_activities as (
    select
        orders.user_id,
        user_cohorts.cohort_month,
        date_trunc('month', orders.order_date)::date as activity_month
    from {{ ref('stg_orders') }} as orders
    inner join user_cohorts
        on orders.user_id = user_cohorts.user_id
    group by
        orders.user_id,
        user_cohorts.cohort_month,
        date_trunc('month', orders.order_date)::date
),

user_cohort_months as (
    select
        user_id,
        cohort_month,
        activity_month,
        -- Calculate elapsed months from cohort month to activity month
        (
            (extract(year from activity_month) - extract(year from cohort_month)) * 12
            + (extract(month from activity_month) - extract(month from cohort_month))
        )::int as month_number
    from user_activities
),

cohort_activity_aggregated as (
    select
        cohort_month,
        month_number,
        count(distinct user_id) as active_users
    from user_cohort_months
    where month_number >= 0
    group by
        cohort_month,
        month_number
),

cohort_retention_joined as (
    select
        cohort_activity_aggregated.cohort_month,
        cohort_sizes.cohort_size,
        cohort_activity_aggregated.month_number,
        cohort_activity_aggregated.active_users,
        -- Calculate retention rate as percentage of initial cohort size
        round(
            (cohort_activity_aggregated.active_users::numeric / cohort_sizes.cohort_size::numeric) * 100.0,
            2
        ) as retention_pct
    from cohort_activity_aggregated
    inner join cohort_sizes
        on cohort_activity_aggregated.cohort_month = cohort_sizes.cohort_month
)

select
    cohort_month,
    cohort_size,
    month_number,
    active_users,
    retention_pct
from cohort_retention_joined
order by
    cohort_month asc,
    month_number asc
