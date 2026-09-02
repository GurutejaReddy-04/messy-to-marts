# Synthetic Raw Data Specification

Goal: messiness that looks like it came from years of real user behavior and system quirks, not a uniform random injector. Vary the *rate* and *pattern* of each issue — do not apply the same messiness rule identically to every affected row.

## users table
- ~500-2,000 rows (pick one, note it in README)
- 3-6% of users have a typo-variant duplicate elsewhere in the table (a second row, different user_id, near-identical but not identical email — e.g., missing letter, swapped letters, different domain typo like `gmial.com`). Vary the typo type across duplicates — don't use the same typo pattern every time.
- 1-2% of rows have a null `signup_date` or null `country`
- Signup dates should cluster realistically (e.g., more signups in some months than others — not uniform distribution across the whole range)

## orders table
- 1-2% of orders reference a `user_id` that doesn't exist yet in `users` at load time (simulates late-arriving dimension / event ordering issues)
- 0.5-1% of orders have negative or zero `order_value` (data entry errors)
- A small number (~1%) of duplicate `order_id`s with conflicting values (simulates a retry/re-send bug) — these should NOT all look identical; vary which fields differ between the duplicate pair
- Timestamps stored in UTC, ISO 8601 format
- Order volume should show some realistic pattern (e.g., weekday vs weekend variation, or a seasonal bump) rather than flat random distribution

## events table
- Timestamps stored in **local time, not UTC** — this mismatch with `orders` is intentional and should be called out explicitly in the staging model comments
- Event types: `page_view`, `add_to_cart`, `purchase` (at minimum) — with a realistic funnel drop-off between each (i.e., far more page_views than add_to_cart, far more add_to_cart than purchase — don't make the funnel artificially even)
- Some sessions should have no purchase event at all; some should have multiple add_to_cart events before one purchase
- A small fraction (~1%) of events reference a `user_id` not present in `users`

## General rules
- Do not use the same random seed logic to generate every issue — vary rates and patterns per field so nothing looks templated when someone inspects row counts.
- Document the exact rates and row counts used in the README once generation is final, so any inspector can verify the messiness was intentional and non-trivial, not accidental.
