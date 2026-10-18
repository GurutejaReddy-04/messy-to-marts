"""Synthetic orders data generator with deliberate real-world messiness.

Implements:
- 1.5% orphaned user_id (simulating late-arriving dimension records)
- 0.8% negative or zero order_value (simulating transaction entry glitches)
- 1.0% conflicting duplicate order_id records with varied field mismatches (retry bugs)
- Realistic order volume distribution (weekday/weekend variations and Q4 holiday surge)
- Timestamps stored in standard UTC ISO 8601 format
"""

import math
import random
from datetime import datetime, timedelta

import config



def generate_clustered_order_timestamp(
    user_signup_str: str,
    random_instance: random.Random,
) -> datetime:
    """Generate an order timestamp occurring after user signup with realistic seasonal and weekend weighting."""
    start_bound = datetime.strptime(config.START_DATE, "%Y-%m-%d")
    max_end_dt = datetime.strptime(config.END_DATE, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    if user_signup_str:
        user_signup_dt = datetime.strptime(user_signup_str, "%Y-%m-%d %H:%M:%S")
        earliest_date = user_signup_dt.date()
    else:
        user_signup_dt = None
        earliest_date = start_bound.date()

    latest_date = max_end_dt.date()
    available_days = max(1, (latest_date - earliest_date).days + 1)

    candidate_days = [earliest_date + timedelta(days=day_idx) for day_idx in range(available_days)]

    day_weights: list[float] = []
    for day_idx, candidate_day in enumerate(candidate_days):
        recency_weight = math.exp(-day_idx / 75.0)
        dow_weight = config.DAY_OF_WEEK_WEIGHTS[candidate_day.weekday()]
        seasonal_weight = config.MONTHLY_SEASONAL_WEIGHTS[candidate_day.month - 1]
        day_weights.append(recency_weight * dow_weight * seasonal_weight)

    chosen_day = random_instance.choices(candidate_days, weights=day_weights, k=1)[0]

    hour = random_instance.choices(
        range(24),
        weights=[1, 1, 1, 1, 1, 2, 3, 5, 8, 9, 10, 10, 9, 9, 8, 8, 9, 10, 10, 9, 8, 6, 4, 2],
        k=1,
    )[0]
    minute = random_instance.randint(0, 59)
    second = random_instance.randint(0, 59)

    order_dt = datetime(chosen_day.year, chosen_day.month, chosen_day.day, hour, minute, second)
    if user_signup_dt:
        if user_signup_dt >= max_end_dt:
            raise ValueError(
                f"Cannot generate order timestamp after user signup '{user_signup_dt}' "
                f"within maximum bound '{max_end_dt}'. Order must occur strictly after signup."
            )
        remaining_seconds = int((max_end_dt - user_signup_dt).total_seconds())
        if order_dt <= user_signup_dt:
            add_seconds = random_instance.randint(1, min(3600, remaining_seconds))
            order_dt = user_signup_dt + timedelta(seconds=add_seconds)

    if order_dt > max_end_dt:
        order_dt = max_end_dt

    return order_dt


def generate_raw_orders(user_records: list[dict]) -> list[dict]:
    """Generate raw order records adhering to target volumes and deliberate messiness rules."""
    random_instance = random.Random(config.SEED_ORDERS)
    max_end_dt = datetime.strptime(config.END_DATE, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    total_target_count = config.TOTAL_ORDERS_TARGET
    duplicate_count = int(total_target_count * config.ORDER_CONFLICTING_DUPLICATE_RATE)
    base_order_count = total_target_count - duplicate_count

    # Identify existing valid base user IDs (strictly <= base_user_count, excluding typo duplicates and upper-bound signups)
    base_user_count = config.TOTAL_USERS_TARGET - int(config.TOTAL_USERS_TARGET * config.USER_TYPO_DUPLICATE_RATE)
    valid_user_ids = [
        int(u["user_id"])
        for u in user_records
        if int(u["user_id"]) <= base_user_count
        and not u.get("is_typo_duplicate", False)
        and (
            not u.get("signup_date")
            or datetime.strptime(u["signup_date"], "%Y-%m-%d %H:%M:%S") < max_end_dt
        )
    ]
    user_lookup = {int(u["user_id"]): u for u in user_records}

    # Generate pool of orphaned / non-existent user IDs (IDs well outside the range)
    orphaned_user_pool = list(range(9001, 9500))

    orphaned_count = int(base_order_count * config.ORDER_ORPHANED_USER_RATE)
    invalid_value_count = int(base_order_count * config.ORDER_INVALID_VALUE_RATE)

    order_records: list[dict] = []

    # Step 1: Generate primary base orders
    for order_index in range(1, base_order_count + 1):
        order_id = 10000 + order_index
        
        # Decide if this order is orphaned
        is_orphaned = order_index <= orphaned_count
        if is_orphaned:
            assigned_user_id = random_instance.choice(orphaned_user_pool)
            order_dt = generate_clustered_order_timestamp("", random_instance)
        else:
            assigned_user_id = random_instance.choice(valid_user_ids)
            user_signup = user_lookup[assigned_user_id]["signup_date"]
            order_dt = generate_clustered_order_timestamp(user_signup, random_instance)

        # Generate base order value
        # Normal-like log distribution around $65.00
        raw_price = random_instance.lognormvariate(4.0, 0.6)
        clamped_price = round(max(config.ORDER_MIN_VALID_PRICE, min(config.ORDER_MAX_VALID_PRICE, raw_price)), 2)

        order_status = random_instance.choices(
            config.ORDER_STATUSES,
            weights=config.ORDER_STATUS_WEIGHTS,
            k=1,
        )[0]

        order_entry = {
            "order_id": order_id,
            "user_id": assigned_user_id,
            "order_date": order_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "order_value": clamped_price,
            "order_status": order_status,
            "is_duplicate": False,
        }
        order_records.append(order_entry)

    # Step 2: Inject negative or zero order values on selected rows
    invalid_value_indices = random_instance.sample(
        range(orphaned_count, base_order_count),
        invalid_value_count,
    )
    for idx in invalid_value_indices:
        error_type = random_instance.choice(["zero", "negative_small", "negative_large"])
        if error_type == "zero":
            order_records[idx]["order_value"] = 0.00
        elif error_type == "negative_small":
            order_records[idx]["order_value"] = -round(random_instance.uniform(5.0, 50.0), 2)
        else:
            order_records[idx]["order_value"] = -round(order_records[idx]["order_value"], 2)

    # Step 3: Create conflicting duplicate order_ids (simulating retry / resend race condition)
    orders_to_duplicate = random_instance.sample(order_records, duplicate_count)

    for orig_order in orders_to_duplicate:
        conflict_type = random_instance.choice([
            "conflicting_value",
            "conflicting_status",
            "shifted_timestamp",
            "conflicting_status_and_value",
        ])

        dup_value = orig_order["order_value"]
        dup_status = orig_order["order_status"]
        dup_date = orig_order["order_date"]

        if conflict_type == "conflicting_value":
            # Modified value due to discount or surcharge on retry
            dup_value = round(orig_order["order_value"] * random_instance.choice([0.9, 1.15]), 2)
        elif conflict_type == "conflicting_status":
            # Status changed between retry (e.g. pending vs completed)
            dup_status = "pending" if orig_order["order_status"] == "completed" else "completed"
        elif conflict_type == "shifted_timestamp":
            # Shifted timestamp by a few seconds/minutes, strictly clamped to max_end_dt
            orig_dt = datetime.strptime(orig_order["order_date"], "%Y-%m-%dT%H:%M:%SZ")
            max_shift = max(1, min(300, int((max_end_dt - orig_dt).total_seconds())))
            dup_dt = min(orig_dt + timedelta(seconds=random_instance.randint(1, max_shift)), max_end_dt)
            dup_date = dup_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            dup_status = "cancelled"
            dup_value = 0.00

        duplicate_entry = {
            "order_id": orig_order["order_id"],
            "user_id": orig_order["user_id"],
            "order_date": dup_date,
            "order_value": dup_value,
            "order_status": dup_status,
            "is_duplicate": True,
        }
        order_records.append(duplicate_entry)

    # Sort primarily by order_date with slight shuffle to simulate asynchronous event arrival
    order_records.sort(key=lambda item: item["order_date"])

    return order_records
