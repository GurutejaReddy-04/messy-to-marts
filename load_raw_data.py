"""Loads raw CSV data into PostgreSQL warehouse under the 'raw' schema."""

import csv
import psycopg2
from psycopg2 import sql

import config

import os

DB_NAME = os.getenv("DB_NAME", os.getenv("DBT_DBNAME", "analytics_pipeline"))
DB_USER = os.getenv("DB_USER", os.getenv("DBT_USER", "postgres"))
DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("DBT_PASSWORD", "postgres"))
DB_HOST = os.getenv("DB_HOST", os.getenv("DBT_HOST", "localhost"))
DB_PORT = os.getenv("DB_PORT", os.getenv("DBT_PORT", "5432"))


def setup_database_and_load_data() -> None:
    """Create analytics_pipeline database, raw schema, and load CSV tables."""
    # 1. Connect to default postgres to create database if not exists
    admin_conn = psycopg2.connect(
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )
    admin_conn.autocommit = True
    with admin_conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
        if not cur.fetchone():
            print(f"Creating database '{DB_NAME}'...")
            cur.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(DB_NAME)))
        else:
            print(f"Database '{DB_NAME}' already exists.")
    admin_conn.close()

    # 2. Connect to analytics_pipeline database
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        # Create raw schema
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw;")

        # Create raw.users
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

        # Create raw.orders
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

        # Create raw.events
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

        # Bulk copy CSV data
        with open(config.USERS_CSV_PATH, "r", encoding="utf-8") as f:
            next(f) # Skip header
            cur.copy_expert("COPY raw.users FROM STDIN WITH CSV HEADER", open(config.USERS_CSV_PATH, "r", encoding="utf-8"))
        print(f"Loaded raw.users from {config.USERS_CSV_PATH}")

        with open(config.ORDERS_CSV_PATH, "r", encoding="utf-8") as f:
            cur.copy_expert("COPY raw.orders FROM STDIN WITH CSV HEADER", open(config.ORDERS_CSV_PATH, "r", encoding="utf-8"))
        print(f"Loaded raw.orders from {config.ORDERS_CSV_PATH}")

        with open(config.EVENTS_CSV_PATH, "r", encoding="utf-8") as f:
            cur.copy_expert("COPY raw.events FROM STDIN WITH CSV HEADER", open(config.EVENTS_CSV_PATH, "r", encoding="utf-8"))
        print(f"Loaded raw.events from {config.EVENTS_CSV_PATH}")

        # Verification counts
        for table in ["users", "orders", "events"]:
            cur.execute(sql.SQL("SELECT count(*) FROM raw.{};").format(sql.Identifier(table)))
            count = cur.fetchone()[0]
            print(f"Verification: raw.{table} row count = {count}")

    conn.close()
    print("All raw tables successfully loaded into PostgreSQL warehouse.")


if __name__ == "__main__":
    setup_database_and_load_data()
