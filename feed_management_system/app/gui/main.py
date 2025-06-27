"""
Main Streamlit Application Entry Point
"""
import streamlit as st
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Configure Streamlit page
st.set_page_config(
    page_title="Feed Management System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    st.title("📊 Feed Management System")
    st.markdown("---")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Dashboard", "Feeds", "Feed Runs", "System Codes", "Admin"]
    )
    
    # Main content area
    if page == "Dashboard":
        st.header("Dashboard")
        st.info("Welcome to the Feed Management System!")
        
        # Sample metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Feeds", "12", "2")
        with col2:
            st.metric("Active Runs", "3", "-1")
        with col3:
            st.metric("Success Rate", "94.5%", "1.2%")
        with col4:
            st.metric("Avg Runtime", "2.3m", "-0.1m")
    
    elif page == "Feeds":
        st.header("Feed Configuration")
        st.info("Feed management interface coming soon...")
    
    elif page == "Feed Runs":
        st.header("Feed Run History")
        st.info("Feed run monitoring interface coming soon...")
    
    elif page == "System Codes":
        st.header("System Codes Management")
        st.info("System codes administration interface coming soon...")
    
    elif page == "Admin":
        st.header("System Administration")
        st.info("Admin panel coming soon...")

if __name__ == "__main__":
    main()
