"""Verification and audit script to inspect generated synthetic data."""

import csv
from collections import Counter
from datetime import datetime
from src.data_generation.users_generator import generate_raw_users

# Read generated users
with open('raw_data/users.csv', mode='r', encoding='utf-8') as f:
    users = list(csv.DictReader(f))

# Re-run generator internal metadata to link original to typo duplicate
gen_users = generate_raw_users()
typo_dups = [u for u in gen_users if u.get('is_typo_duplicate', False)]
orig_lookup = {u['user_id']: u for u in gen_users if not u.get('is_typo_duplicate', False)}

print('=== 5 TYPO VARIANT PAIRS ===')
for i, dup in enumerate(typo_dups[1:6], start=1):
    orig = orig_lookup[dup['original_user_id']]
    orig_email = orig['email']
    dup_email = dup['email']
    print(f'\nPair {i}:')
    print(f'  [Original]  user_id: {orig["user_id"]}, name: {orig["first_name"]} {orig["last_name"]}, email: {orig_email}, signup: {orig["signup_date"]}')
    print(f'  [Duplicate] user_id: {dup["user_id"]}, name: {dup["first_name"]} {dup["last_name"]}, email: {dup_email}, signup: {dup["signup_date"]}')

print('\n=== ORDERS CONFLICTING DUPLICATES BREAKDOWN ===')
with open('raw_data/orders.csv', mode='r', encoding='utf-8') as f:
    orders = list(csv.DictReader(f))

orders_by_id = {}
for o in orders:
    orders_by_id.setdefault(o['order_id'], []).append(o)

dup_orders = {k: v for k, v in orders_by_id.items() if len(v) > 1}
conflict_counts = Counter()

for o_id, pair in dup_orders.items():
    o1, o2 = pair[0], pair[1]
    diffs = []
    if o1['order_value'] != o2['order_value']:
        diffs.append('order_value')
    if o1['order_status'] != o2['order_status']:
        diffs.append('order_status')
    if o1['order_date'] != o2['order_date']:
        diffs.append('order_date')
    diff_key = ' + '.join(diffs) if diffs else 'identical'
    conflict_counts[diff_key] += 1

print(f'Total duplicate pairs: {len(dup_orders)}')
for conflict_type, count in conflict_counts.items():
    print(f'  - {conflict_type}: {count} pairs ({count/len(dup_orders)*100:.1f}%)')

print('\n=== SIGNUPS PER MONTH ===')
monthly_signups = Counter()
for u in users:
    if u['signup_date']:
        month = u['signup_date'][:7]
        monthly_signups[month] += 1
    else:
        monthly_signups['NULL (Missing)'] += 1

for month in sorted(monthly_signups.keys()):
    print(f'  {month}: {monthly_signups[month]} signups')

print('\n=== ORDERS PER DAY OF WEEK ===')
dow_orders = Counter()
dow_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
for o in orders:
    dt = datetime.strptime(o['order_date'], '%Y-%m-%dT%H:%M:%SZ')
    dow = dow_names[dt.weekday()]
    dow_orders[dow] += 1

for dow in dow_names:
    print(f'  {dow:<9}: {dow_orders[dow]} orders')
