/*
Staging model for user accounts.

Deduplication strategy:
- User registrations contain ~4% typo-variant duplicates where the same user re-signed up
  with dots omitted or domain typos (e.g. gmial.com, yaho.com).
- We normalize emails by stripping dots from the local part and standardizing domain typo variants.
- We partition by normalized email and retain the earliest registration record (user_account_rank = 1).
- Un-cohortable rows missing signup_date (~1.5%) are filtered out since downstream retention models require valid signup cohorts.
- Missing country values are preserved as NULL because country is optional and nullable by design.
*/

with raw_users as (
    select
        user_id,
        first_name,
        last_name,
        lower(trim(email)) as raw_email,
        country,
        signup_date
    from {{ source('raw', 'users') }}
),

normalized_users as (
    select
        user_id,
        first_name,
        last_name,
        raw_email,
        -- Standardize known domain typos and remove dot variations in local email part
        case
            when split_part(raw_email, '@', 2) in ('gmial.com', 'gmai.com', 'gamil.com')
                then split_part(replace(raw_email, '.', ''), '@', 1) || '@gmail.com'
            when split_part(raw_email, '@', 2) in ('yaho.com', 'yahooo.com', 'yaho.co')
                then split_part(replace(raw_email, '.', ''), '@', 1) || '@yahoo.com'
            when split_part(raw_email, '@', 2) in ('hotmial.com', 'hotmal.com')
                then split_part(replace(raw_email, '.', ''), '@', 1) || '@hotmail.com'
            when split_part(raw_email, '@', 2) in ('outlok.com', 'outlookk.com')
                then split_part(replace(raw_email, '.', ''), '@', 1) || '@outlook.com'
            else replace(split_part(raw_email, '@', 1), '.', '') || '@' || split_part(raw_email, '@', 2)
        end as normalized_email,
        nullif(trim(country), '') as country,
        nullif(trim(signup_date), '')::timestamp as signup_at,
        nullif(trim(signup_date), '')::date as signup_date
    from raw_users
),

deduplicated_users as (
    select
        user_id,
        first_name,
        last_name,
        raw_email as email,
        normalized_email,
        country,
        signup_at,
        signup_date,
        -- Prioritize the earliest signup timestamp for duplicate registrations
        row_number() over (
            partition by normalized_email
            order by
                signup_at asc nulls last,
                user_id asc
        ) as user_account_rank
    from normalized_users
    -- Filter out un-cohortable records missing signup date
    where signup_date is not null
)

select
    user_id,
    first_name,
    last_name,
    email,
    country,
    signup_at,
    signup_date
from deduplicated_users
where user_account_rank = 1
