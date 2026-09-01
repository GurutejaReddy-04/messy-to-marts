"""Renders BI dashboard charts from PostgreSQL marts."""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd

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


def get_db_connection():
    """Retrieve an authenticated PostgreSQL database connection via centralized configuration."""
    return db_config.get_db_connection()


def render_cohort_retention_chart():
    conn = get_db_connection()
    query = """
        select
            cohort_month::text,
            cohort_size,
            month_number,
            active_users,
            retention_pct
        from public_marts.monthly_cohort_retention
        order by cohort_month, month_number;
    """
    df_cohort = pd.read_sql(query, conn)
    conn.close()

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


def render_funnel_chart():
    conn = get_db_connection()
    query = """
        select
            funnel_step_order,
            funnel_step,
            session_count,
            step_conversion_pct,
            overall_conversion_pct
        from public_marts.funnel_summary
        order by funnel_step_order;
    """
    df_funnel = pd.read_sql(query, conn)
    conn.close()

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


def render_revenue_trends_chart():
    conn = get_db_connection()
    query = """
        select
            order_date,
            total_revenue,
            order_count,
            distinct_user_count,
            average_order_value
        from public_marts.fct_revenue_trends
        order by order_date;
    """
    df_rev = pd.read_sql(query, conn)
    conn.close()

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


def render_full_dashboard():
    conn = get_db_connection()
    df_cohort = pd.read_sql("select cohort_month::text, month_number, retention_pct, cohort_size from public_marts.monthly_cohort_retention order by cohort_month, month_number;", conn)
    df_funnel = pd.read_sql("select funnel_step, session_count, step_conversion_pct, overall_conversion_pct from public_marts.funnel_summary order by funnel_step_order;", conn)
    df_rev = pd.read_sql("select order_date, total_revenue, order_count, average_order_value from public_marts.fct_revenue_trends order by order_date;", conn)
    conn.close()

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
    render_cohort_retention_chart()
    render_funnel_chart()
    render_revenue_trends_chart()
    render_full_dashboard()
    print("Dashboard screenshots rendered in screenshots/.")
