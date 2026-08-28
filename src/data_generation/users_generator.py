"""Synthetic user data generator with deliberate real-world messiness.

Implements:
- Typo-variant duplicate accounts (varying typo rules: omission, swap, domain typos)
- Missing signup_date and missing country values at independent rates
- Non-uniform signup date clustering simulating seasonal acquisition campaigns
"""

import random
from datetime import datetime, timedelta
from faker import Faker

import config


def generate_clustered_signup_date(start_date_str: str, end_date_str: str, random_instance: random.Random) -> datetime:
    """Generate signup dates clustered around marketing campaigns (Q1 and Q4 spikes)."""
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    total_days = (end_date - start_date).days

    # Define seasonal weights by month (spikes in Jan, Nov, Dec)
    # Weights for months 1 to 12
    monthly_weights = [1.6, 1.2, 0.9, 0.8, 0.7, 0.7, 0.8, 0.8, 0.9, 1.1, 1.8, 1.9]

    # Sample a month using weights, then pick a day in that month
    selected_month = random_instance.choices(range(1, 13), weights=monthly_weights, k=1)[0]
    
    # Generate random day within that month in year 2023
    if selected_month == 2:
        day = random_instance.randint(1, 28)
    elif selected_month in [4, 6, 9, 11]:
        day = random_instance.randint(1, 30)
    else:
        day = random_instance.randint(1, 31)

    hour = random_instance.randint(0, 23)
    minute = random_instance.randint(0, 59)
    second = random_instance.randint(0, 59)

    return datetime(2023, selected_month, day, hour, minute, second)


def create_typo_variant_email(original_email: str, random_instance: random.Random) -> str:
    """Create a realistic typo variant of an email address using varied patterns."""
    local_part, domain_part = original_email.split("@", 1)
    typo_strategy = random_instance.choice(["swap_chars", "drop_char", "add_char", "domain_typo", "dot_variation"])

    if typo_strategy == "swap_chars" and len(local_part) > 3:
        # Swap two adjacent characters in local part
        idx = random_instance.randint(1, len(local_part) - 2)
        local_chars = list(local_part)
        local_chars[idx], local_chars[idx + 1] = local_chars[idx + 1], local_chars[idx]
        return f"{''.join(local_chars)}@{domain_part}"

    elif typo_strategy == "drop_char" and len(local_part) > 4:
        # Drop a single character
        idx = random_instance.randint(1, len(local_part) - 2)
        return f"{local_part[:idx]}{local_part[idx+1:]}@{domain_part}"

    elif typo_strategy == "add_char" and len(local_part) > 2:
        # Duplicate an adjacent character
        idx = random_instance.randint(1, len(local_part) - 1)
        return f"{local_part[:idx]}{local_part[idx]}{local_part[idx:]}@{domain_part}"

    elif typo_strategy == "domain_typo":
        # Realistic domain typos
        domain_replacements = {
            "gmail.com": random_instance.choice(["gmial.com", "gmai.com", "gamil.com"]),
            "yahoo.com": random_instance.choice(["yaho.com", "yahooo.com", "yaho.co"]),
            "hotmail.com": random_instance.choice(["hotmial.com", "hotmal.com"]),
            "outlook.com": random_instance.choice(["outlok.com", "outlookk.com"]),
        }
        for known_domain, typo_domain in domain_replacements.items():
            if domain_part.endswith(known_domain):
                return f"{local_part}@{typo_domain}"
        return f"{local_part}@gmial.com"

    else:
        # Dot variation: either add or remove dot in local part
        if "." in local_part:
            return f"{local_part.replace('.', '')}@{domain_part}"
        elif len(local_part) > 4:
            midpoint = len(local_part) // 2
            return f"{local_part[:midpoint]}.{local_part[midpoint:]}@{domain_part}"
        return f"{local_part}1@{domain_part}"


def generate_raw_users() -> list[dict]:
    """Generate raw user records adhering to config targets and deliberate messiness rules."""
    faker_instance = Faker()
    Faker.seed(config.SEED_USERS)
    random_instance = random.Random(config.SEED_USERS)

    total_target_count = config.TOTAL_USERS_TARGET
    duplicate_count = int(total_target_count * config.USER_TYPO_DUPLICATE_RATE)
    base_user_count = total_target_count - duplicate_count

    user_records: list[dict] = []
    base_user_pool: list[dict] = []

    # Step 1: Generate primary base users
    for user_index in range(1, base_user_count + 1):
        first_name = faker_instance.first_name()
        last_name = faker_instance.last_name()
        domain = random_instance.choice(["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "example.com"])
        clean_email = f"{first_name.lower()}.{last_name.lower()}@{domain}"
        country_code = random_instance.choices(config.USER_COUNTRIES, weights=config.USER_COUNTRY_WEIGHTS, k=1)[0]
        signup_dt = generate_clustered_signup_date(config.START_DATE, config.END_DATE, random_instance)

        user_entry = {
            "user_id": user_index,
            "first_name": first_name,
            "last_name": last_name,
            "email": clean_email,
            "country": country_code,
            "signup_date": signup_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "is_typo_duplicate": False,
            "original_user_id": None,
        }
        user_records.append(user_entry)
        base_user_pool.append(user_entry)

    # Step 2: Generate typo-variant duplicate rows with new user_ids
    users_to_duplicate = random_instance.sample(base_user_pool, duplicate_count)
    next_user_id = base_user_count + 1

    for original_user in users_to_duplicate:
        typo_email = create_typo_variant_email(original_user["email"], random_instance)
        
        # Duplicate signup is typically days/weeks later
        orig_signup = datetime.strptime(original_user["signup_date"], "%Y-%m-%d %H:%M:%S")
        days_offset = random_instance.randint(5, 60)
        dup_signup = min(orig_signup + timedelta(days=days_offset), datetime(2023, 12, 31, 23, 59, 59))

        duplicate_entry = {
            "user_id": next_user_id,
            "first_name": original_user["first_name"],
            "last_name": original_user["last_name"],
            "email": typo_email,
            "country": original_user["country"],
            "signup_date": dup_signup.strftime("%Y-%m-%d %H:%M:%S"),
            "is_typo_duplicate": True,
            "original_user_id": original_user["user_id"],
        }
        user_records.append(duplicate_entry)
        next_user_id += 1

    # Step 3: Inject independent null values for signup_date and country
    null_signup_count = int(total_target_count * config.USER_NULL_SIGNUP_DATE_RATE)
    null_country_count = int(total_target_count * config.USER_NULL_COUNTRY_RATE)

    # Choose distinct sets for null injection to maintain varied patterns
    signup_null_indices = random_instance.sample(range(len(user_records)), null_signup_count)
    country_null_indices = random_instance.sample(range(len(user_records)), null_country_count)

    for idx in signup_null_indices:
        user_records[idx]["signup_date"] = ""

    for idx in country_null_indices:
        user_records[idx]["country"] = ""

    # Shuffle slightly so duplicates aren't all clustered strictly at the end of the file
    random_instance.shuffle(user_records)

    return user_records
