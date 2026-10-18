/*
Marts: Monthly Cohort Retention

Business rationale:
- Track customer purchasing retention across monthly acquisition cohorts.
- Active is defined as placing >= 1 valid completed order in a given activity month.
- Generates a dense elapsed-month spine (months 0 to N) for observed periods, filling zero-activity months with 0.00%.
- Respects right-censoring: future unobserved months beyond the observation boundary are omitted.
*/

with user_cohorts as (
    select
        user_id,
        signup_date,
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

max_observation_month as (
    select
        greatest(
            coalesce((select max(cohort_month) from cohort_sizes), '1970-01-01'::date),
            coalesce((select max(date_trunc('month', order_date)::date) from {{ ref('stg_orders') }}), '1970-01-01'::date),
            coalesce((select max(date_trunc('month', signup_date)::date) from {{ ref('stg_users') }}), '1970-01-01'::date)
        ) as max_month
),

cohort_month_spine as (
    select
        cohort_sizes.cohort_month,
        cohort_sizes.cohort_size,
        spine.month_number,
        (cohort_sizes.cohort_month + (spine.month_number || ' month')::interval)::date as activity_month
    from cohort_sizes
    cross join max_observation_month
    cross join lateral generate_series(
        0,
        greatest(
            0,
            (
                (extract(year from max_observation_month.max_month) - extract(year from cohort_sizes.cohort_month)) * 12
                + (extract(month from max_observation_month.max_month) - extract(month from cohort_sizes.cohort_month))
            )::int
        )
    ) as spine (month_number)
),

user_activities as (
    select
        orders.user_id,
        user_cohorts.cohort_month,
        date_trunc('month', orders.order_date)::date as activity_month
    from {{ ref('stg_orders') }} as orders
    inner join user_cohorts
        on orders.user_id = user_cohorts.user_id
    where orders.order_status = 'completed'
    group by
        orders.user_id,
        user_cohorts.cohort_month,
        date_trunc('month', orders.order_date)::date
),

cohort_activity_aggregated as (
    select
        cohort_month,
        activity_month,
        count(distinct user_id) as active_users
    from user_activities
    group by
        cohort_month,
        activity_month
),

cohort_retention_joined as (
    select
        cohort_month_spine.cohort_month,
        cohort_month_spine.cohort_size,
        cohort_month_spine.month_number,
        coalesce(cohort_activity_aggregated.active_users, 0) as active_users,
        round(
            (coalesce(cohort_activity_aggregated.active_users, 0)::numeric / cohort_month_spine.cohort_size::numeric) * 100.0,
            2
        ) as retention_pct
    from cohort_month_spine
    left join cohort_activity_aggregated
        on
            cohort_month_spine.cohort_month = cohort_activity_aggregated.cohort_month
            and cohort_month_spine.activity_month = cohort_activity_aggregated.activity_month
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
