"""
visualize.py
Generates eight analytical charts and saves them to visualizations/.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import pandas as pd
import numpy as np
from db_connection import get_connection, close_connection
from retrieve_data import fetch_all_collections
from preprocess import (
    preprocess_collections, get_area_waste_totals, get_category_distribution,
    get_monthly_totals, get_stacked_category_by_area, get_vehicle_utilization,
    get_status_counts, get_heatmap_data,
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visualizations")
os.makedirs(OUTPUT_DIR, exist_ok=True)

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
COLORS = sns.color_palette("Set2", 10)


def save_fig(filename: str, fig=None):
    path = os.path.join(OUTPUT_DIR, filename)
    (fig or plt).savefig(path, dpi=150, bbox_inches="tight")
    print(f"[visualize] Saved: {path}")
    plt.close("all")


# ── Chart 1: Bar – Total waste by area ───────────────────────────────────────
def chart1_area_waste_totals(df):
    area_totals = get_area_waste_totals(df)
    fig, ax = plt.subplots(figsize=(14, 6))
    bars = ax.bar(area_totals["area_name"], area_totals["total_weight_kg"],
                  color=COLORS[0], edgecolor="white")
    ax.set_title("Total Waste Collected by Residential Area", fontsize=15, fontweight="bold", pad=15)
    ax.set_xlabel("Residential Area", fontsize=12)
    ax.set_ylabel("Total Waste (kg)", fontsize=12)
    ax.tick_params(axis="x", rotation=45)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 50,
                f"{bar.get_height():,.0f}", ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    save_fig("chart1_area_waste_totals.png", fig)


# ── Chart 2: Donut – Waste category distribution ─────────────────────────────
def chart2_category_distribution(df):
    cat_dist = get_category_distribution(df)
    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(
        cat_dist.values, labels=cat_dist.index,
        autopct="%1.1f%%", startangle=90,
        colors=[COLORS[1], COLORS[2], COLORS[3]],
        wedgeprops={"width": 0.5, "edgecolor": "white"},
        pctdistance=0.75,
    )
    for t in autotexts:
        t.set_fontsize(11); t.set_fontweight("bold")
    ax.set_title("Waste Category Distribution (by Total kg)", fontsize=14, fontweight="bold", pad=20)
    ax.legend(cat_dist.index, loc="lower right", fontsize=11)
    save_fig("chart2_category_distribution.png", fig)


# ── Chart 3: Line – Monthly waste generation ─────────────────────────────────
def chart3_monthly_trends(df):
    monthly = get_monthly_totals(df)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(monthly["year_month"], monthly["total_weight_kg"],
            marker="o", linewidth=2.5, color=COLORS[4], markersize=8)
    ax.fill_between(monthly["year_month"], monthly["total_weight_kg"], alpha=0.15, color=COLORS[4])
    ax.set_title("Monthly Waste Generation Trend (Completed Collections)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Month", fontsize=12)
    ax.set_ylabel("Total Waste (kg)", fontsize=12)
    ax.tick_params(axis="x", rotation=30)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    for i, row in monthly.iterrows():
        ax.annotate(f"{row['total_weight_kg']:,.0f}",
                    (row["year_month"], row["total_weight_kg"]),
                    textcoords="offset points", xytext=(0, 10), ha="center", fontsize=8)
    plt.tight_layout()
    save_fig("chart3_monthly_trends.png", fig)


# ── Chart 4: Stacked bar – Category by area ───────────────────────────────────
def chart4_stacked_category_by_area(df):
    pivot = get_stacked_category_by_area(df).set_index("area_name")
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total", ascending=False).drop(columns="total")
    fig, ax = plt.subplots(figsize=(15, 7))
    colors_map = {"Biodegradable": COLORS[1], "Recyclable": COLORS[2], "Non-Recyclable": COLORS[3]}
    bottom = pd.Series([0.0] * len(pivot), index=pivot.index)
    for col in pivot.columns:
        ax.bar(pivot.index, pivot[col], bottom=bottom, label=col, color=colors_map.get(col, COLORS[0]))
        bottom = bottom + pivot[col]
    ax.set_title("Waste Category Breakdown by Residential Area", fontsize=14, fontweight="bold")
    ax.set_xlabel("Residential Area", fontsize=12)
    ax.set_ylabel("Total Quantity (kg)", fontsize=12)
    ax.tick_params(axis="x", rotation=45)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.legend(title="Category", fontsize=10)
    plt.tight_layout()
    save_fig("chart4_stacked_category_by_area.png", fig)


# ── Chart 5: Bar – Vehicle utilization ───────────────────────────────────────
def chart5_vehicle_utilization(df):
    veh = get_vehicle_utilization(df)
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = [COLORS[5] if p < 50 else COLORS[0] for p in veh["avg_load_pct"]]
    bars = ax.bar(veh["registration_number"], veh["avg_load_pct"], color=colors, edgecolor="white")
    ax.axhline(y=50, color="red", linestyle="--", linewidth=1.5, label="50% threshold")
    ax.set_title("Vehicle Utilization (Avg Load % of Capacity)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Vehicle Registration", fontsize=12)
    ax.set_ylabel("Average Load (%)", fontsize=12)
    ax.tick_params(axis="x", rotation=30)
    ax.set_ylim(0, 100)
    ax.legend()
    for bar, row in zip(bars, veh.itertuples()):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{row.avg_load_pct:.1f}%", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    save_fig("chart5_vehicle_utilization.png", fig)


# ── Chart 6: Status distribution ─────────────────────────────────────────────
def chart6_collection_status(df):
    status_counts = get_status_counts(df)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    ax1.pie(status_counts.values, labels=status_counts.index, autopct="%1.1f%%", startangle=90,
            colors=COLORS[:len(status_counts)], wedgeprops={"edgecolor": "white"})
    ax1.set_title("Collection Status Distribution", fontsize=13, fontweight="bold")
    ax2.bar(status_counts.index, status_counts.values, color=COLORS[:len(status_counts)], edgecolor="white")
    ax2.set_title("Collection Status Counts", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Status")
    ax2.set_ylabel("Number of Collections")
    for i, (label, val) in enumerate(status_counts.items()):
        ax2.text(i, val + 1, str(val), ha="center", fontsize=10, fontweight="bold")
    plt.suptitle("Collection Completion Analysis", fontsize=15, fontweight="bold", y=1.02)
    plt.tight_layout()
    save_fig("chart6_collection_status.png", fig)


# ── Chart 7: Heatmap – Area vs Month ─────────────────────────────────────────
def chart7_heatmap_area_month(df):
    heatmap_data = get_heatmap_data(df)
    heatmap_data["total"] = heatmap_data.sum(axis=1)
    heatmap_data = heatmap_data.nlargest(10, "total").drop(columns="total")
    fig, ax = plt.subplots(figsize=(14, 7))
    sns.heatmap(heatmap_data, ax=ax, cmap="YlOrRd", fmt=".0f", annot=True,
                linewidths=0.5, cbar_kws={"label": "Total Waste (kg)"})
    ax.set_title("Monthly Waste Heatmap – Top 10 Areas (kg)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Month", fontsize=12)
    ax.set_ylabel("Residential Area", fontsize=12)
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    save_fig("chart7_heatmap_area_month.png", fig)


# ── Chart 8: Box plot – Quantity by waste type ────────────────────────────────
def chart8_boxplot_quantity_by_type(df):
    completed = df[(df["collection_status"] == "Completed") & (df["quantity_kg"] > 0)].copy()
    categories = sorted(completed["category_name"].dropna().unique())
    data_by_cat = [completed[completed["category_name"] == c]["quantity_kg"].values for c in categories]
    fig, ax = plt.subplots(figsize=(10, 6))
    bp = ax.boxplot(data_by_cat, tick_labels=categories, patch_artist=True,
                    medianprops={"color": "black", "linewidth": 2})
    for patch, color in zip(bp["boxes"], [COLORS[1], COLORS[2], COLORS[3]]):
        patch.set_facecolor(color); patch.set_alpha(0.7)
    ax.set_title("Distribution of Waste Quantity per Collection by Category",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("Waste Category", fontsize=12)
    ax.set_ylabel("Quantity (kg)", fontsize=12)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    plt.tight_layout()
    save_fig("chart8_boxplot_quantity_by_type.png", fig)


def run_all_charts(df: pd.DataFrame):
    """Executes all eight chart generators in sequence."""
    print("\n[visualize] Generating 8 charts...")
    chart1_area_waste_totals(df)
    chart2_category_distribution(df)
    chart3_monthly_trends(df)
    chart4_stacked_category_by_area(df)
    chart5_vehicle_utilization(df)
    chart6_collection_status(df)
    chart7_heatmap_area_month(df)
    chart8_boxplot_quantity_by_type(df)
    print(f"\n[visualize] All 8 charts saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    conn = get_connection()
    try:
        raw   = fetch_all_collections(conn)
        clean = preprocess_collections(raw)
        run_all_charts(clean)
    finally:
        close_connection(conn)
