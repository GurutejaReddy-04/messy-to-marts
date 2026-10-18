"""Loads raw CSV tables into PostgreSQL under the 'raw' schema (Development & CI Ingestion)."""

import sys
from psycopg2 import sql

import config
import db_config


def setup_database_and_load_data() -> None:
    """Creates raw schema tables and bulk-copies CSV data into PostgreSQL for development/CI environments."""
    # Check if raw files exist before attempting DB connection
    for path in [config.USERS_CSV_PATH, config.ORDERS_CSV_PATH, config.EVENTS_CSV_PATH]:
        if not path.exists():
            sys.exit(f"Error: Required raw data file not found at '{path}'. Run generate_raw_data.py first.")

    creds = db_config.get_db_credentials(require_password=True)
    target_dbname = creds["dbname"]

    # Operational safety guard: prevent accidental destructive drops on non-dev databases
    allowed_dev_databases = {"analytics_pipeline", "analytics_pipeline_dev", "analytics_pipeline_test"}
    is_force_reset = "--force-reset" in sys.argv
    is_drop_tables = "--drop-tables" in sys.argv or is_force_reset
    is_replace = "--replace" in sys.argv or "--truncate" in sys.argv or is_drop_tables

    if target_dbname not in allowed_dev_databases and not is_force_reset:
        sys.exit(
            f"Safety Error: Destructive reset target '{target_dbname}' is not a designated "
            f"dev/test database ({', '.join(sorted(allowed_dev_databases))}). "
            f"To execute against this target, explicitly pass '--force-reset'."
        )

    # Create target database if missing via administrative postgres connection
    try:
        admin_conn = db_config.get_db_connection(dbname="postgres", autocommit=True)
        with admin_conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_dbname,))
            if not cur.fetchone():
                cur.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(target_dbname)))
        admin_conn.close()
    except (ValueError, psycopg2.OperationalError) as err:
        sys.exit(f"Failed to connect to PostgreSQL administrative database: {err}")

    # Connect to warehouse database and load tables atomically
    try:
        conn = db_config.get_db_connection(autocommit=False)
    except (ValueError, psycopg2.OperationalError) as err:
        sys.exit(f"Failed to connect to warehouse database '{target_dbname}': {err}")
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS raw;")

            # Only drop existing tables if explicitly requested via --drop-tables or --force-reset
            if is_drop_tables:
                cur.execute("DROP TABLE IF EXISTS raw.users CASCADE;")
                cur.execute("DROP TABLE IF EXISTS raw.orders CASCADE;")
                cur.execute("DROP TABLE IF EXISTS raw.events CASCADE;")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS raw.users (
                    user_id INT,
                    first_name VARCHAR(100),
                    last_name VARCHAR(100),
                    email VARCHAR(255),
                    country VARCHAR(50),
                    signup_date VARCHAR(50)
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS raw.orders (
                    order_id INT,
                    user_id INT,
                    order_date VARCHAR(50),
                    order_amount NUMERIC(10, 2),
                    order_status VARCHAR(50)
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS raw.events (
                    event_id INT,
                    user_id INT,
                    session_id VARCHAR(50),
                    event_name VARCHAR(50),
                    event_timestamp VARCHAR(50),
                    device_type VARCHAR(50),
                    page_url VARCHAR(255)
                );
            """)

            # Protect against accidental truncation of persistent warehouse data
            cur.execute("SELECT count(*) FROM raw.users;")
            user_count = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM raw.orders;")
            order_count = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM raw.events;")
            event_count = cur.fetchone()[0]

            has_existing_data = (user_count > 0 or order_count > 0 or event_count > 0)
            if has_existing_data and not is_replace:
                sys.exit(
                    f"Safety Error: Existing data detected in 'raw' schema tables (users: {user_count}, "
                    f"orders: {order_count}, events: {event_count}).\n"
                    f"load_raw_data.py is a test fixture loader and will not overwrite warehouse data by default.\n"
                    f"  - To overwrite fixture data for development/CI: pass '--replace' or '--truncate'.\n"
                    f"  - To perform a destructive schema reset: pass '--drop-tables'.\n"
                    f"  - For production incremental ingestion: use the continuous/streaming pipeline."
                )

            # Atomic replacement: truncate and copy all tables within the transaction boundary
            cur.execute("TRUNCATE TABLE raw.users, raw.orders, raw.events;")

            with open(config.USERS_CSV_PATH, "r", encoding="utf-8") as f:
                cur.copy_expert("COPY raw.users FROM STDIN WITH CSV HEADER", f)

            with open(config.ORDERS_CSV_PATH, "r", encoding="utf-8") as f:
                cur.copy_expert("COPY raw.orders FROM STDIN WITH CSV HEADER", f)

            with open(config.EVENTS_CSV_PATH, "r", encoding="utf-8") as f:
                cur.copy_expert("COPY raw.events FROM STDIN WITH CSV HEADER", f)

        conn.commit()
        print("Atomically loaded raw.users, raw.orders, and raw.events into PostgreSQL.")
    except Exception as exc:
        conn.rollback()
        sys.exit(f"Data loading failed; transaction rolled back. Error: {exc}")
    finally:
        conn.close()


if __name__ == "__main__":
    setup_database_and_load_data()
