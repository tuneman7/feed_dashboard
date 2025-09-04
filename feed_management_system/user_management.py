# user_management.py
"""
User Management Module for Pipeline Management System
"""
import streamlit as st
import secrets
import pandas as pd
from rds_auth import auth_manager, ROLE_PERMISSIONS

def user_management_page():
    """Main user management page (admin only)"""
    
    # Check if user is admin
    if not st.session_state.get("user") or st.session_state.user.get("role") != "admin":
        st.error("Access Denied: Admin privileges required")
        return
    
    st.header("User Management")
    st.caption("Manage system users, roles, and permissions")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Create User", "Bulk Create", "Manage Users", "Audit Log"])
    
    with tab1:
        create_user_tab()
    
    with tab2:
        bulk_create_users_tab()
    
    with tab3:
        manage_users_tab()
    
    with tab4:
        audit_log_tab()

def create_user_tab():
    """Create new user tab"""
    st.subheader("Create New User")
    
    with st.form("create_user_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_username = st.text_input("Username*", help="Unique username for the user")
            new_password = st.text_input("Password*", type="password", help="Temporary password for the user")
            new_role = st.selectbox("Role*", list(ROLE_PERMISSIONS.keys()), help="User role determines access permissions")
        
        with col2:
            new_full_name = st.text_input("Full Name*", help="User's full display name")
            new_email = st.text_input("Email", help="Optional email address")
        
        # Show role permissions
        if new_role:
            st.write("**Permissions for selected role:**")
            permissions = ROLE_PERMISSIONS.get(new_role, [])
            for perm in permissions:
                st.text(f"• {perm}")
        
        create_button = st.form_submit_button("Create User", type="primary")
        
        if create_button:
            if new_username and new_password and new_full_name:
                created_by = st.session_state.user['username']
                if auth_manager.create_user(new_username, new_password, new_role, 
                                         new_full_name, new_email, created_by):
                    st.success(f"User '{new_username}' created successfully!")
                    st.info(f"**Temporary password:** `{new_password}`")
                    st.warning("Please share the password securely with the user and ask them to change it on first login.")
                    st.rerun()
                else:
                    st.error("Failed to create user. Username may already exist.")
            else:
                st.error("Please fill in all required fields marked with *")

def bulk_create_users_tab():
    """Bulk create users from CSV tab"""
    st.subheader("Bulk Create Users from CSV")
    
    # CSV template download
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        **CSV Format Requirements:**
        - Required columns: `username`, `full_name`  
        - Optional columns: `email`, `role`
        - If role is not specified, users will be created with the default role selected below
        - All users will be created with password: **"password"**
        """)
    
    with col2:
        # Generate sample CSV for download
        sample_csv = """username,full_name,email,role
john.doe,John Doe,john.doe@company.com,developer
jane.smith,Jane Smith,jane.smith@company.com,manager
bob.wilson,Bob Wilson,bob.wilson@company.com,viewer"""
        
        st.download_button(
            label="Download CSV Template",
            data=sample_csv,
            file_name="user_template.csv",
            mime="text/csv"
        )
    
    st.markdown("---")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload CSV File", 
        type=['csv'],
        help="Upload a CSV file with user information"
    )
    
    # Default role selection
    default_role = st.selectbox(
        "Default Role (for users without role specified)",
        list(ROLE_PERMISSIONS.keys()),
        index=list(ROLE_PERMISSIONS.keys()).index('viewer')
    )
    
    if uploaded_file is not None:
        try:
            # Preview uploaded data
            df = pd.read_csv(uploaded_file)
            df.columns = df.columns.str.strip()  # Clean column names
            
            st.write("**Preview of uploaded data:**")
            st.dataframe(df.head(), use_container_width=True)
            
            st.write(f"**Total rows to process:** {len(df)}")
            
            # Validate columns
            required_cols = ['username', 'full_name']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.error(f"Missing required columns: {', '.join(missing_cols)}")
                st.info("Required columns: username, full_name")
                st.info("Optional columns: email, role")
            else:
                st.success("CSV format is valid!")
                
                # Process button
                if st.button("Create Users", type="primary"):
                    with st.spinner("Creating users..."):
                        # Reset file pointer
                        uploaded_file.seek(0)
                        
                        # Bulk create users
                        results = auth_manager.bulk_create_users_from_csv(
                            uploaded_file, 
                            default_role=default_role,
                            created_by=st.session_state.user['username']
                        )
                        
                        # Display results
                        if results['errors']:
                            st.error("Processing Errors:")
                            for error in results['errors']:
                                st.error(error)
                        
                        if results['successful']:
                            st.success(f"Successfully created {len(results['successful'])} users!")
                            
                            # Show created users
                            st.subheader("Created Users")
                            success_df = pd.DataFrame(results['successful'])
                            
                            # Remove temp_password column since it's always "password"
                            if 'temp_password' in success_df.columns:
                                success_df = success_df.drop('temp_password', axis=1)
                            
                            st.dataframe(success_df, use_container_width=True)
                            
                            st.info("All users created with password: **password**")
                            st.warning("Users should change their passwords on first login!")
                        
                        if results['failed']:
                            st.warning(f"{len(results['failed'])} users failed to create:")
                            for failure in results['failed']:
                                st.warning(failure)
                        
                        # Refresh to show new users
                        if results['successful']:
                            st.info("Users created successfully! Switch to 'Manage Users' tab to see all users.")
                            
        except Exception as e:
            st.error(f"Error processing CSV: {str(e)}")
    
    # Instructions
    st.markdown("---")
    with st.expander("Instructions"):
        st.markdown("""
        **How to bulk create users:**
        
        1. **Download the CSV template** using the button above
        2. **Fill in user information** in the CSV file:
           - `username` (required): Unique username for each user
           - `full_name` (required): User's full display name  
           - `email` (optional): User's email address
           - `role` (optional): User role (admin, manager, developer, viewer)
        3. **Upload the completed CSV** using the file uploader
        4. **Review the preview** to ensure data looks correct
        5. **Click 'Create Users'** to bulk create all users
        6. **All users will have password "password"** - tell them to change it on first login
        
        **Notes:**
        - Users without a specified role will get the default role selected above
        - All users are created with the same password: "password"
        - Users should change their passwords on first login
        - Duplicate usernames will be skipped with an error message
        """)

def manage_users_tab():
    """Manage existing users tab"""
    st.subheader("Manage Existing Users")
    
    users_df = auth_manager.get_all_users()
    
    if users_df.empty:
        st.info("No users found in the system.")
        return
    
    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Users", len(users_df))
    with col2:
        active_users = len(users_df[users_df['is_active'] == True])
        st.metric("Active Users", active_users)
    with col3:
        admin_users = len(users_df[users_df['role'] == 'admin'])
        st.metric("Admin Users", admin_users)
    with col4:
        recent_logins = len(users_df[users_df['last_login'].notna()])
        st.metric("Users with Login History", recent_logins)
    
    st.markdown("---")
    
    # Deletion confirmation state
    if 'confirm_delete_user' not in st.session_state:
        st.session_state.confirm_delete_user = None
    
    # User list with actions
    for _, user in users_df.iterrows():
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2.5, 1, 1.5, 2, 1.5])
            
            with col1:
                # User info
                status_icon = "✅" if user['is_active'] else "❌"
                role_color = {
                    'admin': '🔴',
                    'manager': '🟠', 
                    'developer': '🟡',
                    'viewer': '🟢'
                }.get(user['role'], '⚪')
                
                st.markdown(f"**{status_icon} {user['full_name']}** (@{user['username']}) {role_color}")
                st.caption(f"Role: {user['role'].title()} | Email: {user['email'] or 'N/A'}")
                
                if user['last_login']:
                    st.caption(f"Last login: {user['last_login']}")
                else:
                    st.caption("Never logged in")
                
                if user['failed_attempts'] and user['failed_attempts'] > 0:
                    st.caption(f"Failed login attempts: {user['failed_attempts']}")
            
            with col2:
                # Role assignment
                if user['username'] != 'admin':
                    current_role = user['role']
                    new_role = st.selectbox(
                        "Role",
                        options=list(ROLE_PERMISSIONS.keys()),
                        index=list(ROLE_PERMISSIONS.keys()).index(current_role),
                        key=f"role_{user['username']}"
                    )
                    
                    if new_role != current_role:
                        if st.button("Update Role", key=f"update_role_{user['username']}", type="primary"):
                            if auth_manager.update_user_role(user['username'], new_role, 
                                                           st.session_state.user['username']):
                                st.success(f"Role updated to {new_role}!")
                                st.rerun()
                            else:
                                st.error("Failed to update role.")
                else:
                    st.write("**admin**")
                    st.caption("(protected)")
            
            with col3:
                # Status toggle (don't allow disabling admin)
                if user['username'] != 'admin':
                    button_text = "Deactivate" if user['is_active'] else "Activate"
                    button_type = "secondary" if user['is_active'] else "primary"
                    
                    if st.button(button_text, key=f"toggle_{user['username']}", type=button_type):
                        new_status = not user['is_active']
                        if auth_manager.update_user_status(user['username'], new_status, 
                                                         st.session_state.user['username']):
                            status_word = "activated" if new_status else "deactivated"
                            st.success(f"User {status_word}!")
                            st.rerun()
                else:
                    st.caption("System admin")
                    st.caption("(active)")
            
            with col4:
                # Password reset - fixed to use only existing methods
                if st.button("Reset Password", key=f"reset_{user['username']}", type="secondary"):
                    # Generate a secure temporary password
                    temp_password = generate_temp_password()
                    if auth_manager.reset_user_password(user['username'], temp_password, 
                                                     st.session_state.user['username']):
                        st.success("Password reset successfully!")
                        st.code(f"New password: {temp_password}")
                        st.warning("Share this password securely with the user.")
                        st.info("User should change this password on their next login.")
                    else:
                        st.error("Failed to reset password.")
            
            with col5:
                # Delete user functionality
                if user['username'] != 'admin':
                    # Check if we're confirming deletion for this user
                    if st.session_state.confirm_delete_user == user['username']:
                        st.warning("⚠️ Confirm deletion?")
                        col5a, col5b = st.columns(2)
                        
                        with col5a:
                            if st.button("Yes", key=f"confirm_delete_{user['username']}", type="primary"):
                                if auth_manager.delete_user(user['username'], st.session_state.user['username']):
                                    st.success(f"User '{user['username']}' deleted!")
                                    st.session_state.confirm_delete_user = None
                                    st.rerun()
                                else:
                                    st.error("Failed to delete user.")
                        
                        with col5b:
                            if st.button("No", key=f"cancel_delete_{user['username']}", type="secondary"):
                                st.session_state.confirm_delete_user = None
                                st.rerun()
                    else:
                        if st.button("🗑️ Delete", key=f"delete_{user['username']}", type="secondary", 
                                   help="Permanently delete this user"):
                            st.session_state.confirm_delete_user = user['username']
                            st.rerun()
                else:
                    st.caption("System admin")
                    st.caption("(cannot delete)")
            
            st.markdown("---")

def generate_temp_password():
    """Generate a secure temporary password"""
    # Generate a password with mix of characters for better security
    import string
    import random
    
    # Ensure password has uppercase, lowercase, digits, and special chars
    password = [
        random.choice(string.ascii_uppercase),  # At least one uppercase
        random.choice(string.ascii_lowercase),  # At least one lowercase  
        random.choice(string.digits),           # At least one digit
        random.choice('!@#$%^&*')              # At least one special char
    ]
    
    # Fill remaining length with random characters
    all_chars = string.ascii_letters + string.digits + '!@#$%^&*'
    for _ in range(8):  # Total length will be 12
        password.append(random.choice(all_chars))
    
    # Shuffle to randomize positions
    random.shuffle(password)
    
    return ''.join(password)

def audit_log_tab():
    """Audit log tab"""
    st.subheader("System Audit Log")
    
    col1, col2 = st.columns(2)
    with col1:
        # Filter options
        users_df = auth_manager.get_all_users()
        user_options = ['All Users'] + users_df['username'].tolist()
        selected_user = st.selectbox("Filter by User:", user_options)
    
    with col2:
        # Limit options
        limit_options = [25, 50, 100, 200]
        selected_limit = st.selectbox("Number of Records:", limit_options, index=1)
    
    # Get audit data
    username_filter = None if selected_user == 'All Users' else selected_user
    audit_df = auth_manager.get_audit_log(username=username_filter, limit=selected_limit)
    
    if not audit_df.empty:
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            total_events = len(audit_df)
            st.metric("Total Events", total_events)
        with col2:
            successful_events = len(audit_df[audit_df['success'] == True])
            st.metric("Successful Events", successful_events)
        with col3:
            failed_events = len(audit_df[audit_df['success'] == False])
            st.metric("Failed Events", failed_events)
        
        st.markdown("---")
        
        # Format and display audit log
        display_df = audit_df.copy()
        display_df['status'] = display_df['success'].map({
            True: '✅ Success', 
            False: '❌ Failed',
            None: '⚪ Unknown'
        })
        
        # Reorder columns for better display
        column_order = ['timestamp', 'username', 'action', 'status', 'details']
        display_df = display_df[column_order]
        
        st.dataframe(
            display_df, 
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp": st.column_config.DatetimeColumn(
                    "Timestamp",
                    format="MMM DD, YYYY HH:mm:ss"
                ),
                "username": "User",
                "action": "Action",
                "status": "Status", 
                "details": "Details"
            }
        )
    else:
        st.info("No audit events found for the selected criteria.")
    
    # Export option
    if not audit_df.empty:
        csv = audit_df.to_csv(index=False)
        st.download_button(
            label="Download Audit Log (CSV)",
            data=csv,
            file_name=f"audit_log_{username_filter or 'all_users'}_{selected_limit}_records.csv",
            mime="text/csv"
        )