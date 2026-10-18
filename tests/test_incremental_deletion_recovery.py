"""Integration test: validates incremental source-deletion self-healing against PostgreSQL warehouse."""

import sys
import subprocess
from pathlib import Path
from decimal import Decimal

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import db_config


def run_cmd(cmd_list: list[str]) -> None:
    """Execute a CLI command and assert success."""
    res = subprocess.run(cmd_list, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command {' '.join(cmd_list)} failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")


def test_incremental_deletion_recovery():
    """Validates that deleting source orders inside the rolling lookback window heals to zero in incremental runs."""
    try:
        conn = db_config.get_db_connection()
    except Exception as exc:
        print(f"Skipping live incremental deletion test (PostgreSQL not connected: {exc})")
        return

    try:
        with conn.cursor() as cur:
            # 1. Select an in-scope date within the 7-day lookback window that has completed orders
            cur.execute("""
                select order_date, total_revenue, order_count, distinct_user_count, average_order_value
                from public_marts.fct_revenue_trends
                where order_date >= (select max(order_date) - interval '4 days' from public_marts.fct_revenue_trends)
                  and order_count > 0
                order by order_date desc
                limit 1;
            """)
            row = cur.fetchone()
            assert row is not None, "Expected at least one recent completed order date within lookback window"
            target_date, init_rev, init_orders, init_users, init_aov = row
            target_date_str = str(target_date)

            print(f"Testing source deletion healing for date '{target_date_str}' (initial GMV: ${init_rev}, orders: {init_orders})")
            assert init_rev > 0, "Initial revenue should be positive"
            assert init_orders > 0, "Initial order count should be positive"

            # 2. Simulate complete deletion of source orders for this date in raw.orders
            cur.execute("delete from raw.orders where substr(order_date, 1, 10) = %s;", (target_date_str,))
            conn.commit()

        # 3. Execute incremental dbt run on stg_orders and fct_revenue_trends
        print("Executing incremental dbt run to process source deletion...")
        run_cmd(["dbt", "run", "--select", "stg_orders", "fct_revenue_trends", "--profiles-dir", "."])

        # 4. Verify that fct_revenue_trends retains the date row but zeroed out
        with conn.cursor() as cur:
            cur.execute("""
                select total_revenue, order_count, distinct_user_count, average_order_value
                from public_marts.fct_revenue_trends
                where order_date = %s;
            """, (target_date,))
            reconciled_row = cur.fetchone()
            assert reconciled_row is not None, f"Target row for '{target_date_str}' should be preserved in fct_revenue_trends"

            rec_rev, rec_orders, rec_users, rec_aov = reconciled_row
            assert Decimal(str(rec_rev)) == Decimal('0.00'), f"Expected 0.00 revenue, got {rec_rev}"
            assert int(rec_orders) == 0, f"Expected 0 orders, got {rec_orders}"
            assert int(rec_users) == 0, f"Expected 0 distinct users, got {rec_users}"
            assert Decimal(str(rec_aov)) == Decimal('0.00'), f"Expected 0.00 AOV, got {rec_aov}"

        # 5. Assert that dbt reconciliation test passes with the zeroed-out row
        print("Running dbt revenue reconciliation test against healed row...")
        run_cmd(["dbt", "test", "--select", "test_revenue_excludes_non_completed_orders", "--profiles-dir", "."])

        print(f"PASSED: Date '{target_date_str}' was automatically healed to $0.00 revenue and 0 orders!")

    finally:
        # 6. Restore warehouse fixtures to full baseline
        print("Restoring test database fixtures...")
        run_cmd(["python", "load_raw_data.py", "--replace"])
        run_cmd(["dbt", "run", "--profiles-dir", "."])
        conn.close()


if __name__ == "__main__":
    test_incremental_deletion_recovery()
