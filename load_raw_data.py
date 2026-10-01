"""Loads raw CSV tables into PostgreSQL under the 'raw' schema."""

import sys
from psycopg2 import sql

import config
import db_config


def setup_database_and_load_data() -> None:
    """Creates raw schema tables and bulk-copies CSV data into PostgreSQL."""
    # Check if raw files exist before attempting DB connection
    for path in [config.USERS_CSV_PATH, config.ORDERS_CSV_PATH, config.EVENTS_CSV_PATH]:
        if not path.exists():
            sys.exit(f"Error: Required raw data file not found at '{path}'. Run generate_raw_data.py first.")

    creds = db_config.get_db_credentials(require_password=True)
    target_dbname = creds["dbname"]

    # Create target database if missing via administrative postgres connection
    admin_conn = db_config.get_db_connection(dbname="postgres", autocommit=True)
    with admin_conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_dbname,))
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(target_dbname)))
    admin_conn.close()

    # Connect to warehouse database and load tables
    conn = db_config.get_db_connection(autocommit=True)
    with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS raw;")

            cur.execute("DROP TABLE IF EXISTS raw.users CASCADE;")
            cur.execute("""
                CREATE TABLE raw.users (
                    user_id INT,
                    first_name VARCHAR(100),
                    last_name VARCHAR(100),
                    email VARCHAR(255),
                    country VARCHAR(50),
                    signup_date VARCHAR(50)
                );
            """)

            cur.execute("DROP TABLE IF EXISTS raw.orders CASCADE;")
            cur.execute("""
                CREATE TABLE raw.orders (
                    order_id INT,
                    user_id INT,
                    order_date VARCHAR(50),
                    order_amount NUMERIC(10, 2),
                    order_status VARCHAR(50)
                );
            """)

            cur.execute("DROP TABLE IF EXISTS raw.events CASCADE;")
            cur.execute("""
                CREATE TABLE raw.events (
                    event_id INT,
                    user_id INT,
                    session_id VARCHAR(50),
                    event_name VARCHAR(50),
                    event_timestamp VARCHAR(50),
                    device_type VARCHAR(50),
                    page_url VARCHAR(255)
                );
            """)

            with open(config.USERS_CSV_PATH, "r", encoding="utf-8") as f:
                cur.copy_expert("COPY raw.users FROM STDIN WITH CSV HEADER", f)

            with open(config.ORDERS_CSV_PATH, "r", encoding="utf-8") as f:
                cur.copy_expert("COPY raw.orders FROM STDIN WITH CSV HEADER", f)

            with open(config.EVENTS_CSV_PATH, "r", encoding="utf-8") as f:
                cur.copy_expert("COPY raw.events FROM STDIN WITH CSV HEADER", f)

        conn.close()
    print("Loaded raw.users, raw.orders, and raw.events into PostgreSQL.")


if __name__ == "__main__":
    setup_database_and_load_data()
