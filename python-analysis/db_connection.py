"""
db_connection.py
Provides a MySQL database connection factory for the Python analytics module.
Credentials are loaded from environment variables via a .env file.
"""
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """
    Creates and returns a MySQL database connection.
    Configuration read from environment variables: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD.

    Returns
    -------
    mysql.connector.connection.MySQLConnection

    Raises
    ------
    RuntimeError if connection cannot be established.
    """
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "waste_management_db"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            charset="utf8mb4",
            use_unicode=True,
        )
        if conn.is_connected():
            print(f"[DB] Connected to {os.getenv('DB_NAME')} on {os.getenv('DB_HOST')}")
        return conn
    except Error as e:
        raise RuntimeError(f"Failed to connect to database: {e}") from e


def close_connection(conn):
    """Closes the database connection if open."""
    if conn and conn.is_connected():
        conn.close()
        print("[DB] Connection closed.")


if __name__ == "__main__":
    connection = get_connection()
    print("Connection test successful.")
    close_connection(connection)
