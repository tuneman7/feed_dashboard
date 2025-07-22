# streamlit_app.py
"""
Pipeline Management System - Streamlit Admin Interface
"""
import streamlit as st
import os
from dotenv import load_dotenv
import uuid

# Import modular components
from database_setup import admin_database_setup
from system_codes import admin_system_codes
from pipeline_management import admin_pipelines
from dashboard import dashboard
from visualizations import visualizations_page
from database_utils import init_connection, DB_CONFIG

# Force cache clear at startup
os.environ["CACHE_BUSTER"] = str(uuid.uuid4())

# Load environment variables
load_dotenv()

# Configure Streamlit page
st.set_page_config(
    page_title="Pipeline Management Admin",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    """Main application"""
    st.title("🔧 Pipeline Management System - Admin Interface")
    
    # Sidebar navigation
    st.sidebar.title("🧭 Navigation")
    page = st.sidebar.selectbox(
        "Choose a section",
        ["Dashboard", "Database Setup", "System Codes", "Pipeline Management", "Visualizations"]
    )
    
    # Database connection info in sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔌 Database Info")
    st.sidebar.text(f"Host: {DB_CONFIG['host']}")
    st.sidebar.text(f"Database: {DB_CONFIG['database']}")
    st.sidebar.text(f"User: {DB_CONFIG['user']}")
    
    # Test connection
    conn = init_connection()
    if conn:
        st.sidebar.success("✅ Connected")
    else:
        st.sidebar.error("❌ Not Connected")
    
    # Route to appropriate page
    if page == "Dashboard":
        dashboard()
    elif page == "Database Setup":
        admin_database_setup()
    elif page == "System Codes":
        admin_system_codes()
    elif page == "Pipeline Management":
        admin_pipelines()
    elif page == "Visualizations":
        visualizations_page()

if __name__ == "__main__":
    main()