"""
retrieve_data.py
Retrieves raw data from the MySQL database into pandas DataFrames.
Uses cursor-based approach compatible with mysql-connector-python v8+/v26+.
"""
import pandas as pd
from db_connection import get_connection, close_connection


def _query_to_df(conn, query: str) -> pd.DataFrame:
    """Helper: executes a query and returns a DataFrame using cursor (connector-agnostic)."""
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    cols = [d[0] for d in cursor.description]
    cursor.close()
    return pd.DataFrame(rows, columns=cols)


def fetch_all_collections(conn) -> pd.DataFrame:
    """Fetches all collection records joined with area, vehicle and category details."""
    query = """
        SELECT
            c.collection_id,
            a.area_name,
            a.zone,
            a.population,
            v.vehicle_id,
            v.registration_number,
            v.vehicle_type,
            v.capacity_kg,
            v.status            AS vehicle_status,
            c.scheduled_date,
            c.actual_date,
            c.status            AS collection_status,
            c.total_weight_kg,
            wc.category_name,
            cd.quantity_kg
        FROM collection c
        INNER JOIN area a         ON c.area_id      = a.area_id
        LEFT  JOIN vehicle v      ON c.vehicle_id   = v.vehicle_id
        LEFT  JOIN collection_detail cd ON c.collection_id = cd.collection_id
        LEFT  JOIN waste_category wc    ON cd.category_id  = wc.category_id
        ORDER BY c.scheduled_date, c.collection_id
    """
    df = _query_to_df(conn, query)
    print(f"[retrieve] Fetched {len(df)} rows.")
    return df


def fetch_area_summary(conn) -> pd.DataFrame:
    """Fetches area-wise waste summary from the SQL view."""
    return _query_to_df(conn, "SELECT * FROM area_collection_report ORDER BY total_waste_kg DESC")


def fetch_vehicle_summary(conn) -> pd.DataFrame:
    """Fetches vehicle utilization summary from the SQL view."""
    return _query_to_df(conn, "SELECT * FROM vehicle_utilization_report ORDER BY avg_load_pct DESC")


def fetch_completion_summary(conn) -> pd.DataFrame:
    """Fetches collection completion summary from the SQL view."""
    return _query_to_df(conn, "SELECT * FROM collection_completion_report")


def fetch_monthly_trends(conn) -> pd.DataFrame:
    """Fetches monthly category-wise waste generation trends."""
    query = """
        SELECT DATE_FORMAT(c.scheduled_date,'%Y-%m') AS year_month,
               wc.category_name,
               SUM(cd.quantity_kg) AS total_kg
        FROM collection c
        INNER JOIN collection_detail cd ON c.collection_id = cd.collection_id
        INNER JOIN waste_category wc    ON cd.category_id  = wc.category_id
        WHERE c.status = 'Completed'
        GROUP BY year_month, wc.category_name
        ORDER BY year_month, wc.category_name
    """
    return _query_to_df(conn, query)


if __name__ == "__main__":
    conn = get_connection()
    try:
        df = fetch_all_collections(conn)
        print(df.head())
        print(f"Shape: {df.shape}")
    finally:
        close_connection(conn)
