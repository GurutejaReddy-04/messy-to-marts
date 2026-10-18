"""Parity test: verifies that offline fallback produces exact dbt mart metrics."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import render_dashboard_charts
import db_config


def test_offline_fallback_fixture_metrics():
    """Verify offline fallback computes exact staging and mart values matching dbt logic."""
    df_cohort, df_funnel, df_rev = render_dashboard_charts.compute_marts_from_fixtures()

    # Mart 1: fct_revenue_trends
    assert len(df_rev) == 363, f"Expected 363 tracked calendar dates, got {len(df_rev)}"
    active_days = df_rev[df_rev['order_count'] > 0]
    assert len(active_days) == 362, f"Expected 362 active days with completed orders, got {len(active_days)}"
    assert round(df_rev['total_revenue'].sum(), 2) == 182321.85, (
        f"Expected $182,321.85 GMV, got {df_rev['total_revenue'].sum()}"
    )
    assert df_rev['order_count'].sum() == 2792, (
        f"Expected 2,792 completed orders, got {df_rev['order_count'].sum()}"
    )
    assert round(active_days['average_order_value'].mean(), 2) == 66.28, (
        f"Expected $66.28 mean active day AOV, got {round(active_days['average_order_value'].mean(), 2)}"
    )

    # Mart 2: monthly_cohort_retention
    cohort_sizes = df_cohort[df_cohort['month_number'] == 0]
    assert cohort_sizes['cohort_size'].sum() == 946, (
        f"Expected 946 total cohorted users across 12 months, got {cohort_sizes['cohort_size'].sum()}"
    )
    jan_cohort = cohort_sizes[cohort_sizes['cohort_month'] == '2023-01-01']
    assert len(jan_cohort) == 1 and jan_cohort['cohort_size'].iloc[0] == 116, (
        f"Expected January 2023 cohort size N=116, got {jan_cohort['cohort_size'].values}"
    )

    # Mart 3: funnel_summary
    assert len(df_funnel) == 3, f"Expected 3 funnel steps, got {len(df_funnel)}"
    assert df_funnel['session_count'].tolist() == [4672, 1512, 581], (
        f"Expected [4672, 1512, 581], got {df_funnel['session_count'].tolist()}"
    )
    assert df_funnel['step_conversion_pct'].tolist() == [100.0, 32.36, 38.43], (
        f"Expected [100.0, 32.36, 38.43], got {df_funnel['step_conversion_pct'].tolist()}"
    )
    assert df_funnel['overall_conversion_pct'].tolist() == [100.0, 32.36, 12.44], (
        f"Expected [100.0, 32.36, 12.44], got {df_funnel['overall_conversion_pct'].tolist()}"
    )


def test_connection_refusal_triggers_fallback():
    """Verify that when PostgreSQL connection fails in db_config, load_all_marts switches to CSV fallback."""
    import os
    from unittest.mock import patch
    import psycopg2
    import psycopg2.errors

    # 1. Simulate OperationalError at the underlying psycopg2.connect level
    # This exercises the real render_dashboard_charts.get_db_connection() and db_config.get_db_connection()
    # ensuring db_config does not call sys.exit() and re-raises OperationalError.
    with patch.dict(os.environ, {"DB_PASSWORD": "test_ephemeral_password"}):
        with patch("psycopg2.connect", side_effect=psycopg2.OperationalError("Connection refused: mock connection failure")):
            df_cohort, df_funnel, df_rev = render_dashboard_charts.load_all_marts()
            assert len(df_cohort) == 78, f"Expected 78 cohort rows from fallback, got {len(df_cohort)}"
            assert len(df_funnel) == 3, f"Expected 3 funnel steps from fallback, got {len(df_funnel)}"
            assert len(df_rev) == 363, f"Expected 363 revenue rows from fallback, got {len(df_rev)}"

    # 2. Simulate missing credentials traveling through real db_config.get_db_connection()
    with patch.dict(os.environ, {}, clear=True):
        df_cohort, df_funnel, df_rev = render_dashboard_charts.load_all_marts()
        assert len(df_rev) == 363

    # 3. Verify that non-connection errors (e.g. query/schema error) are NOT suppressed by the fallback
    class MockConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def close(self):
            pass

    with patch("db_config.get_db_connection", return_value=MockConn()):
        with patch("pandas.read_sql", side_effect=psycopg2.errors.UndefinedTable("relation does not exist")):
            try:
                render_dashboard_charts.load_all_marts()
                assert False, "Expected UndefinedTable query error to surface without triggering fallback"
            except psycopg2.errors.UndefinedTable:
                pass


def test_database_vs_fallback_parity_if_connected():
    """If PostgreSQL is accessible, assert exact row-by-row and column-by-column parity between warehouse and fallback."""
    try:
        conn = db_config.get_db_connection()
    except Exception as exc:
        print(f"PostgreSQL warehouse connection not available ({exc}); skipping live database parity check.")
        return

    try:
        import pandas as pd
        df_cohort_fb, df_funnel_fb, df_rev_fb = render_dashboard_charts.compute_marts_from_fixtures()

        # 1. Exact Row-by-Row Parity: fct_revenue_trends (all 5 columns)
        df_rev_db = pd.read_sql(
            "select order_date::text as order_date, round(total_revenue::numeric, 2)::float as total_revenue, "
            "order_count::int as order_count, distinct_user_count::int as distinct_user_count, "
            "round(average_order_value::numeric, 2)::float as average_order_value "
            "from public_marts.fct_revenue_trends order by order_date;",
            conn
        )
        assert len(df_rev_db) == len(df_rev_fb) == 363, f"Row count mismatch: DB {len(df_rev_db)} vs fallback {len(df_rev_fb)}"
        assert df_rev_db['order_date'].tolist() == df_rev_fb['order_date'].tolist(), "Order date sequence mismatch"
        assert (df_rev_db['order_count'].values == df_rev_fb['order_count'].values).all(), "Order count row mismatch"
        assert (df_rev_db['distinct_user_count'].values == df_rev_fb['distinct_user_count'].values).all(), "Distinct user count row mismatch"
        # Strict exact comparison normalized to 2 decimal places (cents)
        assert [f"{v:.2f}" for v in df_rev_db['total_revenue']] == [f"{v:.2f}" for v in df_rev_fb['total_revenue']], "Total revenue strict value mismatch"
        assert [f"{v:.2f}" for v in df_rev_db['average_order_value']] == [f"{v:.2f}" for v in df_rev_fb['average_order_value']], "AOV strict value mismatch"

        # 2. Exact Row-by-Row Parity: monthly_cohort_retention (all 5 columns)
        df_cohort_db = pd.read_sql(
            "select cohort_month::text as cohort_month, cohort_size::int as cohort_size, "
            "month_number::int as month_number, active_users::int as active_users, "
            "round(retention_pct::numeric, 2)::float as retention_pct "
            "from public_marts.monthly_cohort_retention order by cohort_month, month_number;",
            conn
        )
        assert len(df_cohort_db) == len(df_cohort_fb) == 78, f"Cohort row count mismatch: DB {len(df_cohort_db)} vs fallback {len(df_cohort_fb)}"
        assert df_cohort_db['cohort_month'].tolist() == df_cohort_fb['cohort_month'].tolist(), "Cohort month sequence mismatch"
        assert (df_cohort_db['cohort_size'].values == df_cohort_fb['cohort_size'].values).all(), "Cohort size row mismatch"
        assert (df_cohort_db['month_number'].values == df_cohort_fb['month_number'].values).all(), "Month number sequence mismatch"
        assert (df_cohort_db['active_users'].values == df_cohort_fb['active_users'].values).all(), "Active users row mismatch"
        # Strict exact comparison normalized to 2 decimal places (hundredths of a percent)
        assert [f"{v:.2f}" for v in df_cohort_db['retention_pct']] == [f"{v:.2f}" for v in df_cohort_fb['retention_pct']], "Retention pct strict value mismatch"

        # 3. Exact Row-by-Row Parity: funnel_summary (all 5 columns)
        df_funnel_db = pd.read_sql(
            "select funnel_step_order::int as funnel_step_order, funnel_step::text as funnel_step, "
            "session_count::int as session_count, round(step_conversion_pct::numeric, 2)::float as step_conversion_pct, "
            "round(overall_conversion_pct::numeric, 2)::float as overall_conversion_pct "
            "from public_marts.funnel_summary order by funnel_step_order;",
            conn
        )
        assert len(df_funnel_db) == len(df_funnel_fb) == 3, f"Funnel row count mismatch: DB {len(df_funnel_db)} vs fallback {len(df_funnel_fb)}"
        assert (df_funnel_db['funnel_step_order'].values == df_funnel_fb['funnel_step_order'].values).all(), "Funnel step order mismatch"
        assert df_funnel_db['funnel_step'].tolist() == df_funnel_fb['funnel_step'].tolist(), "Funnel step name mismatch"
        assert (df_funnel_db['session_count'].values == df_funnel_fb['session_count'].values).all(), "Session count row mismatch"
        # Strict exact comparison normalized to 2 decimal places
        assert [f"{v:.2f}" for v in df_funnel_db['step_conversion_pct']] == [f"{v:.2f}" for v in df_funnel_fb['step_conversion_pct']], "Step conversion pct strict value mismatch"
        assert [f"{v:.2f}" for v in df_funnel_db['overall_conversion_pct']] == [f"{v:.2f}" for v in df_funnel_fb['overall_conversion_pct']], "Overall conversion pct strict value mismatch"

        print("Exact row-by-row and column-by-column database vs fallback parity verified for all 3 marts!")
    finally:
        conn.close()


if __name__ == "__main__":
    test_offline_fallback_fixture_metrics()
    test_connection_refusal_triggers_fallback()
    test_database_vs_fallback_parity_if_connected()
    print("All offline fallback parity and connection tests PASSED successfully!")
