# rds_auth.py
"""
RDS-backed Authentication Module for Pipeline Management System
"""
import streamlit as st
import bcrypt
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
from database_utils import execute_query, init_connection

# Role permissions
ROLE_PERMISSIONS = {
    "admin": ["Dashboard", "Database Setup", "System Codes", "Pipeline Management","Alert Management"],
    "manager": ["Dashboard", "Pipeline Management", "Visualizations"],
    "viewer": ["Dashboard", "Visualizations"],
    "developer": ["Dashboard", "System Codes", "Pipeline Management", "Visualizations","Alert Management"]
}

class RDSAuthManager:
    """RDS-based authentication manager"""
    
    def __init__(self):
        self.init_auth_tables()
        self.create_default_admin()
    
    def init_auth_tables(self):
        """Initialize authentication tables in RDS"""
        
        try:
            conn = init_connection()
            if not conn:
                st.error("Failed to connect to database for auth table initialization")
                return
            
            cursor = conn.cursor()
            
            # Create auth schema if it doesn't exist
            cursor.execute("CREATE SCHEMA IF NOT EXISTS auth;")
            
            # Create users table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth.users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'manager', 'developer', 'viewer')),
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                failed_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP,
                created_by VARCHAR(50),
                modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_by VARCHAR(50)
            );
            """)
            
            # Create login sessions table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth.login_sessions (
                session_id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                session_token VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                is_active BOOLEAN DEFAULT TRUE
            );
            """)
            
            # Create audit log table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth.user_audit_log (
                audit_id SERIAL PRIMARY KEY,
                username VARCHAR(50),
                action VARCHAR(50) NOT NULL,
                details TEXT,
                ip_address VARCHAR(45),
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN
            );
            """)
            
            # Create indexes for better performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_users_username ON auth.users(username);",
                "CREATE INDEX IF NOT EXISTS idx_users_active ON auth.users(is_active);",
                "CREATE INDEX IF NOT EXISTS idx_sessions_token ON auth.login_sessions(session_token);",
                "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON auth.login_sessions(expires_at);",
                "CREATE INDEX IF NOT EXISTS idx_audit_username ON auth.user_audit_log(username);",
                "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON auth.user_audit_log(timestamp);"
            ]
            
            for index_query in indexes:
                cursor.execute(index_query)
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            st.error(f"Failed to create auth tables: {e}")
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
            return
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception:
            return False
    
    def log_audit_event(self, username: str, action: str, details: str = None, success: bool = True):
        """Log audit events"""
        try:
            audit_query = """
            INSERT INTO auth.user_audit_log (username, action, details, success)
            VALUES (%s, %s, %s, %s);
            """
            execute_query(audit_query, params=(username, action, details, success), fetch=False)
        except Exception as e:
            print(f"Failed to log audit event: {str(e)}")
    
    def create_default_admin(self):
        """Create default admin user if it doesn't exist"""
        try:
            # Check if admin user exists
            check_admin_query = "SELECT COUNT(*) as count FROM auth.users WHERE username = %s;"
            result = execute_query(check_admin_query, params=('admin',))
            
            if not result.empty and result.iloc[0]['count'] == 0:
                password_hash = self.hash_password('admin123')
                create_admin_query = """
                INSERT INTO auth.users (username, password_hash, role, full_name, email, created_by)
                VALUES (%s, %s, %s, %s, %s, %s);
                """
                execute_query(create_admin_query, params=(
                    'admin', password_hash, 'admin', 'System Administrator', 
                    'admin@company.com', 'system'
                ), fetch=False)
                self.log_audit_event('system', 'CREATE_DEFAULT_ADMIN', 'Default admin user created')
        except Exception as e:
            print(f"Failed to create default admin: {str(e)}")
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user info"""
        try:
            # Get user data
            user_query = """
            SELECT password_hash, role, full_name, email, is_active, failed_attempts, 
                   locked_until, last_login
            FROM auth.users 
            WHERE username = %s;
            """
            user_df = execute_query(user_query, params=(username,))
            
            if user_df.empty:
                self.log_audit_event(username, 'LOGIN_FAILED', 'User not found', False)
                return None
            
            user_data = user_df.iloc[0]
            
            # Check if account is active
            if not user_data['is_active']:
                self.log_audit_event(username, 'LOGIN_FAILED', 'Account inactive', False)
                return None
            
            # Check if account is locked
            if (user_data['locked_until'] and 
                pd.to_datetime(user_data['locked_until']) > datetime.now()):
                self.log_audit_event(username, 'LOGIN_FAILED', 'Account locked', False)
                return None
            
            # Verify password
            if self.verify_password(password, user_data['password_hash']):
                # Reset failed attempts and update last login
                update_login_query = """
                UPDATE auth.users 
                SET failed_attempts = 0, locked_until = NULL, last_login = CURRENT_TIMESTAMP,
                    modified_at = CURRENT_TIMESTAMP, modified_by = %s
                WHERE username = %s;
                """
                execute_query(update_login_query, params=(username, username), fetch=False)
                
                self.log_audit_event(username, 'LOGIN_SUCCESS', 'Successful login', True)
                
                return {
                    "username": username,
                    "role": user_data['role'],
                    "name": user_data['full_name'],
                    "email": user_data['email'],
                    "permissions": ROLE_PERMISSIONS.get(user_data['role'], []),
                    "last_login": user_data['last_login']
                }
            else:
                # Increment failed attempts
                new_failed_attempts = (user_data['failed_attempts'] or 0) + 1
                locked_until = None
                
                # Lock account after 5 failed attempts for 30 minutes
                if new_failed_attempts >= 5:
                    locked_until = datetime.now() + timedelta(minutes=30)
                
                update_failed_query = """
                UPDATE auth.users 
                SET failed_attempts = %s, locked_until = %s, modified_at = CURRENT_TIMESTAMP
                WHERE username = %s;
                """
                execute_query(update_failed_query, params=(new_failed_attempts, locked_until, username), fetch=False)
                
                self.log_audit_event(username, 'LOGIN_FAILED', f'Invalid password, attempt {new_failed_attempts}', False)
                return None
                
        except Exception as e:
            st.error(f"Authentication error: {str(e)}")
            self.log_audit_event(username, 'LOGIN_ERROR', str(e), False)
            return None
    
    def create_user(self, username: str, password: str, role: str, full_name: str, 
                   email: str = None, created_by: str = None) -> bool:
        """Create a new user"""
        try:
            # Check if username already exists
            check_user_query = "SELECT COUNT(*) as count FROM auth.users WHERE username = %s;"
            result = execute_query(check_user_query, params=(username,))
            
            if not result.empty and result.iloc[0]['count'] > 0:
                return False  # Username already exists
            
            password_hash = self.hash_password(password)
            create_user_query = """
            INSERT INTO auth.users (username, password_hash, role, full_name, email, created_by)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            execute_query(create_user_query, params=(
                username, password_hash, role, full_name, email, created_by
            ), fetch=False)
            
            self.log_audit_event(created_by or 'system', 'CREATE_USER', f'Created user: {username}', True)
            return True
            
        except Exception as e:
            st.error(f"Failed to create user: {str(e)}")
            self.log_audit_event(created_by or 'system', 'CREATE_USER_FAILED', f'Failed to create user {username}: {str(e)}', False)
            return False

    def get_all_users(self) -> pd.DataFrame:
        """Get all users (admin only)"""
        try:
            users_query = """
            SELECT username, role, full_name, email, created_at, last_login, 
                   is_active, failed_attempts, locked_until, created_by
            FROM auth.users
            ORDER BY created_at DESC;
            """
            return execute_query(users_query)
        except Exception as e:
            st.error(f"Failed to get users: {str(e)}")
            return pd.DataFrame()
    
    def update_user_status(self, username: str, is_active: bool, modified_by: str) -> bool:
        """Update user active status"""
        try:
            update_query = """
            UPDATE auth.users 
            SET is_active = %s, modified_at = CURRENT_TIMESTAMP, modified_by = %s
            WHERE username = %s;
            """
            execute_query(update_query, params=(is_active, modified_by, username), fetch=False)
            
            action = 'ACTIVATE_USER' if is_active else 'DEACTIVATE_USER'
            self.log_audit_event(modified_by, action, f'Updated status for user: {username}', True)
            return True
            
        except Exception as e:
            st.error(f"Failed to update user status: {str(e)}")
            return False
    
    def reset_user_password(self, username: str, new_password: str, modified_by: str) -> bool:
        """Reset user password (admin only)"""
        try:
            password_hash = self.hash_password(new_password)
            reset_query = """
            UPDATE auth.users 
            SET password_hash = %s, failed_attempts = 0, locked_until = NULL,
                modified_at = CURRENT_TIMESTAMP, modified_by = %s
            WHERE username = %s;
            """
            execute_query(reset_query, params=(password_hash, modified_by, username), fetch=False)
            
            self.log_audit_event(modified_by, 'RESET_PASSWORD', f'Reset password for user: {username}', True)
            return True
            
        except Exception as e:
            st.error(f"Failed to reset password: {str(e)}")
            return False
    
    def change_user_password(self, username: str, current_password: str, new_password: str) -> bool:
        """Change user's own password"""
        try:
            # First verify current password
            user_query = "SELECT password_hash FROM auth.users WHERE username = %s;"
            user_df = execute_query(user_query, params=(username,))
            
            if user_df.empty:
                return False
            
            current_hash = user_df.iloc[0]['password_hash']
            if not self.verify_password(current_password, current_hash):
                return False
            
            # Update with new password
            new_hash = self.hash_password(new_password)
            update_query = """
            UPDATE auth.users 
            SET password_hash = %s, modified_at = CURRENT_TIMESTAMP, modified_by = %s
            WHERE username = %s;
            """
            execute_query(update_query, params=(new_hash, username, username), fetch=False)
            
            self.log_audit_event(username, 'CHANGE_PASSWORD', 'User changed own password', True)
            return True
            
        except Exception as e:
            st.error(f"Failed to change password: {str(e)}")
            return False
    
    def bulk_create_users_from_csv(self, csv_data, default_role: str = 'viewer', created_by: str = None) -> Dict:
        """Bulk create users from CSV data"""
        results = {
            'successful': [],
            'failed': [],
            'errors': []
        }
        
        try:
            import pandas as pd
            from io import StringIO
            
            # Parse CSV data
            if isinstance(csv_data, str):
                df = pd.read_csv(StringIO(csv_data))
            else:
                df = pd.read_csv(csv_data)
            
            # Clean column names (remove whitespace)
            df.columns = df.columns.str.strip()
            
            # Required columns
            required_cols = ['username', 'full_name']
            optional_cols = ['email', 'role']
            
            # Check for required columns
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                results['errors'].append(f"Missing required columns: {', '.join(missing_cols)}")
                return results
            
            # Process each row
            for index, row in df.iterrows():
                try:
                    username = str(row['username']).strip()
                    full_name = str(row['full_name']).strip()
                    email = str(row.get('email', '')).strip() if pd.notna(row.get('email')) else None
                    role = str(row.get('role', default_role)).strip().lower()
                    
                    # Validate role
                    if role not in ROLE_PERMISSIONS:
                        role = default_role
                    
                    # Skip empty usernames
                    if not username or username.lower() == 'nan':
                        results['failed'].append(f"Row {index + 1}: Empty username")
                        continue
                    
                    # Skip empty full names
                    if not full_name or full_name.lower() == 'nan':
                        results['failed'].append(f"Row {index + 1}: Empty full name for {username}")
                        continue
                    
                    # Use simple default password for all bulk created users
                    temp_password = "password"
                    
                    # Create user
                    if self.create_user(username, temp_password, role, full_name, email, created_by):
                        results['successful'].append({
                            'username': username,
                            'full_name': full_name,
                            'email': email,
                            'role': role,
                            'temp_password': temp_password
                        })
                    else:
                        results['failed'].append(f"Row {index + 1}: Failed to create user {username} (may already exist)")
                        
                except Exception as e:
                    results['failed'].append(f"Row {index + 1}: Error - {str(e)}")
            
            self.log_audit_event(
                created_by or 'system', 
                'BULK_CREATE_USERS', 
                f"Created {len(results['successful'])} users, {len(results['failed'])} failed", 
                True
            )
            
        except Exception as e:
            results['errors'].append(f"CSV processing error: {str(e)}")
            
        return results
    
    def update_user_role(self, username: str, new_role: str, modified_by: str) -> bool:
        """Update user role"""
        try:
            # Validate role
            if new_role not in ROLE_PERMISSIONS:
                st.error(f"Invalid role: {new_role}")
                return False
            
            # Prevent changing admin user role
            if username == 'admin' and new_role != 'admin':
                st.error("Cannot change the system administrator's role.")
                return False
            
            update_query = """
            UPDATE auth.users 
            SET role = %s, modified_at = CURRENT_TIMESTAMP, modified_by = %s
            WHERE username = %s;
            """
            execute_query(update_query, params=(new_role, modified_by, username), fetch=False)
            
            self.log_audit_event(modified_by, 'UPDATE_USER_ROLE', f'Changed role for {username} to {new_role}', True)
            return True
            
        except Exception as e:
            st.error(f"Failed to update user role: {str(e)}")
            return False

    def delete_user(self, username: str, deleted_by: str) -> bool:
        """Permanently delete a user (admin only)"""
        try:
            # Prevent deletion of admin user
            if username == 'admin':
                st.error("Cannot delete the system administrator account.")
                return False
            
            # Check if user exists
            check_user_query = "SELECT COUNT(*) as count FROM auth.users WHERE username = %s;"
            result = execute_query(check_user_query, params=(username,))
            
            if result.empty or result.iloc[0]['count'] == 0:
                st.error("User not found.")
                return False
            
            # Delete user from database
            delete_query = "DELETE FROM auth.users WHERE username = %s;"
            execute_query(delete_query, params=(username,), fetch=False)
            
            self.log_audit_event(deleted_by, 'DELETE_USER', f'Deleted user: {username}', True)
            return True
            
        except Exception as e:
            st.error(f"Failed to delete user: {str(e)}")
            self.log_audit_event(deleted_by, 'DELETE_USER_FAILED', f'Failed to delete user {username}: {str(e)}', False)
            return False

    def get_audit_log(self, username: str = None, limit: int = 100) -> pd.DataFrame:
        """Get audit log entries"""
        try:
            if username:
                audit_query = """
                SELECT username, action, details, ip_address, timestamp, success
                FROM auth.user_audit_log
                WHERE username = %s
                ORDER BY timestamp DESC
                LIMIT %s;
                """
                return execute_query(audit_query, params=(username, limit))
            else:
                audit_query = """
                SELECT username, action, details, ip_address, timestamp, success
                FROM auth.user_audit_log
                ORDER BY timestamp DESC
                LIMIT %s;
                """
                return execute_query(audit_query, params=(limit,))
                
        except Exception as e:
            st.error(f"Failed to get audit log: {str(e)}")
            return pd.DataFrame()

