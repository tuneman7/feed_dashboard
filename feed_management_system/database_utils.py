# database_utils.py
"""
Database utilities and connection management
"""
import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'pipeline_management'),
    'user': os.getenv('DB_USER', os.getenv('USER')),
    'password': os.getenv('DB_PASSWORD', '')
}

def create_db_if_missing():
    """Create the target database if it does not exist"""
    from psycopg2 import sql, OperationalError

    try:
        # Try connecting to the target database
        psycopg2.connect(**DB_CONFIG).close()
        return  # Database exists
    except OperationalError as e:
        if f'database "{DB_CONFIG["database"]}" does not exist' not in str(e):
            raise e  # Rethrow any error other than 'does not exist'

    # Attempt to connect to 'postgres' DB to create the target DB
    try:
        fallback_config = DB_CONFIG.copy()
        fallback_config["database"] = "postgres"

        conn = psycopg2.connect(**fallback_config)
        conn.autocommit = True

        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_CONFIG["database"])))
        conn.close()

        print(f"✅ Created missing database '{DB_CONFIG['database']}'.")

    except Exception as ex:
        raise RuntimeError(f"❌ Failed to create database '{DB_CONFIG['database']}': {ex}")

# Initialize database
create_db_if_missing()

@st.cache_resource(hash_funcs={"builtins.str": lambda _: os.getenv("CACHE_BUSTER", "")})
def init_connection():
    """Initialize database connection with caching"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None

def execute_query(query, params=None, fetch=True):
    """Execute database query with error handling"""
    if not query or query.strip() == "":
        return True  # Skip empty query safely
    try:
        # Create a fresh connection for each query to avoid transaction issues
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                result = cur.fetchall()
                conn.close()
                return pd.DataFrame(result) if result else pd.DataFrame()
            else:
                conn.commit()
                conn.close()
                return True
    except Exception as e:
        st.error(f"Query execution failed: {e}")
        return pd.DataFrame() if fetch else False