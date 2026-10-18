"""Renders BI dashboard charts from PostgreSQL marts or directly from CSV fixtures."""

from pathlib import Path
import sqlite3
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
import psycopg2

import db_config

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 11
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['axes.titleweight'] = 'bold'
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['figure.titlesize'] = 16

SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


from decimal import Decimal, ROUND_HALF_UP

def get_db_connection():
    """Retrieve an authenticated PostgreSQL database connection via centralized configuration."""
    return db_config.get_db_connection()


class DecimalAvg:
    """Aggregate matching PostgreSQL numeric arbitrary-precision average and round-half-up rounding."""

    def __init__(self):
        self.total = Decimal('0')
        self.count = 0

    def step(self, value):
        if value is not None:
            self.total += Decimal(str(round(value, 2)))
            self.count += 1

    def finalize(self):
        if self.count == 0:
            return 0.00
        avg = self.total / Decimal(self.count)
        return float(avg.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def compute_marts_from_fixtures() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Computes exact dbt marts from CSV raw fixtures when warehouse connection is unavailable."""
    conn = sqlite3.connect(":memory:")
    conn.create_aggregate("pg_avg", 1, DecimalAvg)

    users_df = pd.read_csv("raw_data/users.csv")
    orders_df = pd.read_csv("raw_data/orders.csv")
    events_df = pd.read_csv("raw_data/events.csv")

    users_df.to_sql("raw_users", conn, index=False)
    orders_df.to_sql("raw_orders", conn, index=False)
    events_df.to_sql("raw_events", conn, index=False)

    conn.execute("""
        create table stg_users as
        with normalized as (
            select
                user_id,
                first_name,
                last_name,
                lower(trim(email)) as raw_email,
                country,
                signup_date,
                case
                    when substr(lower(trim(email)), instr(lower(trim(email)), '@') + 1) in ('gmail.com', 'googlemail.com', 'gmial.com', 'gmai.com', 'gamil.com')
                        then replace(substr(lower(trim(email)), 1, instr(lower(trim(email)), '@') - 1), '.', '') || '@gmail.com'
                    when substr(lower(trim(email)), instr(lower(trim(email)), '@') + 1) in ('yaho.com', 'yahooo.com', 'yaho.co')
                        then substr(lower(trim(email)), 1, instr(lower(trim(email)), '@') - 1) || '@yahoo.com'
                    when substr(lower(trim(email)), instr(lower(trim(email)), '@') + 1) in ('hotmial.com', 'hotmal.com')
                        then substr(lower(trim(email)), 1, instr(lower(trim(email)), '@') - 1) || '@hotmail.com'
                    when substr(lower(trim(email)), instr(lower(trim(email)), '@') + 1) in ('outlok.com', 'outlookk.com')
                        then substr(lower(trim(email)), 1, instr(lower(trim(email)), '@') - 1) || '@outlook.com'
                    else lower(trim(email))
                end as normalized_email
            from raw_users
        ),
        dedup as (
            select *,
                row_number() over (partition by normalized_email order by signup_date asc, user_id asc) as rn
            from normalized
            where signup_date is not null
        )
        select user_id, first_name, last_name, normalized_email, country, signup_date,
               substr(signup_date, 1, 10) as signup_date_day,
               substr(signup_date, 1, 7) || '-01' as cohort_month
        from dedup where rn = 1;
    """)

    conn.execute("""
        create table stg_orders as
        with parsed_orders as (
            select
                order_id,
                user_id,
                order_date as ordered_at,
                substr(order_date, 1, 10) as order_date,
                order_value,
                lower(trim(order_status)) as order_status
            from raw_orders
            where order_value > 0
        ),
        deduplicated_orders as (
            select
                order_id,
                user_id,
                ordered_at,
                order_date,
                order_value,
                order_status,
                row_number() over (
                    partition by order_id
                    order by
                        case when order_status = 'completed' then 1 else 2 end asc,
                        ordered_at desc,
                        order_value desc
                ) as order_attempt_rank
            from parsed_orders
        )
        select order_id, user_id, ordered_at, order_date, order_value, order_status
        from deduplicated_orders
        where order_attempt_rank = 1;
    """)

    conn.execute("""
        create table int_user_first_purchase as
        with completed_orders as (
            select * from stg_orders where order_status = 'completed'
        ),
        first_orders as (
            select
                user_id,
                order_id,
                order_date,
                row_number() over (partition by user_id order by order_date asc, order_id asc) as rn
            from completed_orders
        )
        select
            u.user_id,
            u.signup_date,
            u.cohort_month,
            f.order_id as first_order_id,
            f.order_date as first_order_date
        from stg_users u
        left join first_orders f on u.user_id = f.user_id and f.rn = 1;
    """)

    conn.execute("""
        create table monthly_cohort_retention as
        with cohort_sizes as (
            select cohort_month, count(distinct user_id) as cohort_size
            from int_user_first_purchase
            group by cohort_month
        ),
        max_obs as (
            select max(m) as max_month from (
                select max(cohort_month) as m from cohort_sizes
                union
                select max(substr(order_date, 1, 7) || '-01') as m from stg_orders
                union
                select max(cohort_month) as m from stg_users
            )
        ),
        cohort_months_list as (
            select distinct cohort_month, cohort_size from cohort_sizes
        ),
        spine as (
            select c.cohort_month, c.cohort_size, m.month_num
            from cohort_months_list c
            cross join (
                select 0 as month_num union select 1 union select 2 union select 3 union select 4
                union select 5 union select 6 union select 7 union select 8 union select 9
                union select 10 union select 11
            ) m
            where date(c.cohort_month, '+' || m.month_num || ' month') <= (select max_month from max_obs)
        ),
        user_activities as (
            select
                o.user_id,
                u.cohort_month,
                substr(o.order_date, 1, 7) || '-01' as activity_month
            from stg_orders o
            inner join int_user_first_purchase u on o.user_id = u.user_id
            where o.order_status = 'completed'
            group by o.user_id, u.cohort_month, substr(o.order_date, 1, 7) || '-01'
        ),
        cohort_act as (
            select cohort_month, activity_month, count(distinct user_id) as active_users
            from user_activities
            group by cohort_month, activity_month
        )
        select
            s.cohort_month,
            s.cohort_size,
            s.month_num as month_number,
            coalesce(a.active_users, 0) as active_users,
            round((coalesce(a.active_users, 0) * 100.0 / s.cohort_size), 2) as retention_pct
        from spine s
        left join cohort_act a on s.cohort_month = a.cohort_month
          and date(s.cohort_month, '+' || s.month_num || ' month') = a.activity_month
        order by s.cohort_month, s.month_num;
    """)

    conn.execute("""
        create table int_sessionized_events as
        with sorted as (
            select
                session_id,
                user_id,
                event_name,
                event_timestamp,
                row_number() over (partition by session_id order by event_timestamp asc, event_id asc) as rn
            from raw_events
        ),
        sess_agg as (
            select
                session_id,
                user_id,
                min(event_timestamp) as session_start_at,
                max(event_timestamp) as session_end_at,
                count(*) as total_events,
                max(case when event_name = 'page_view' then 1 else 0 end) as has_page_view,
                max(case when event_name = 'add_to_cart' then 1 else 0 end) as has_add_to_cart,
                max(case when event_name = 'purchase' then 1 else 0 end) as has_purchase,
                min(case when event_name = 'page_view' then event_timestamp end) as first_pv,
                min(case when event_name = 'add_to_cart' then event_timestamp end) as first_cart,
                min(case when event_name = 'purchase' then event_timestamp end) as first_purch
            from sorted
            group by session_id, user_id
        )
        select
            session_id,
            user_id,
            has_page_view,
            case when has_page_view = 1 and has_add_to_cart = 1 and first_pv <= first_cart then 1 else 0 end as has_sequential_cart,
            case when has_page_view = 1 and has_add_to_cart = 1 and has_purchase = 1 and first_pv <= first_cart and first_cart <= first_purch then 1 else 0 end as has_sequential_purchase
        from sess_agg;
    """)

    conn.execute("""
        create table funnel_summary as
        with steps as (
            select
                1 as funnel_step_order,
                'page_view' as funnel_step,
                count(distinct case when has_page_view = 1 then session_id end) as session_count
            from int_sessionized_events
            union all
            select
                2 as funnel_step_order,
                'add_to_cart' as funnel_step,
                count(distinct case when has_sequential_cart = 1 then session_id end) as session_count
            from int_sessionized_events
            union all
            select
                3 as funnel_step_order,
                'purchase' as funnel_step,
                count(distinct case when has_sequential_purchase = 1 then session_id end) as session_count
            from int_sessionized_events
        ),
        top_step as (
            select session_count as top_count from steps where funnel_step_order = 1
        )
        select
            s.funnel_step_order,
            s.funnel_step,
            s.session_count,
            round(s.session_count * 100.0 / lag(s.session_count, 1, s.session_count) over (order by s.funnel_step_order), 2) as step_conversion_pct,
            round(s.session_count * 100.0 / (select top_count from top_step), 2) as overall_conversion_pct
        from steps s
        order by s.funnel_step_order;
    """)

    conn.execute("""
        create table fct_revenue_trends as
        with dates_in_scope as (
            select distinct order_date from stg_orders
        ),
        completed_orders as (
            select * from stg_orders where order_status = 'completed'
        )
        select
            d.order_date,
            coalesce(round(sum(c.order_value), 2), 0.00) as total_revenue,
            count(c.order_id) as order_count,
            count(distinct c.user_id) as distinct_user_count,
            coalesce(pg_avg(c.order_value), 0.00) as average_order_value
        from dates_in_scope d
        left join completed_orders c on d.order_date = c.order_date
        group by d.order_date
        order by d.order_date;
    """)

    df_cohort = pd.read_sql("select cohort_month, cohort_size, month_number, active_users, retention_pct from monthly_cohort_retention order by cohort_month, month_number;", conn)
    df_funnel = pd.read_sql("select funnel_step_order, funnel_step, session_count, step_conversion_pct, overall_conversion_pct from funnel_summary order by funnel_step_order;", conn)
    df_rev = pd.read_sql("select order_date, total_revenue, order_count, distinct_user_count, average_order_value from fct_revenue_trends order by order_date;", conn)
    conn.close()

    return df_cohort, df_funnel, df_rev


def load_all_marts() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads marts from warehouse if connected, otherwise computes directly from CSV fixtures."""
    try:
        conn = get_db_connection()
    except (ValueError, psycopg2.OperationalError) as conn_err:
        print(f"Note: PostgreSQL unavailable ({conn_err}); computing marts directly from CSV fixtures.")
        return compute_marts_from_fixtures()

    try:
        with conn:
            df_cohort = pd.read_sql(
                "select cohort_month::text, cohort_size, month_number, active_users, retention_pct from public_marts.monthly_cohort_retention order by cohort_month, month_number;",
                conn
            )
            df_funnel = pd.read_sql(
                "select funnel_step_order, funnel_step, session_count, step_conversion_pct, overall_conversion_pct from public_marts.funnel_summary order by funnel_step_order;",
                conn
            )
            df_rev = pd.read_sql(
                "select order_date, total_revenue, order_count, distinct_user_count, average_order_value from public_marts.fct_revenue_trends order by order_date;",
                conn
            )
        return df_cohort, df_funnel, df_rev
    finally:
        conn.close()


def render_cohort_retention_chart(df_cohort: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    palette = sns.color_palette("tab10", len(df_cohort['cohort_month'].unique()))
    
    for idx, (cohort, group) in enumerate(df_cohort.groupby('cohort_month')):
        ax.plot(
            group['month_number'],
            group['retention_pct'],
            marker='o',
            linewidth=2.2,
            label=f"Cohort {cohort[:7]} (N={group['cohort_size'].iloc[0]})",
            color=palette[idx]
        )

    ax.set_title("Customer Cohort Retention Curves (by Acquisition Month)")
    ax.set_xlabel("Elapsed Months Since Signup (Month 0 = Acquisition)")
    ax.set_ylabel("Retention Rate (%)")
    ax.set_ylim(0, 105)
    ax.set_xlim(-0.2, 11.2)
    ax.set_xticks(range(0, 12))
    ax.legend(title="Acquisition Cohort", bbox_to_anchor=(1.04, 1), loc="upper left", frameon=True)
    ax.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    output_path = SCREENSHOTS_DIR / "dashboard_cohort.png"
    plt.savefig(output_path, dpi=300)
    plt.close()


def render_funnel_chart(df_funnel: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 6), dpi=300)
    colors = ['#2b5c8f', '#4682b4', '#5dade2']
    bars = ax.bar(
        df_funnel['funnel_step'],
        df_funnel['session_count'],
        color=colors,
        width=0.55,
        edgecolor='#1b3b5f',
        linewidth=1.2
    )

    for bar, row in zip(bars, df_funnel.itertuples()):
        height = bar.get_height()
        ax.annotate(
            f"{row.session_count:,} sessions\nStep: {row.step_conversion_pct:.1f}%\nOverall: {row.overall_conversion_pct:.1f}%",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 6),
            textcoords="offset points",
            ha='center', va='bottom',
            fontsize=10,
            fontweight='bold',
            color='#1f2937'
        )

    ax.set_title("E-Commerce User Conversion Funnel")
    ax.set_xlabel("Funnel Milestone")
    ax.set_ylabel("Total Unique Sessions")
    ax.set_ylim(0, max(df_funnel['session_count']) * 1.25)
    ax.grid(axis='y', linestyle="--", alpha=0.5)

    plt.tight_layout()
    output_path = SCREENSHOTS_DIR / "dashboard_funnel.png"
    plt.savefig(output_path, dpi=300)
    plt.close()


