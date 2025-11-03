"""
database_utils_standalone.py
Database utilities for standalone scripts (no Streamlit dependencies)
"""
import os
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql, OperationalError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "pipeline_management"),
    "user": os.getenv("DB_USER", os.getenv("USER")),
    "password": os.getenv("DB_PASSWORD", ""),
}

def create_db_if_missing():
    """Create the target database if it does not exist."""
    try:
        psycopg2.connect(**DB_CONFIG).close()
        return  # DB exists
    except OperationalError as e:
        if f'database "{DB_CONFIG["database"]}" does not exist' not in str(e):
            raise

    # Connect to 'postgres' to create the target DB
    fallback = dict(DB_CONFIG)
    fallback["database"] = "postgres"
    try:
        conn = psycopg2.connect(**fallback)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_CONFIG["database"])))
        conn.close()
        print(f"✅ Created missing database '{DB_CONFIG['database']}'.")
    except Exception as ex:
        raise RuntimeError(f"❌ Failed to create database '{DB_CONFIG['database']}': {ex}")

# Initialize database (ensure DB exists)
create_db_if_missing()

def init_connection():
    """Initialize database connection with caching (not used by execute_query)."""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

def _should_commit_from_status(status: str) -> bool:
    """
    Decide whether to commit based on cursor.statusmessage.
    Examples:
      'INSERT 0 1', 'UPDATE 3', 'DELETE 1', 'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE'
      'SELECT 1' (no commit)
    """
    if not status:
        return False
    verb = status.split()[0].upper()
    # Treat non-SELECT as write; SELECT/SHOW/EXPLAIN/VALUES are read-only
    return verb not in {"SELECT", "SHOW", "EXPLAIN", "VALUES"}

def execute_query(query: str, params=None, fetch: bool = True, commit: bool | None = None):
    """
    Execute a SQL statement with robust commit behavior.

    - If commit is True -> always commit after execute (even when fetch=True).
    - If commit is False -> never commit here (caller manages).
    - If commit is None (default) -> infer from cursor.statusmessage:
        * commit for INSERT/UPDATE/DELETE/DDL, even with RETURNING
        * don't commit for SELECT/SHOW/EXPLAIN/VALUES

    Returns:
      - DataFrame for fetch=True
      - True/False for fetch=False (success flag)
    """
    if not query or query.strip() == "":
        return True

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)

        # Decide on commit if not explicitly specified
        if commit is None:
            commit = _should_commit_from_status(getattr(cur, "statusmessage", "") or "")

        result_df = pd.DataFrame()
        if fetch:
            # If the statement produced a result set (e.g., SELECT or INSERT ... RETURNING)
            if cur.description is not None:
                rows = cur.fetchall()
                result_df = pd.DataFrame(rows) if rows else pd.DataFrame()
            else:
                # No rows produced (e.g., DDL with fetch=True) – return empty DF
                result_df = pd.DataFrame()

        if commit:
            conn.commit()

        return result_df if fetch else True

    except Exception as e:
        # Roll back any partial transaction
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        print(f"Query execution failed: {e}")
        return pd.DataFrame() if fetch else False

    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass