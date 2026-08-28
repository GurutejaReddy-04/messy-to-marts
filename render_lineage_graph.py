"""Renders a clean, high-resolution dbt DAG lineage diagram as a PNG artifact."""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches

SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def render_dag_lineage():
    fig, ax = plt.subplots(figsize=(15, 8), dpi=300)
    fig.patch.set_facecolor('#ffffff')
    ax.set_facecolor('#f8fafc')

    # Define node layers and coordinates: (x, y)
    nodes = {
        # Sources (Layer 0)
        'raw.users': (1.5, 7.0, '#64748b', 'Source Table\nraw.users'),
        'raw.orders': (1.5, 4.5, '#64748b', 'Source Table\nraw.orders'),
        'raw.events': (1.5, 2.0, '#64748b', 'Source Table\nraw.events'),

        # Staging (Layer 1)
        'stg_users': (5.0, 7.0, '#0284c7', 'Staging View\nstg_users'),
        'stg_orders': (5.0, 4.5, '#0284c7', 'Staging View\nstg_orders'),
        'stg_events': (5.0, 2.0, '#0284c7', 'Staging View\nstg_events'),

        # Intermediate (Layer 2)
        'int_user_first_purchase': (8.8, 6.0, '#7c3aed', 'Intermediate View\nint_user_first_purchase'),
        'int_sessionized_events': (8.8, 2.0, '#7c3aed', 'Intermediate View\nint_sessionized_events'),

        # Marts (Layer 3)
        'monthly_cohort_retention': (12.5, 7.0, '#059669', 'Mart Table\nmonthly_cohort_retention'),
        'fct_revenue_trends': (12.5, 4.5, '#d97706', 'Incremental Mart\nfct_revenue_trends'),
        'funnel_summary': (12.5, 2.0, '#059669', 'Mart Table\nfunnel_summary'),
    }

    # Directed edges: (from_node, to_node)
    edges = [
        ('raw.users', 'stg_users'),
        ('raw.orders', 'stg_orders'),
        ('raw.events', 'stg_events'),
        
        ('stg_users', 'int_user_first_purchase'),
        ('stg_orders', 'int_user_first_purchase'),
        ('stg_events', 'int_sessionized_events'),
        
        ('int_user_first_purchase', 'monthly_cohort_retention'),
        ('stg_orders', 'monthly_cohort_retention'),
        ('stg_orders', 'fct_revenue_trends'),
        ('int_sessionized_events', 'funnel_summary'),
    ]

    # Draw edges with curved arrows
    for src, dst in edges:
        x1, y1, _, _ = nodes[src]
        x2, y2, _, _ = nodes[dst]
        
        # Calculate box offset for arrow connection
        dx = (x2 - x1)
        ax.annotate(
            '',
            xy=(x2 - 1.1, y2),
            xytext=(x1 + 1.1, y1),
            arrowprops=dict(
                arrowstyle="-|>",
                color="#94a3b8",
                lw=2.0,
                mutation_scale=18,
                connectionstyle="arc3,rad=0.0"
            )
        )

    # Draw nodes as styled rounded boxes
    for name, (x, y, color, label) in nodes.items():
        box = patches.FancyBboxPatch(
            (x - 1.05, y - 0.55),
            2.1, 1.1,
            boxstyle="round,pad=0.15,rounding_size=0.15",
            facecolor='#ffffff',
            edgecolor=color,
            linewidth=2.5,
            zorder=3
        )
        ax.add_patch(box)
        
        # Add colored top badge line
        badge = patches.FancyBboxPatch(
            (x - 1.05, y + 0.35),
            2.1, 0.2,
            boxstyle="round,pad=0.05,rounding_size=0.08",
            facecolor=color,
            edgecolor=color,
            zorder=4
        )
        ax.add_patch(badge)

        ax.text(
            x, y - 0.08,
            label,
            ha='center', va='center',
            fontsize=9.5,
            fontweight='bold',
            color='#1e293b',
            zorder=5
        )

    # Layer section headers
    headers = [
        (1.5, 8.3, 'RAW SOURCES', '#64748b'),
        (5.0, 8.3, 'STAGING LAYER\n(Cleaning & Type Casting)', '#0284c7'),
        (8.8, 8.3, 'INTERMEDIATE LAYER\n(Business Logic Joins)', '#7c3aed'),
        (12.5, 8.3, 'MARTS LAYER\n(BI-Ready Analytics)', '#059669'),
    ]

    for x, y, text, col in headers:
        ax.text(
            x, y, text,
            ha='center', va='center',
            fontsize=11,
            fontweight='heavy',
            color=col
        )
        ax.axvline(x=x + 1.85, color='#e2e8f0', linestyle=':', lw=1.5, ymin=0.05, ymax=0.92)

    ax.set_xlim(-0.2, 14.2)
    ax.set_ylim(0.5, 9.2)
    ax.axis('off')
    ax.set_title("dbt Transformation Pipeline — Directed Acyclic Graph (DAG)", fontsize=15, fontweight='bold', pad=20, color='#0f172a')

    plt.tight_layout()
    out_path = SCREENSHOTS_DIR / "dbt_lineage.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    render_dag_lineage()
