/*
Asserts that monthly_cohort_retention includes all observed cohorts from month 0
up to the maximum observed dataset horizon without missing elapsed months.
Catches regressions where cohorts later than the latest completed order are dropped,
or where months with orders but zero completed orders are omitted from the spine.
*/

with dataset_horizon as (
    select
        greatest(
            coalesce((select max(date_trunc('month', signup_date)::date) from {{ ref('stg_users') }}), '1970-01-01'::date),
            coalesce((select max(date_trunc('month', order_date)::date) from {{ ref('stg_orders') }}), '1970-01-01'::date)
        ) as max_month
),

cohort_expected as (
    select
        date_trunc('month', signup_date)::date as cohort_month,
        greatest(
            0,
            (
                (extract(year from dataset_horizon.max_month) - extract(year from date_trunc('month', signup_date)::date)) * 12
                + (extract(month from dataset_horizon.max_month) - extract(month from date_trunc('month', signup_date)::date))
            )::int
        ) as expected_max_month_number,
        greatest(
            0,
            (
                (extract(year from dataset_horizon.max_month) - extract(year from date_trunc('month', signup_date)::date)) * 12
                + (extract(month from dataset_horizon.max_month) - extract(month from date_trunc('month', signup_date)::date))
            )::int
        ) + 1 as expected_row_count
    from {{ ref('stg_users') }}
    cross join dataset_horizon
    group by
        date_trunc('month', signup_date)::date,
        dataset_horizon.max_month
),

cohort_actual as (
    select
        cohort_month,
        max(month_number) as actual_max_month_number,
        count(*) as actual_row_count,
        min(month_number) as min_month_number
    from {{ ref('monthly_cohort_retention') }}
    group by
        cohort_month
)

select
    cohort_expected.cohort_month,
    cohort_expected.expected_max_month_number,
    cohort_actual.actual_max_month_number,
    cohort_expected.expected_row_count,
    cohort_actual.actual_row_count,
    cohort_actual.min_month_number
from cohort_expected
left join cohort_actual
    on cohort_expected.cohort_month = cohort_actual.cohort_month
where
    cohort_actual.cohort_month is null
    or cohort_actual.min_month_number != 0
    or cohort_actual.actual_max_month_number != cohort_expected.expected_max_month_number
    or cohort_actual.actual_row_count != cohort_expected.expected_row_count
