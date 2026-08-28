"""Centralized configuration for synthetic data generation.

All constants, row counts, messiness rates, and date bounds are defined here
to ensure consistency and avoid magic numbers across the pipeline.
"""

from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).parent
RAW_DATA_DIR = PROJECT_ROOT / "raw_data"
USERS_CSV_PATH = RAW_DATA_DIR / "users.csv"
ORDERS_CSV_PATH = RAW_DATA_DIR / "orders.csv"
EVENTS_CSV_PATH = RAW_DATA_DIR / "events.csv"

# Global Random Seeds for Reproducibility
SEED_USERS = 42
SEED_ORDERS = 101
SEED_EVENTS = 202

# Date Ranges
START_DATE = "2023-01-01"
END_DATE = "2023-12-31"

# Day of Week Distribution Weights (Monday=0 ... Sunday=6)
# Saturday and Sunday are moderately elevated over weekdays (~25-30%)
DAY_OF_WEEK_WEIGHTS = [1.00, 0.98, 1.00, 1.02, 1.15, 1.28, 1.32]

# Monthly Seasonality Distribution Weights (Months 1 to 12)
MONTHLY_SEASONAL_WEIGHTS = [1.20, 0.95, 0.90, 0.85, 0.80, 0.80, 0.85, 0.90, 0.95, 1.10, 1.40, 1.50]


# Target Row Counts (Users: ~1000, Orders: ~3500, Events: ~15000)
TOTAL_USERS_TARGET = 1000
TOTAL_ORDERS_TARGET = 3500
TOTAL_EVENTS_TARGET = 15000

# -----------------------------------------------------------------------------
# Users Table Configuration
# -----------------------------------------------------------------------------
# 3-6% typo-variant duplicates (DATA_SPEC.md) -> set to 4.0% (40 duplicate pairs)
USER_TYPO_DUPLICATE_RATE = 0.040

# 1-2% null signup_date and null country (DATA_SPEC.md) -> set to 1.5% each
USER_NULL_SIGNUP_DATE_RATE = 0.015
USER_NULL_COUNTRY_RATE = 0.015

USER_COUNTRIES = ["US", "CA", "GB", "DE", "FR", "IN", "AU", "NL"]
USER_COUNTRY_WEIGHTS = [0.45, 0.12, 0.12, 0.08, 0.06, 0.09, 0.05, 0.03]

# -----------------------------------------------------------------------------
# Orders Table Configuration
# -----------------------------------------------------------------------------
# 1-2% orphaned user_id (late-arriving dimension) -> set to 1.5%
ORDER_ORPHANED_USER_RATE = 0.015

# 0.5-1% negative or zero order values (data entry errors) -> set to 0.8%
ORDER_INVALID_VALUE_RATE = 0.008

# ~1% duplicate order_ids with conflicting values (retry/resend race condition) -> set to 1.0%
ORDER_CONFLICTING_DUPLICATE_RATE = 0.010

# Order Status Distribution
ORDER_STATUSES = ["completed", "pending", "returned", "cancelled"]
ORDER_STATUS_WEIGHTS = [0.82, 0.08, 0.06, 0.04]

# Order Pricing Bounds
ORDER_MIN_VALID_PRICE = 10.00
ORDER_MAX_VALID_PRICE = 450.00

# -----------------------------------------------------------------------------
# Events Table Configuration
# -----------------------------------------------------------------------------
# ~1% orphaned user_id -> set to 1.0%
EVENT_ORPHANED_USER_RATE = 0.010

EVENT_TYPES = ["page_view", "add_to_cart", "purchase"]

DEVICE_TYPES = ["mobile", "desktop", "tablet"]
DEVICE_TYPE_WEIGHTS = [0.58, 0.34, 0.08]

PRODUCT_CATEGORIES = ["electronics", "apparel", "home", "books", "beauty"]

# Typical conversion funnel probabilities per session
FUNNEL_CART_PROBABILITY = 0.32       # 32% of sessions add at least one item to cart
FUNNEL_PURCHASE_PROBABILITY = 0.40   # 40% of cart sessions complete a purchase
MULTI_CART_PROBABILITY = 0.28        # 28% of cart sessions add multiple items
