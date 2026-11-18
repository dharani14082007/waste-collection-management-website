"""
preprocess.py
Cleans, transforms and enriches raw DataFrames for analysis and visualization.
"""
import pandas as pd
import numpy as np
from db_connection import get_connection, close_connection
from retrieve_data import fetch_all_collections


def preprocess_collections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and enriches the main collections DataFrame.

    Steps
    -----
    1. Convert date columns to datetime.
    2. Create year_month, month_name, weekday columns.
    3. Fill missing quantity_kg with 0.
    4. Remove duplicate detail rows.
    5. Detect outliers using IQR on quantity_kg.
    6. Calculate vehicle utilization percentage per collection.
    """
    df = df.copy()

    # 1. Parse dates
    df["scheduled_date"] = pd.to_datetime(df["scheduled_date"], errors="coerce")
    df["actual_date"]    = pd.to_datetime(df["actual_date"],    errors="coerce")

    # 2. Time-based features
    df["year_month"] = df["scheduled_date"].dt.to_period("M").astype(str)
    df["month_name"] = df["scheduled_date"].dt.strftime("%b %Y")
    df["weekday"]    = df["scheduled_date"].dt.day_name()

    # 3. Fill missing quantities
    df["quantity_kg"]     = pd.to_numeric(df["quantity_kg"],     errors="coerce").fillna(0.0)
    df["total_weight_kg"] = pd.to_numeric(df["total_weight_kg"], errors="coerce").fillna(0.0)
    df["capacity_kg"]     = pd.to_numeric(df["capacity_kg"],     errors="coerce")

    # 4. Remove duplicate detail rows
    before = len(df)
    df = df.drop_duplicates(subset=["collection_id", "category_name"])
    after = len(df)
    if before != after:
        print(f"[preprocess] Removed {before - after} duplicate rows.")

    # 5. Outlier detection (IQR on non-zero quantities)
    qty = df.loc[df["quantity_kg"] > 0, "quantity_kg"]
    if len(qty) > 0:
        q1, q3 = qty.quantile(0.25), qty.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers = df[(df["quantity_kg"] > 0) &
                      ((df["quantity_kg"] < lower) | (df["quantity_kg"] > upper))]
        if not outliers.empty:
            print(f"[preprocess] {len(outliers)} outliers detected (IQR). Retained for review.")

    # 6. Vehicle utilization percentage
    df["utilization_pct"] = np.where(
        df["capacity_kg"] > 0,
        (df["total_weight_kg"] / df["capacity_kg"] * 100).round(2),
        0.0,
    )

    print(f"[preprocess] Complete. Shape: {df.shape}")
    return df


def get_area_waste_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Total waste per area (completed, deduplicated by collection_id)."""
    completed = df[df["collection_status"] == "Completed"].copy()
    return (
        completed.drop_duplicates(subset=["collection_id"])
        .groupby("area_name")["total_weight_kg"]
        .sum()
        .reset_index()
        .sort_values("total_weight_kg", ascending=False)
    )


def get_category_distribution(df: pd.DataFrame) -> pd.Series:
    """Total waste quantity per category (completed collections)."""
    completed = df[df["collection_status"] == "Completed"].copy()
    return (
        completed.groupby("category_name")["quantity_kg"]
        .sum()
        .sort_values(ascending=False)
    )


def get_monthly_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly waste totals (completed, deduplicated)."""
    completed = df[df["collection_status"] == "Completed"].copy()
    return (
        completed.drop_duplicates(subset=["collection_id"])
        .groupby("year_month")["total_weight_kg"]
        .sum()
        .reset_index()
        .sort_values("year_month")
    )


def get_stacked_category_by_area(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot: area × category with quantity sums."""
    completed = df[df["collection_status"] == "Completed"].copy()
    return (
        completed.groupby(["area_name", "category_name"])["quantity_kg"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )


def get_vehicle_utilization(df: pd.DataFrame) -> pd.DataFrame:
    """Per-vehicle utilization metrics."""
    completed = df[(df["collection_status"] == "Completed") &
                   (df["registration_number"].notna())].copy()
    veh = (
        completed.drop_duplicates(subset=["collection_id"])
        .groupby(["registration_number", "vehicle_type", "capacity_kg"])
        .agg(total_runs=("collection_id", "count"), total_waste=("total_weight_kg", "sum"))
        .reset_index()
    )
    veh["avg_load_pct"] = (
        veh["total_waste"] / (veh["total_runs"] * veh["capacity_kg"]) * 100
    ).round(2)
    return veh.sort_values("avg_load_pct", ascending=False)


def get_status_counts(df: pd.DataFrame) -> pd.Series:
    """Count per collection status."""
    return df.drop_duplicates(subset=["collection_id"])["collection_status"].value_counts()


def get_heatmap_data(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot: area × month with total waste (completed)."""
    completed = df[df["collection_status"] == "Completed"].copy()
    return (
        completed.drop_duplicates(subset=["collection_id"])
        .groupby(["area_name", "year_month"])["total_weight_kg"]
        .sum()
        .unstack(fill_value=0)
    )


if __name__ == "__main__":
    conn = get_connection()
    try:
        raw   = fetch_all_collections(conn)
        clean = preprocess_collections(raw)
        print("\n--- Area Waste Totals ---")
        print(get_area_waste_totals(clean))
        print("\n--- Category Distribution ---")
        print(get_category_distribution(clean))
        print("\n--- Monthly Totals ---")
        print(get_monthly_totals(clean))
        print("\n--- Status Counts ---")
        print(get_status_counts(clean))
    finally:
        close_connection(conn)
