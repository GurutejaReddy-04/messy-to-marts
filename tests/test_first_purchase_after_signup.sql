/*
Asserts first_purchase_date is not earlier than signup_date.
Catches time-traveling purchases from clock drift or bad timezone casting.
*/

with first_purchases as (
    select
        user_id,
        first_purchase_date,
        first_purchase_at
    from {{ ref('int_user_first_purchase') }}
    where first_purchase_date is not null
),

users as (
    select
        user_id,
        signup_date,
        signup_at
    from {{ ref('stg_users') }}
),

invalid_first_purchases as (
    select
        first_purchases.user_id,
        users.signup_date,
        first_purchases.first_purchase_date,
        users.signup_at,
        first_purchases.first_purchase_at
    from first_purchases
    inner join users
        on first_purchases.user_id = users.user_id
    where first_purchases.first_purchase_date < users.signup_date
)

select
    user_id,
    signup_date,
    first_purchase_date,
    signup_at,
    first_purchase_at
from invalid_first_purchases
