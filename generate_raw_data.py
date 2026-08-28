"""Main CLI script to generate synthetic raw CSV datasets for the analytics pipeline.

Executes data generation across users, orders, and events tables, saving them to raw_data/
and printing comprehensive validation metrics and spot-check samples.
"""

import csv
from pathlib import Path

import config
from src.data_generation.users_generator import generate_raw_users
from src.data_generation.orders_generator import generate_raw_orders
from src.data_generation.events_generator import generate_raw_events


def write_records_to_csv(filepath: Path, fieldnames: list[str], records: list[dict]) -> None:
    """Write a list of dictionaries to a CSV file with given headers."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def execute_pipeline_generation() -> None:
    """Run full synthetic data generation and output validation metrics."""
    print("=" * 70)
    print("STARTING SYNTHETIC RAW DATA GENERATION (PHASE 1)")
    print("=" * 70)

    # 1. Generate Users
    print("\n[1/3] Generating raw users dataset...")
    users_records = generate_raw_users()
    user_fields = ["user_id", "first_name", "last_name", "email", "country", "signup_date"]
    write_records_to_csv(config.USERS_CSV_PATH, user_fields, users_records)
    print(f" -> Successfully written {len(users_records)} rows to {config.USERS_CSV_PATH}")

    # 2. Generate Orders
    print("\n[2/3] Generating raw orders dataset...")
    orders_records = generate_raw_orders(users_records)
    order_fields = ["order_id", "user_id", "order_date", "order_value", "order_status"]
    write_records_to_csv(config.ORDERS_CSV_PATH, order_fields, orders_records)
    print(f" -> Successfully written {len(orders_records)} rows to {config.ORDERS_CSV_PATH}")

    # 3. Generate Events
    print("\n[3/3] Generating raw events dataset...")
    events_records = generate_raw_events(users_records)
    event_fields = ["event_id", "user_id", "session_id", "event_name", "event_timestamp", "device_type", "page_url"]
    write_records_to_csv(config.EVENTS_CSV_PATH, event_fields, events_records)
    print(f" -> Successfully written {len(events_records)} rows to {config.EVENTS_CSV_PATH}")

    # 4. Detailed Audit & Metrics Summary
    print("\n" + "=" * 70)
    print("RAW DATASET AUDIT & MESSINESS VERIFICATION")
    print("=" * 70)

    # Users audit
    user_ids_in_users = {u["user_id"] for u in users_records}
    typo_duplicate_count = sum(1 for u in users_records if u.get("is_typo_duplicate", False))
    null_signup_count = sum(1 for u in users_records if not u["signup_date"])
    null_country_count = sum(1 for u in users_records if not u["country"])

    print(f"\nUSERS TABLE (Total Rows: {len(users_records)}):")
    print(f" - Typo-variant duplicates : {typo_duplicate_count} ({typo_duplicate_count/len(users_records)*100:.1f}%) [Target: 3-6%]")
    print(f" - Null signup_date        : {null_signup_count} ({null_signup_count/len(users_records)*100:.1f}%) [Target: 1-2%]")
    print(f" - Null country            : {null_country_count} ({null_country_count/len(users_records)*100:.1f}%) [Target: 1-2%]")

    # Orders audit
    orphaned_order_count = sum(1 for o in orders_records if o["user_id"] not in user_ids_in_users)
    invalid_value_order_count = sum(1 for o in orders_records if o["order_value"] <= 0)
    
    order_id_counts: dict[int, int] = {}
    for o in orders_records:
        order_id_counts[o["order_id"]] = order_id_counts.get(o["order_id"], 0) + 1
    duplicate_order_id_count = sum(1 for o_id, c in order_id_counts.items() if c > 1)

    print(f"\nORDERS TABLE (Total Rows: {len(orders_records)}):")
    print(f" - Orphaned user_id orders : {orphaned_order_count} ({orphaned_order_count/len(orders_records)*100:.2f}%) [Target: 1-2%]")
    print(f" - Negative/zero value rows: {invalid_value_order_count} ({invalid_value_order_count/len(orders_records)*100:.2f}%) [Target: 0.5-1%]")
    print(f" - Duplicate order_id sets : {duplicate_order_id_count} ({duplicate_order_id_count/len(orders_records)*100:.2f}%) [Target: ~1%]")

    # Events audit
    orphaned_events_count = sum(1 for e in events_records if e["user_id"] not in user_ids_in_users)
    page_view_count = sum(1 for e in events_records if e["event_name"] == "page_view")
    add_to_cart_count = sum(1 for e in events_records if e["event_name"] == "add_to_cart")
    purchase_count = sum(1 for e in events_records if e["event_name"] == "purchase")

    print(f"\nEVENTS TABLE (Total Rows: {len(events_records)}):")
    print(f" - Orphaned user_id events : {orphaned_events_count} ({orphaned_events_count/len(events_records)*100:.2f}%) [Target: ~1%]")
    print(f" - Funnel: page_view       : {page_view_count} ({page_view_count/len(events_records)*100:.1f}%)")
    print(f" - Funnel: add_to_cart     : {add_to_cart_count} ({add_to_cart_count/len(events_records)*100:.1f}%)")
    print(f" - Funnel: purchase        : {purchase_count} ({purchase_count/len(events_records)*100:.1f}%)")

    # Spot checks
    print("\n" + "=" * 70)
    print("SPOT-CHECK OF INJECTED MESSINESS SAMPLES")
    print("=" * 70)

    # 1. Typo-variant pair spot check
    dup_sample = next((u for u in users_records if u.get("is_typo_duplicate", False)), None)
    if dup_sample:
        orig_sample = next((u for u in users_records if u["user_id"] == dup_sample["original_user_id"]), None)
        print("\n1. Typo-Variant Duplicate Pair in Users:")
        print(f"   [Original]  user_id: {orig_sample['user_id']}, name: {orig_sample['first_name']} {orig_sample['last_name']}, email: {orig_sample['email']}, signup: {orig_sample['signup_date']}")
        print(f"   [Duplicate] user_id: {dup_sample['user_id']}, name: {dup_sample['first_name']} {dup_sample['last_name']}, email: {dup_sample['email']}, signup: {dup_sample['signup_date']}")

    # 2. Orphaned order spot check
    orphaned_sample = next((o for o in orders_records if o["user_id"] not in user_ids_in_users), None)
    if orphaned_sample:
        print("\n2. Orphaned Order (Non-existent user_id):")
        print(f"   order_id: {orphaned_sample['order_id']}, user_id: {orphaned_sample['user_id']} (NOT in users table), date: {orphaned_sample['order_date']}, value: ${orphaned_sample['order_value']:.2f}")

    # 3. Negative / Zero order value spot check
    negative_sample = next((o for o in orders_records if o["order_value"] < 0), None)
    if negative_sample:
        print("\n3. Negative-Value Order (Glitch/Entry Error):")
        print(f"   order_id: {negative_sample['order_id']}, user_id: {negative_sample['user_id']}, date: {negative_sample['order_date']}, value: ${negative_sample['order_value']:.2f}, status: {negative_sample['order_status']}")

    # 4. Conflicting duplicate order pair spot check
    dup_order_id = next((o_id for o_id, c in order_id_counts.items() if c > 1), None)
    if dup_order_id:
        duplicate_pair = [o for o in orders_records if o["order_id"] == dup_order_id]
        print("\n4. Conflicting Duplicate Order ID Pair (Retry Bug):")
        for idx, item in enumerate(duplicate_pair, start=1):
            print(f"   [Row {idx}] order_id: {item['order_id']}, user_id: {item['user_id']}, date: {item['order_date']}, value: ${item['order_value']:.2f}, status: {item['order_status']}")

    # 5. Events timestamp format vs Orders timestamp format
    print("\n5. Timestamp Format Mismatch (Intentional):")
    print(f"   Orders (UTC ISO 8601) : {orders_records[0]['order_date']}")
    print(f"   Events (Local Time)   : {events_records[0]['event_timestamp']}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    execute_pipeline_generation()
