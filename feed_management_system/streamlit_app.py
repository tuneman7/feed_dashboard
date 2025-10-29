# streamlit_app.py
"""
Pipeline Management System - Streamlit Admin Interface with RDS Authentication
"""
import streamlit as st
import os
from dotenv import load_dotenv
import uuid

# Import RDS authentication module
from rds_auth import (
    require_auth, 
    check_permission, 
    show_user_info, 
    filter_navigation_options, 
    show_access_denied
)

# Import modular components
from database_setup import admin_database_setup
from system_codes import admin_system_codes
from pipeline_management import admin_pipelines
from dashboard import dashboard
from visualizations import visualizations_page
from user_management import user_management_page
from database_utils import init_connection, DB_CONFIG
from alert_management import alert_management_page


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
    """Main application with RDS-based authentication"""
    
    # Check if user is authenticated
    if not require_auth():
        return  # Show login page if not authenticated
    
    # Handle password change flow
    if st.session_state.get("show_password_change", False):
        from rds_auth import show_password_change_form
        show_password_change_form()
        return
    
    # Main app title with user context
    user = st.session_state.user
    st.title("🔧 Pipeline Management System - Admin Interface")
    st.caption(f"Welcome back, {user['name']} ({user['role'].title()})")
    
    # All available pages
    all_pages = ["Dashboard", "Database Setup", "System Codes", "Pipeline Management",
             "Alert Management", "Visualizations", "User Management", "My Profile"]
    
    # Filter pages based on user permissions
    available_pages = filter_navigation_options(all_pages[:-2])  # Exclude User Management and My Profile from filtering
    
    # Add User Management for admins only
    if user.get('role') == 'admin':
        available_pages.append("User Management")
    
    # Add My Profile for all users
    available_pages.append("My Profile")
    
    # Sidebar navigation
    st.sidebar.title("🧭 Navigation")
    
    if available_pages:
        page = st.sidebar.selectbox(
            "Choose a section",
            available_pages
        )
    else:
        st.error("❌ No pages available for your role.")
        return
    
    # Show user info in sidebar
    show_user_info()
    
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
        conn.close()
    else:
        st.sidebar.error("❌ Not Connected")
    
    # Add environment info if available
    try:
        env_info = os.getenv('ENVIRONMENT', 'Development')
        st.sidebar.text(f"Environment: {env_info}")
    except:
        pass
    
    # Route to appropriate page with permission check
    try:
        if page == "Dashboard" and check_permission("Dashboard"):
            dashboard()
        elif page == "Database Setup" and check_permission("Database Setup"):
            admin_database_setup()
        elif page == "System Codes" and check_permission("System Codes"):
            admin_system_codes()
        elif page == "Pipeline Management" and check_permission("Pipeline Management"):
            admin_pipelines()
        elif page == "Visualizations" and check_permission("Visualizations"):
            visualizations_page()
        elif page == "User Management":
            user_management_page()
        elif page == "Alert Management" and check_permission("Alert Management"):
            alert_management_page()
        elif page == "My Profile":
            from rds_auth import show_profile_page
            show_profile_page()
        else:
            show_access_denied(page)
    except Exception as e:
        st.error(f"❌ An error occurred while loading the {page} page: {str(e)}")
        st.info("Please contact your administrator if this issue persists.")

if __name__ == "__main__":
    main()