def render_revenue_trends_chart(df_rev: pd.DataFrame):
    df_rev = df_rev.copy()
    df_rev['order_date'] = pd.to_datetime(df_rev['order_date'])
    df_rev['revenue_7d_ma'] = df_rev['total_revenue'].rolling(window=7, min_periods=1).mean()
    df_rev['aov_7d_ma'] = df_rev['average_order_value'].rolling(window=7, min_periods=1).mean()

    fig, ax1 = plt.subplots(figsize=(11, 6), dpi=300)
    color_rev = '#1f77b4'
    ax1.plot(df_rev['order_date'], df_rev['total_revenue'], color=color_rev, alpha=0.3, label='Daily Revenue ($)')
    ax1.plot(df_rev['order_date'], df_rev['revenue_7d_ma'], color=color_rev, linewidth=2.4, label='7-Day Rolling Revenue ($)')
    ax1.set_xlabel('Order Date (2023)')
    ax1.set_ylabel('Daily Revenue ($)', color=color_rev, fontweight='bold')
    ax1.tick_params(axis='y', labelcolor=color_rev)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))

    ax2 = ax1.twinx()
    color_aov = '#ff7f0e'
    ax2.plot(df_rev['order_date'], df_rev['aov_7d_ma'], color=color_aov, linewidth=2.0, linestyle='--', label='7-Day Rolling AOV ($)')
    ax2.set_ylabel('Average Order Value ($)', color=color_aov, fontweight='bold')
    ax2.tick_params(axis='y', labelcolor=color_aov)

    ax1.set_title('Daily Revenue Trends & Average Order Value (AOV)')
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    output_path = SCREENSHOTS_DIR / "dashboard_revenue.png"
    plt.savefig(output_path, dpi=300)
    plt.close()


