/*
Staging: User Accounts

Cleaning logic:
- People struggle to spell 'gmail' and 'yahoo'. Strip dots from local-part and fix common domain typos.
- Retain the earliest valid registration per individual (rank = 1).
- Drop rows missing signup_date (cannot cohort un-dated users). Country nulls are kept as-is.
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
        -- Standardize domain typos and strip local-part dots
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
        row_number() over (
            partition by normalized_email
            order by
                signup_at asc nulls last,
                user_id asc
        ) as user_account_rank
    from normalized_users
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
