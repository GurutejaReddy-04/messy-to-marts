"""Synthetic events data generator with deliberate real-world messiness.

Implements:
- Local time formatting (intentional timezone mismatch with orders UTC timestamps)
- Realistic e-commerce session conversion funnel: page_view -> add_to_cart -> purchase
- Diverse session paths: single/multi-page browsing, multi-item cart additions, abandonment
- ~1.0% orphaned user_id records (late-arriving or untracked visitors)
"""

import random
from datetime import datetime, timedelta

import config


def generate_session_events(
    session_id: str,
    user_id: int,
    session_start_dt: datetime,
    device_type: str,
    random_instance: random.Random,
) -> list[dict]:
    """Generate an ordered sequence of event records for a single user session."""
    events_in_session: list[dict] = []
    current_dt = session_start_dt

    # Step 1: Initial Page Views (1 to 5 page views)
    page_view_count = random_instance.choices([1, 2, 3, 4, 5, 6], weights=[0.30, 0.25, 0.20, 0.12, 0.08, 0.05], k=1)[0]
    
    available_pages = [
        "/home",
        "/categories/electronics",
        "/categories/apparel",
        "/categories/home-goods",
        "/products/smart-watch",
        "/products/running-shoes",
        "/products/coffee-maker",
        "/deals/summer-sale",
    ]

    for _ in range(page_view_count):
        chosen_page = random_instance.choice(available_pages)
        events_in_session.append({
            "user_id": user_id,
            "session_id": session_id,
            "event_name": "page_view",
            # Timestamps stored in local time without UTC offset
            "event_timestamp": current_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "device_type": device_type,
            "page_url": chosen_page,
        })
        # Advance 15-180 seconds between page views
        current_dt += timedelta(seconds=random_instance.randint(15, 180))

    # Step 2: Funnel Decision - Add to Cart (32% probability)
    proceeds_to_cart = random_instance.random() < config.FUNNEL_CART_PROBABILITY
    if not proceeds_to_cart:
        return events_in_session

    # Multi-cart handling: some sessions add multiple products
    has_multiple_items = random_instance.random() < config.MULTI_CART_PROBABILITY
    cart_add_count = random_instance.randint(2, 4) if has_multiple_items else 1

    for _ in range(cart_add_count):
        events_in_session.append({
            "user_id": user_id,
            "session_id": session_id,
            "event_name": "add_to_cart",
            "event_timestamp": current_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "device_type": device_type,
            "page_url": "/cart",
        })
        current_dt += timedelta(seconds=random_instance.randint(20, 120))

    # Step 3: Funnel Decision - Purchase (40% probability given cart add)
    proceeds_to_purchase = random_instance.random() < config.FUNNEL_PURCHASE_PROBABILITY
    if not proceeds_to_purchase:
        return events_in_session

    # Add purchase event at checkout confirmation
    current_dt += timedelta(seconds=random_instance.randint(45, 240))
    events_in_session.append({
        "user_id": user_id,
        "session_id": session_id,
        "event_name": "purchase",
        "event_timestamp": current_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "device_type": device_type,
        "page_url": "/order-confirmation",
    })

    return events_in_session


def generate_raw_events(user_records: list[dict]) -> list[dict]:
    """Generate raw event records with realistic session distributions and orphaned keys."""
    random_instance = random.Random(config.SEED_EVENTS)

    valid_user_ids = [u["user_id"] for u in user_records if not u.get("is_typo_duplicate", False)]
    user_lookup = {u["user_id"]: u for u in user_records}

    orphaned_user_pool = list(range(9001, 9500))

    all_event_records: list[dict] = []
    session_counter = 100000

    target_total = config.TOTAL_EVENTS_TARGET
    estimated_events_per_session = 3.5
    target_sessions = int(target_total / estimated_events_per_session)

    # Generate sessions until we reach target volume
    while len(all_event_records) < target_total:
        session_counter += 1
        session_id = f"ses_{session_counter}"

        # Determine if this session references an orphaned user (~1.0% rate)
        is_orphaned_session = random_instance.random() < config.EVENT_ORPHANED_USER_RATE
        if is_orphaned_session:
            assigned_user_id = random_instance.choice(orphaned_user_pool)
            start_month = random_instance.choices(range(1, 13), weights=[1.5, 1.1, 0.9, 0.8, 0.7, 0.7, 0.8, 0.8, 0.9, 1.1, 1.8, 1.9], k=1)[0]
            start_day = random_instance.randint(1, 28)
            session_start_dt = datetime(2023, start_month, start_day, random_instance.randint(0, 23), random_instance.randint(0, 59))
        else:
            assigned_user_id = random_instance.choice(valid_user_ids)
            user_signup_str = user_lookup[assigned_user_id]["signup_date"]
            if user_signup_str:
                user_signup_dt = datetime.strptime(user_signup_str, "%Y-%m-%d %H:%M:%S")
            else:
                user_signup_dt = datetime(2023, 1, 1, 0, 0, 0)
            
            end_period = datetime(2023, 12, 31, 23, 59, 59)
            available_days = max(1, (end_period - user_signup_dt).days)
            day_offset = int(random_instance.expovariate(1.0 / 40.0))
            day_offset = min(day_offset, available_days)
            session_start_dt = user_signup_dt + timedelta(days=day_offset, hours=random_instance.randint(0, 23), minutes=random_instance.randint(0, 59))

        device_type = random_instance.choices(config.DEVICE_TYPES, weights=config.DEVICE_TYPE_WEIGHTS, k=1)[0]

        session_events = generate_session_events(
            session_id=session_id,
            user_id=assigned_user_id,
            session_start_dt=session_start_dt,
            device_type=device_type,
            random_instance=random_instance,
        )

        all_event_records.extend(session_events)

    # Trim to exact target count and assign unique event_ids
    trimmed_records = all_event_records[:target_total]

    final_event_records: list[dict] = []
    for event_index, record in enumerate(trimmed_records, start=1):
        event_entry = {
            "event_id": 100000 + event_index,
            "user_id": record["user_id"],
            "session_id": record["session_id"],
            "event_name": record["event_name"],
            "event_timestamp": record["event_timestamp"],
            "device_type": record["device_type"],
            "page_url": record["page_url"],
        }
        final_event_records.append(event_entry)

    # Sort records chronologically
    final_event_records.sort(key=lambda item: item["event_timestamp"])

    return final_event_records