def render_full_dashboard(df_cohort: pd.DataFrame, df_funnel: pd.DataFrame, df_rev: pd.DataFrame):
    df_rev = df_rev.copy()
    df_rev['order_date'] = pd.to_datetime(df_rev['order_date'])
    df_rev['revenue_7d_ma'] = df_rev['total_revenue'].rolling(window=7, min_periods=1).mean()

    fig = plt.figure(figsize=(16, 11), dpi=300)
    fig.patch.set_facecolor('#f8fafc')
    fig.suptitle("E-Commerce Analytics Pipeline — Executive Metabase Dashboard", fontsize=18, fontweight='bold', y=0.98, color='#0f172a')

    # Panel 1: Revenue Trends
    ax1 = plt.subplot2grid((2, 2), (0, 0))
    ax1.set_facecolor('#ffffff')
    ax1.plot(df_rev['order_date'], df_rev['total_revenue'], color='#3b82f6', alpha=0.25, label='Daily Revenue')
    ax1.plot(df_rev['order_date'], df_rev['revenue_7d_ma'], color='#1d4ed8', linewidth=2.2, label='7D Moving Avg')
    ax1.set_title("Gross Daily Revenue & Holiday Surge ($)")
    ax1.set_xlabel("Order Date (2023)")
    ax1.set_ylabel("Revenue ($)")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax1.legend(loc='upper left', frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.4)

    # Panel 2: Funnel Drop-off
    ax2 = plt.subplot2grid((2, 2), (0, 1))
    ax2.set_facecolor('#ffffff')
    bars = ax2.bar(
        df_funnel['funnel_step'],
        df_funnel['session_count'],
        color=['#3b82f6', '#06b6d4', '#10b981'],
        width=0.55,
        edgecolor='#1e293b'
    )
    for bar, row in zip(bars, df_funnel.itertuples()):
        height = bar.get_height()
        ax2.annotate(
            f"{row.session_count:,}\n({row.overall_conversion_pct:.1f}% overall)",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 4),
            textcoords="offset points",
            ha='center', va='bottom',
            fontsize=9,
            fontweight='bold',
            color='#0f172a'
        )
    ax2.set_title("User Conversion Funnel (Drop-off Analysis)")
    ax2.set_ylabel("Unique Sessions")
    ax2.set_ylim(0, max(df_funnel['session_count']) * 1.25)
    ax2.grid(axis='y', linestyle="--", alpha=0.4)

    # Panel 3: Cohort Retention Matrix Heatmap
    ax3 = plt.subplot2grid((2, 2), (1, 0))
    ax3.set_facecolor('#ffffff')
    cohort_pivot = df_cohort.pivot(index='cohort_month', columns='month_number', values='retention_pct')
    cohort_pivot.index = [d[:7] for d in cohort_pivot.index]
    sns.heatmap(cohort_pivot, annot=True, fmt=".1f", cmap="YlGnBu", cbar=True, ax=ax3, vmin=0, vmax=100)
    ax3.set_title("Monthly Cohort Retention Heatmap (%)")
    ax3.set_xlabel("Elapsed Months Since Acquisition")
    ax3.set_ylabel("Acquisition Cohort")

    # Panel 4: Cohort Retention Curves
    ax4 = plt.subplot2grid((2, 2), (1, 1))
    ax4.set_facecolor('#ffffff')
    palette = sns.color_palette("Set2", len(df_cohort['cohort_month'].unique()))
    for idx, (cohort, group) in enumerate(df_cohort.groupby('cohort_month')):
        if idx in [0, 2, 5, 8, 10]:
            ax4.plot(
                group['month_number'],
                group['retention_pct'],
                marker='o',
                linewidth=2.0,
                label=f"Cohort {cohort[:7]}",
                color=palette[idx]
            )
    ax4.set_title("Cohort Retention Decay Curves")
    ax4.set_xlabel("Elapsed Months")
    ax4.set_ylabel("Retention Rate (%)")
    ax4.set_ylim(0, 105)
    ax4.legend(loc="upper right", frameon=True, fontsize=9)
    ax4.grid(True, linestyle="--", alpha=0.4)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    output_path = SCREENSHOTS_DIR / "dashboard_full.png"
    plt.savefig(output_path, dpi=300)
    plt.close()


if __name__ == "__main__":
    df_cohort, df_funnel, df_rev = load_all_marts()
    render_cohort_retention_chart(df_cohort)
    render_funnel_chart(df_funnel)
    render_revenue_trends_chart(df_rev)
    render_full_dashboard(df_cohort, df_funnel, df_rev)
    print("Dashboard screenshots rendered in screenshots/.")