# Initialize the auth manager
auth_manager = RDSAuthManager()

def require_auth():
    """Require authentication for the application"""
    if "user" not in st.session_state:
        st.session_state.user = None
    
    if st.session_state.user is None:
        show_login_page()
        return False
    return True

def show_login_page():
    """Display login page"""
    st.title("🔐 Pipeline Management System")
    st.markdown("**Secure Access Required**")
    
    # Test database connection
    conn = init_connection()
    if not conn:
        st.error("❌ Database connection failed. Please check your database configuration.")
        st.stop()
    else:
        conn.close()
    
    # Login form
    with st.form("login_form"):
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("🔓 Login")
        
        if submit_button and username and password:
            user = auth_manager.authenticate_user(username, password)
            if user:
                st.session_state.user = user
                st.success(f"Welcome back, {user['name']}!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials or account locked")
    
    # Demo credentials
    st.markdown("---")
    with st.expander("🔧 Demo Credentials"):
        st.markdown("""
        **Default Admin Account:** 
        - Username: `admin`
        - Password: `admin123`
        
        Use the admin account to create additional users with appropriate roles.
        """)

def show_password_change_form():
    """Show password change form for current user"""
    st.subheader("🔒 Change Your Password")
    
    # Back button
    if st.button("← Back to Dashboard"):
        st.session_state.show_password_change = False
        st.rerun()
    
    if "user" not in st.session_state or not st.session_state.user:
        st.error("❌ You must be logged in to change your password.")
        return
    
    user = st.session_state.user
    st.info(f"Changing password for: **{user['name']}** (@{user['username']})")
    
    with st.form("change_password_form"):
        st.write("**Enter Password Details**")
        current_password = st.text_input("Current Password*", type="password")
        new_password = st.text_input("New Password*", type="password")
        confirm_password = st.text_input("Confirm New Password*", type="password")
        
        # Password requirements
        st.markdown("""
        **Password Requirements:**
        - Minimum 8 characters
        - At least one uppercase letter
        - At least one lowercase letter  
        - At least one number
        """)
        
        if st.form_submit_button("🔄 Change Password"):
            # Validation
            if not current_password or not new_password or not confirm_password:
                st.error("❌ All fields are required.")
                return
            
            if new_password != confirm_password:
                st.error("❌ New passwords don't match.")
                return
            
            if len(new_password) < 8:
                st.error("❌ New password must be at least 8 characters long.")
                return
            
            # Check password complexity
            import re
            if not (re.search(r'[A-Z]', new_password) and 
                   re.search(r'[a-z]', new_password) and 
                   re.search(r'\d', new_password)):
                st.error("❌ Password must contain uppercase, lowercase, and numbers.")
                return
            
            if new_password == current_password:
                st.error("❌ New password must be different from current password.")
                return
            
            # Attempt password change
            if auth_manager.change_user_password(user['username'], current_password, new_password):
                st.success("✅ Password changed successfully!")
                st.info("Please log in again with your new password.")
                
                # Clear session to force re-login
                st.session_state.user = None
                st.session_state.show_password_change = False
                st.rerun()
            else:
                st.error("❌ Failed to change password. Please check your current password.")

def show_profile_page():
    """Show user profile page"""
    if "user" not in st.session_state or not st.session_state.user:
        return
    
    user = st.session_state.user
    st.subheader("👤 My Profile")
    
    # Display user info
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Account Information**")
        st.text(f"Username: {user['username']}")
        st.text(f"Full Name: {user['name']}")
        st.text(f"Email: {user.get('email', 'N/A')}")
        st.text(f"Role: {user['role'].title()}")
        
    with col2:
        st.write("**Account Activity**")
        if user.get('last_login'):
            st.text(f"Last Login: {user['last_login']}")
        
        # Show user's permissions
        st.write("**Your Permissions:**")
        permissions = user.get('permissions', [])
        for perm in permissions:
            st.text(f"• {perm}")
    
    # Password change section
    st.markdown("---")
    st.write("**Security**")
    if st.button("🔒 Change Password"):
        st.session_state.show_password_change = True
        st.rerun()
    
    # Show recent activity for this user
    st.markdown("---")
    st.write("**Recent Activity**")
    user_audit = auth_manager.get_audit_log(username=user['username'], limit=10)
    
    if not user_audit.empty:
        # Format the audit log for better display
        display_audit = user_audit[['action', 'timestamp', 'success']].copy()
        display_audit['status'] = display_audit['success'].map({True: '✅ Success', False: '❌ Failed'})
        display_audit = display_audit[['action', 'timestamp', 'status']]
        
        st.dataframe(display_audit, width="stretch", hide_index=True)
    else:
        st.info("No recent activity found.")

def check_permission(page: str) -> bool:
    """Check if current user has permission to access a page"""
    if "user" not in st.session_state or not st.session_state.user:
        return False
    
    user_permissions = st.session_state.user.get("permissions", [])
    return page in user_permissions

def show_user_info():
    """Display current user info in sidebar"""
    if "user" in st.session_state and st.session_state.user:
        user = st.session_state.user
        st.sidebar.markdown("---")
        st.sidebar.subheader("👤 Current User")
        st.sidebar.text(f"Name: {user['name']}")
        st.sidebar.text(f"Role: {user['role'].title()}")
        st.sidebar.text(f"Username: {user['username']}")
        
        if st.sidebar.button("🚪 Logout"):
            auth_manager.log_audit_event(user['username'], 'LOGOUT', 'User logged out', True)
            st.session_state.user = None
            st.rerun()

def filter_navigation_options(all_pages: List[str]) -> List[str]:
    """Filter navigation options based on user permissions"""
    if "user" not in st.session_state or st.session_state.user is None:
        return []
    
    user_permissions = st.session_state.user.get("permissions", [])
    return [page for page in all_pages if page in user_permissions]

def show_access_denied(page: str):
    """Show access denied message"""
    st.error(f"🚫 Access Denied")
    st.markdown(f"You don't have permission to access the **{page}** section.")
    st.markdown(f"Your current role: **{st.session_state.user['role'].title()}**")
    st.markdown("Contact an administrator if you need access to this section.")