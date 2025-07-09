# streamlit_app.py
"""
Pipeline Management System - Streamlit Admin Interface
"""
import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import glob
# Force cache clear at startup
import uuid
os.environ["CACHE_BUSTER"] = str(uuid.uuid4())


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

create_db_if_missing()

# Configure Streamlit page
st.set_page_config(
    page_title="Pipeline Management Admin",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

def clear_database():
    """Clear all user-defined objects by running sql/clear_database/*.sql in order"""
    clear_path = os.path.join("sql", "clear_database", "*.sql")
    clear_files = sorted(glob.glob(clear_path))

    for file_path in clear_files:
        try:
            with open(file_path, "r") as f:
                sql_block = f.read()
                if sql_block.strip():
                    #st.code(sql_blofck, language="sql")  # Optional: display executed SQL
                    execute_query(sql_block, fetch=False)
        except Exception as e:
            st.error(f"Failed to process {file_path}: {e}")



def create_database_schema():
    """Execute all .sql files in sql/ddl/ directory in sorted order"""
    ddl_path = os.path.join("sql", "ddl", "*.sql")
    ddl_files = sorted(glob.glob(ddl_path))

    for file_path in ddl_files:
        try:
            with open(file_path, "r") as f:
                sql_commands = f.read()
                for command in sql_commands.split(';'):
                    if command.strip():
                        execute_query(command + ';', fetch=False)
        except Exception as e:
            st.error(f"Failed to process {file_path}: {e}")

def insert_sample_data():
    """Insert sample data by running all .sql files in sql/dcl/ directory in sorted order"""

    dcl_path = os.path.join("sql", "dcl", "*.sql")
    dcl_files = sorted(glob.glob(dcl_path))

    for file_path in dcl_files:
        try:
            with open(file_path, "r") as f:
                sql_commands = f.read()
                for command in sql_commands.split(';'):
                    if command.strip():
                        execute_query(command + ';', fetch=False)
        except Exception as e:
            st.error(f"Failed to process {file_path}: {e}")

    functions_path = os.path.join("sql", "functions", "*.sql")
    functions_files = sorted(glob.glob(functions_path))

    for file_path in functions_files:
        try:
            with open(file_path, "r") as f:
                command = f.read()
                execute_query(command, fetch=False)
        except Exception as e:
            st.error(f"Failed to process {file_path}: {e}")




def admin_database_setup():
    """Database setup and initialization page"""
    st.header("🔧 Database Administration")

    # Connection status
    conn = init_connection()
    if conn:
        st.success("✅ Database connection successful")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("🏗️ Create Schema"):
                with st.spinner("Creating database schema..."):
                    create_database_schema()
                    st.success("Database schema created successfully!")
                    st.rerun()

        with col2:
            if st.button("📊 Insert Sample Data"):
                with st.spinner("Inserting sample data..."):
                    insert_sample_data()
                    st.success("Sample data inserted successfully!")
                    st.rerun()

        with col3:
            if st.button("🔄 Test Connection"):
                try:
                    test_query = "SELECT version();"
                    result = execute_query(test_query)
                    st.success("Database connection test passed!")
                    st.info(f"PostgreSQL Version: {result.iloc[0, 0] if not result.empty else 'Unknown'}")
                except Exception as e:
                    st.error(f"Connection test failed: {e}")

        with col4:
            if st.button("🧨 Clear Database"):
                try:
                    with st.spinner("Clearing all user-defined objects..."):
                        clear_database()
                    st.success("Database cleared successfully!")
                    st.stop()  # Don't rerun immediately; let user see success
                except Exception as e:
                    st.error(f"❌ Error during clear:\n\n{e}")



        # Database status
        st.subheader("📈 Database Status")

        try:
            table_query = """
            SELECT table_name, 
                   (SELECT count(*) FROM information_schema.columns 
                    WHERE table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
            """
            tables_df = execute_query(table_query)

            if not tables_df.empty:
                st.dataframe(tables_df, use_container_width=True)

                st.subheader("📊 Record Counts")
                counts_data = []
                for table in tables_df['table_name']:
                    try:
                        count_result = execute_query(f"SELECT COUNT(*) as count FROM {table};")
                        count = count_result.iloc[0, 0] if not count_result.empty else 0
                        counts_data.append({"Table": table, "Records": count})
                    except:
                        counts_data.append({"Table": table, "Records": "Error"})

                counts_df = pd.DataFrame(counts_data)
                st.dataframe(counts_df, use_container_width=True)
            else:
                st.warning("No tables found. Please create the database schema first.")

        except Exception as e:
            st.error(f"Error retrieving database status: {e}")
    else:
        st.error("❌ Cannot connect to database")
        st.info("Please check your database configuration in the .env file")




def admin_system_codes():
    """System codes management interface"""
    st.header("🏷️ System Codes Management")
    
    tab1, tab2, tab3, tab4 = st.tabs(["View Codes", "Add Code Type", "Add System Code", "Delete/Edit"])
    
    with tab1:
        st.subheader("Current System Codes")
        
        # Get all system codes with type descriptions
        codes_query = """
        SELECT sc.code_id, sc.common_cd, sc.code_type_cd, 
               ct.code_type_description, sc.code_description, 
               sc.sort_order, sc.is_active, sc.created_at
        FROM admin.system_codes sc
        JOIN admin.code_type ct ON sc.code_type_cd = ct.code_type_cd
        ORDER BY sc.code_type_cd, sc.sort_order, sc.common_cd;
        """
        codes_df = execute_query(codes_query)
        
        if not codes_df.empty:
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                code_types = ['All'] + sorted(codes_df['code_type_cd'].unique().tolist())
                selected_type = st.selectbox("Filter by Code Type", code_types)
            
            with col2:
                active_filter = st.selectbox("Filter by Status", ["All", "Active", "Inactive"])
            
            # Apply filters
            filtered_df = codes_df.copy()
            if selected_type != 'All':
                filtered_df = filtered_df[filtered_df['code_type_cd'] == selected_type]
            if active_filter == 'Active':
                filtered_df = filtered_df[filtered_df['is_active'] == True]
            elif active_filter == 'Inactive':
                filtered_df = filtered_df[filtered_df['is_active'] == False]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Statistics
            st.subheader("📊 Statistics")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Codes", len(codes_df))
            with col2:
                st.metric("Active Codes", len(codes_df[codes_df['is_active'] == True]))
            with col3:
                st.metric("Code Types", codes_df['code_type_cd'].nunique())
        else:
            st.warning("No system codes found. Please insert sample data first.")
    
    with tab2:
        st.subheader("Add New Code Type")
        
        with st.form("add_code_type"):
            code_type_cd = st.text_input("Code Type Code", max_chars=50, 
                                       help="Unique identifier (e.g., 'USER_ROLE')")
            code_type_desc = st.text_input("Description", max_chars=255,
                                         help="Human-readable description")
            
            if st.form_submit_button("Add Code Type"):
                if code_type_cd and code_type_desc:
                    query = """
                    INSERT INTO admin.code_type (code_type_cd, code_type_description)
                    VALUES (%s, %s);
                    """
                    if execute_query(query, (code_type_cd.upper(), code_type_desc), fetch=False):
                        st.success(f"Code type '{code_type_cd}' added successfully!")
                        st.rerun()
                else:
                    st.error("Please fill in all required fields")
    
    with tab3:
        st.subheader("Add New System Code")
        
        # Get available code types
        types_query = "SELECT code_type_cd, code_type_description FROM admin.code_type ORDER BY code_type_cd;"
        types_df = execute_query(types_query)
        
        if not types_df.empty:
            with st.form("add_system_code"):
                code_type = st.selectbox("Code Type", 
                                       options=types_df['code_type_cd'].tolist(),
                                       format_func=lambda x: f"{x} - {types_df[types_df['code_type_cd']==x]['code_type_description'].iloc[0]}")
                
                common_cd = st.text_input("Code", max_chars=50,
                                        help="Unique code within the type (e.g., 'ADMIN')")
                code_desc = st.text_input("Description", max_chars=255,
                                        help="Human-readable description")
                
                col1, col2 = st.columns(2)
                with col1:
                    sort_order = st.number_input("Sort Order", min_value=0, value=0)
                with col2:
                    is_active = st.checkbox("Active", value=True)
                
                if st.form_submit_button("Add System Code"):
                    if common_cd and code_desc:
                        query = """
                        INSERT INTO admin.system_codes (common_cd, code_type_cd, code_description, sort_order, is_active)
                        VALUES (%s, %s, %s, %s, %s);
                        """
                        if execute_query(query, (common_cd.upper(), code_type, code_desc, sort_order, is_active), fetch=False):
                            st.success(f"System code '{common_cd}' added successfully!")
                            st.rerun()
                    else:
                        st.error("Please fill in all required fields")
        else:
            st.warning("No code types available. Please add code types first.")
    
    with tab4:
        st.subheader("🗑️ Delete or Edit System Codes")
        
        # Get all system codes for selection
        all_codes_query = """
        SELECT sc.code_id, sc.common_cd, sc.code_type_cd, 
               sc.code_description, sc.sort_order, sc.is_active
        FROM admin.system_codes sc
        ORDER BY sc.code_type_cd, sc.common_cd;
        """
        all_codes_df = execute_query(all_codes_query)
        
        if not all_codes_df.empty:
            # Create selection options
            code_options = []
            for _, row in all_codes_df.iterrows():
                label = f"{row['code_type_cd']} | {row['common_cd']} - {row['code_description']}"
                code_options.append((label, row['code_id']))
            
            selected_code = st.selectbox(
                "Select System Code to Delete/Edit",
                options=[opt[1] for opt in code_options],
                format_func=lambda x: next(opt[0] for opt in code_options if opt[1] == x)
            )
            
            if selected_code:
                # Get selected code details
                selected_row = all_codes_df[all_codes_df['code_id'] == selected_code].iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("✏️ Edit Code")
                    with st.form("edit_system_code"):
                        new_desc = st.text_input("Description", value=selected_row['code_description'])
                        new_sort = st.number_input("Sort Order", value=int(selected_row['sort_order']))
                        new_active = st.checkbox("Active", value=bool(selected_row['is_active']))
                        
                        if st.form_submit_button("Update Code"):
                            update_query = """
                            UPDATE admin.system_codes 
                            SET code_description = %s, sort_order = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE code_id = %s;
                            """
                            if execute_query(update_query, (new_desc, new_sort, new_active, selected_code), fetch=False):
                                st.success("System code updated successfully!")
                                st.rerun()
                
                with col2:
                    st.subheader("🗑️ Delete Code")
                    st.warning(f"**Selected:** {selected_row['code_type_cd']} | {selected_row['common_cd']}")
                    
                    # Check for dependencies
                    dep_queries = [
                        ("Pipelines", f"SELECT COUNT(*) as count FROM pipeline.pipeline WHERE pipeline_type_cd = '{selected_row['common_cd']}'"),
                        ("Pipeline Runs", f"SELECT COUNT(*) as count FROM pipeline.pipeline_run WHERE status_cd = '{selected_row['common_cd']}'")
                    ]
                    
                    has_dependencies = False
                    for dep_name, dep_query in dep_queries:
                        try:
                            dep_result = execute_query(dep_query)
                            if not dep_result.empty and dep_result.iloc[0, 0] > 0:
                                st.error(f"⚠️ Cannot delete: {dep_result.iloc[0, 0]} {dep_name} reference this code")
                                has_dependencies = True
                        except:
                            pass
                    
                    if not has_dependencies:
                        confirm_delete = st.checkbox("I understand this will permanently delete the system code")
                        
                        if st.button("🗑️ DELETE SYSTEM CODE", type="primary", disabled=not confirm_delete):
                            delete_query = "DELETE FROM admin.system_codes WHERE code_id = %s;"
                            if execute_query(delete_query, (selected_code,), fetch=False):
                                st.success("System code deleted successfully!")
                                st.rerun()
                    else:
                        st.info("💡 Tip: Deactivate the code instead of deleting it to preserve data integrity")
        else:
            st.warning("No system codes available to delete.")


def admin_pipelines():
    """Pipeline management interface"""
    st.header("📡 Pipeline Management")

    # Use modern query params
    query_params = st.query_params
    default_tab = query_params.get("tab", "view")

    tab1, tab2, tab3 = st.tabs(["View Pipelines", "Add/Edit Pipeline", "Pipeline Environments & Details"])

    with tab1:
        st.subheader("Current Pipelines")

        pipelines_query = """
        SELECT f.pipeline_id, f.pipeline_name, f.pipeline_type_cd, 
               sc.code_description as pipeline_type_description,
               scc.code_description as pipeline_status_description,
               f.pipeline_description, f.pipeline_tag, f.is_active, f.created_at,
               (SELECT COUNT(*) FROM pipeline.pipeline_run fr WHERE fr.pipeline_id = f.pipeline_id) as run_count
        FROM pipeline.pipeline f
        JOIN admin.system_codes sc ON f.pipeline_type_cd = sc.common_cd AND sc.code_type_cd = 'FEED_TYPE'
        LEFT JOIN admin.system_codes scc ON f.pipeline_status_id = scc.code_id
        ORDER BY f.pipeline_name;
        """
        pipelines_df = execute_query(pipelines_query)

        if not pipelines_df.empty:
            # Display pipelines table
            display_df = pipelines_df.drop(columns=['pipeline_id'])
            st.dataframe(display_df, use_container_width=True)

            # Pipeline selection for editing
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_pipeline = st.selectbox(
                    "Select a pipeline to edit:", 
                    options=pipelines_df['pipeline_id'], 
                    format_func=lambda fid: pipelines_df[pipelines_df['pipeline_id'] == fid]['pipeline_name'].iloc[0],
                    key="pipeline_selector"
                )
            with col2:
                if st.button("Edit Selected Pipeline", type="primary"):
                    st.session_state['selected_pipeline_id_for_edit'] = selected_pipeline
                    st.query_params["tab"] = "edit"
                    st.rerun()
        else:
            st.warning("No pipelines found.")
            if st.button("Add First Pipeline"):
                st.query_params["tab"] = "edit"
                st.rerun()

    with tab2:
        st.subheader("Add or Edit Pipeline")

        # Get reference data
        pipeline_types_df = execute_query("""
            SELECT common_cd, code_description 
            FROM admin.system_codes 
            WHERE code_type_cd = 'FEED_TYPE' AND is_active = true
            ORDER BY sort_order, common_cd;
        """)
        
        pipeline_status_df = execute_query("""
            SELECT code_id, code_description
            FROM admin.system_codes
            WHERE code_type_cd = 'FEED_STATUS' AND is_active = true
            ORDER BY sort_order, code_description;
        """)

        # Determine mode and get existing data
        pipeline_id = st.session_state.get('selected_pipeline_id_for_edit')
        mode = "Edit" if pipeline_id else "Add"
        
        if mode == "Edit":
            st.info(f"Editing pipeline ID: {pipeline_id}")
            pipeline_data = execute_query("SELECT * FROM pipeline.pipeline WHERE pipeline_id = %s", (pipeline_id,))
            if pipeline_data.empty:
                st.error("Pipeline not found!")
                st.session_state.pop('selected_pipeline_id_for_edit', None)
                st.rerun()
            pipeline_data = pipeline_data.iloc[0]
        else:
            pipeline_data = pd.Series(dtype=object)

        # Form for add/edit
        with st.form("pipeline_form", clear_on_submit=False):
            pipeline_name = st.text_input(
                "Pipeline Name", 
                value=pipeline_data.get('pipeline_name', '') if not pipeline_data.empty else "", 
                max_chars=255
            )

            # Pipeline type selection
            if not pipeline_types_df.empty:
                type_index = 0
                if not pipeline_data.empty and 'pipeline_type_cd' in pipeline_data:
                    try:
                        type_index = pipeline_types_df['common_cd'].tolist().index(pipeline_data['pipeline_type_cd'])
                    except ValueError:
                        pass
                
                pipeline_type = st.selectbox(
                    "Pipeline Type", 
                    pipeline_types_df['common_cd'],
                    format_func=lambda x: f"{x} - {pipeline_types_df[pipeline_types_df['common_cd'] == x]['code_description'].iloc[0]}",
                    index=type_index
                )
            else:
                st.error("No pipeline types available")
                return

            # Pipeline status selection
            if not pipeline_status_df.empty:
                status_index = 0
                if not pipeline_data.empty and 'pipeline_status_id' in pipeline_data:
                    try:
                        status_index = pipeline_status_df['code_id'].tolist().index(pipeline_data['pipeline_status_id'])
                    except ValueError:
                        pass
                
                pipeline_status = st.selectbox(
                    "Pipeline Status", 
                    pipeline_status_df['code_id'],
                    format_func=lambda x: f"{pipeline_status_df[pipeline_status_df['code_id'] == x]['code_description'].iloc[0]}",
                    index=status_index
                )
            else:
                st.error("No pipeline statuses available")
                return

            pipeline_desc = st.text_area(
                "Description", 
                value=pipeline_data.get('pipeline_description', '') if not pipeline_data.empty else ""
            )

            # NEW: Pipeline tag input
            pipeline_tag = st.text_input(
                "Pipeline Tag", 
                value=pipeline_data.get('pipeline_tag', '') if not pipeline_data.empty else "",
                max_chars=255,
                help="Optional tag for categorizing or labeling this pipeline"
            )

            is_active = st.checkbox(
                "Active", 
                value=pipeline_data.get('is_active', True) if not pipeline_data.empty else True
            )

            # Submit button
            submitted = st.form_submit_button(f"{mode} Pipeline", type="primary")
            
            if submitted:
                if not pipeline_name.strip():
                    st.error("Pipeline name is required.")
                else:
                    try:
                        if mode == "Add":
                            query = """
                            INSERT INTO pipeline.pipeline (pipeline_name, pipeline_type_cd, pipeline_type_cd_type, pipeline_status_id, pipeline_description, pipeline_tag, is_active)
                            VALUES (%s, %s, 'FEED_TYPE', %s, %s, %s, %s);
                            """
                            params = (pipeline_name, pipeline_type, pipeline_status, pipeline_desc, pipeline_tag if pipeline_tag.strip() else None, is_active)
                        else:
                            query = """
                            UPDATE pipeline.pipeline
                            SET pipeline_name = %s, pipeline_type_cd = %s, pipeline_status_id = %s, pipeline_description = %s, pipeline_tag = %s, is_active = %s
                            WHERE pipeline_id = %s;
                            """
                            params = (pipeline_name, pipeline_type, pipeline_status, pipeline_desc, pipeline_tag if pipeline_tag.strip() else None, is_active, pipeline_id)
                        
                        if execute_query(query, params, fetch=False):
                            st.success(f"Pipeline '{pipeline_name}' {mode.lower()}ed successfully!")
                            st.session_state.pop('selected_pipeline_id_for_edit', None)
                            st.query_params.clear()
                            st.rerun()
                        else:
                            st.error(f"Failed to {mode.lower()} pipeline.")
                    except Exception as e:
                        st.error(f"Error {mode.lower()}ing pipeline: {str(e)}")

        # Delete section (only for edit mode)
        if mode == "Edit":
            st.divider()
            st.subheader("⚠️ Danger Zone")
            
            with st.expander("Delete Pipeline", expanded=False):
                st.warning("This action cannot be undone. All related data (environments, details, runs) will be deleted.")
                
                confirm_delete = st.checkbox("I understand this will delete all related data")
                
                if confirm_delete:
                    if st.button("🗑️ DELETE FEED", type="secondary"):
                        try:
                            # Delete in correct order to handle foreign key constraints
                            delete_queries = [
                                "DELETE FROM pipeline.pipeline_details WHERE pipeline_id = %s;",
                                "DELETE FROM pipeline.pipeline_run WHERE pipeline_id = %s;",
                                "DELETE FROM pipeline.pipeline_environment WHERE pipeline_id = %s;",
                                "DELETE FROM pipeline.pipeline WHERE pipeline_id = %s;"
                            ]
                            
                            success = True
                            for query in delete_queries:
                                if not execute_query(query, (pipeline_id,), fetch=False):
                                    success = False
                                    break
                            
                            if success:
                                st.success("Pipeline deleted successfully.")
                                st.session_state.pop('selected_pipeline_id_for_edit', None)
                                st.query_params.clear()
                                st.rerun()
                            else:
                                st.error("Failed to delete pipeline.")
                        except Exception as e:
                            st.error(f"Error deleting pipeline: {str(e)}")

        # Cancel/Back button
        if mode == "Edit":
            if st.button("← Back to Pipeline List"):
                st.session_state.pop('selected_pipeline_id_for_edit', None)
                st.query_params.clear()
                st.rerun()

    with tab3:
        st.subheader("Pipeline Environments & Details")

        pipelines = execute_query("SELECT pipeline_id, pipeline_name FROM pipeline.pipeline ORDER BY pipeline_name;")

        if not pipelines.empty:
            pipeline_options = pipelines.set_index("pipeline_id")['pipeline_name'].to_dict()
            selected_pipeline_id = st.selectbox(
                "Select Pipeline", 
                options=list(pipeline_options.keys()), 
                format_func=lambda x: pipeline_options[x]
            )

            # Pipeline Environments
            st.markdown("### Pipeline Environments")
            envs_df = execute_query("""
                SELECT e.environment_id, e.env_system_cd, s.code_description AS environment_label, e.created_at
                FROM pipeline.pipeline_environment e
                JOIN admin.system_codes s ON e.env_system_cd = s.code_id
                WHERE e.pipeline_id = %s
                ORDER BY e.created_at DESC;
            """, (selected_pipeline_id,))

            if not envs_df.empty:
                st.dataframe(envs_df, use_container_width=True)

            # Add environment
            env_codes_df = execute_query("""
                SELECT code_id, code_description FROM admin.system_codes
                WHERE code_type_cd = 'FEED_ENVIRONMENT' AND is_active = true
                ORDER BY sort_order;
            """)

            with st.form("add_env"):
                if not env_codes_df.empty:
                    env_code_id = st.selectbox(
                        "Environment", 
                        env_codes_df['code_id'],
                        format_func=lambda x: env_codes_df[env_codes_df['code_id'] == x]['code_description'].iloc[0]
                    )
                    
                    if st.form_submit_button("Add Environment"):
                        insert_env_query = """
                        INSERT INTO pipeline.pipeline_environment (pipeline_id, env_system_cd)
                        VALUES (%s, %s);
                        """
                        if execute_query(insert_env_query, (selected_pipeline_id, env_code_id), fetch=False):
                            st.success("Environment added successfully")
                            st.rerun()

            # Pipeline Details
            st.markdown("### Pipeline Details")
            details_df = execute_query("""
                SELECT fd.detail_id, fd.detail_desc, fd.detail_data, fd.created_at,
                       sc.code_description AS detail_type_desc,
                       senv.code_description AS environment_desc,
                       fd.detail_type_cd, fd.environment_id
                FROM pipeline.pipeline_details fd
                JOIN admin.system_codes sc ON fd.detail_type_cd = sc.common_cd
                JOIN pipeline.pipeline_environment fe ON fd.environment_id = fe.environment_id
                JOIN admin.system_codes senv ON fe.env_system_cd = senv.code_id
                WHERE fd.pipeline_id = %s
                ORDER BY fd.created_at DESC;
            """, (selected_pipeline_id,))

            if not details_df.empty:
                # Display details with edit/delete options
                for idx, detail in details_df.iterrows():
                    with st.expander(f"Detail: {detail['detail_desc'][:50]}..." if len(detail['detail_desc']) > 50 else f"Detail: {detail['detail_desc']}"):
                        col1, col2, col3 = st.columns([6, 1, 1])
                        
                        with col1:
                            st.write(f"**Type:** {detail['detail_type_desc']}")
                            st.write(f"**Environment:** {detail['environment_desc']}")
                            st.write(f"**Created:** {detail['created_at']}")
                            st.write(f"**Description:** {detail['detail_desc']}")
                            st.write(f"**Data:** {detail['detail_data']}")
                        
                        with col2:
                            if st.button("Edit", key=f"edit_detail_{detail['detail_id']}"):
                                st.session_state[f'editing_detail_{detail["detail_id"]}'] = True
                                st.rerun()
                        
                        with col3:
                            if st.button("Delete", key=f"delete_detail_{detail['detail_id']}"):
                                delete_detail_query = "DELETE FROM pipeline.pipeline_details WHERE detail_id = %s;"
                                if execute_query(delete_detail_query, (detail['detail_id'],), fetch=False):
                                    st.success("Detail deleted")
                                    st.rerun()

                        # Edit form (appears when edit button clicked)
                        if st.session_state.get(f'editing_detail_{detail["detail_id"]}', False):
                            st.markdown("---")
                            
                            detail_codes_df = execute_query("""
                                SELECT common_cd, code_description FROM admin.system_codes
                                WHERE code_type_cd = 'FEED_RUN_DETAIL_TYPE' AND is_active = true
                                ORDER BY sort_order;
                            """)
                            
                            with st.form(f"edit_detail_{detail['detail_id']}"):
                                edit_desc = st.text_area("Detail Description", value=detail['detail_desc'])
                                edit_data = st.text_area("Detail Data", value=detail['detail_data'])
                                
                                # Detail type
                                type_index = 0
                                try:
                                    type_index = detail_codes_df['common_cd'].tolist().index(detail['detail_type_cd'])
                                except ValueError:
                                    pass
                                
                                edit_type = st.selectbox(
                                    "Detail Type", 
                                    detail_codes_df['common_cd'],
                                    format_func=lambda x: detail_codes_df[detail_codes_df['common_cd'] == x]['code_description'].iloc[0],
                                    index=type_index
                                )
                                
                                # Environment
                                env_index = 0
                                try:
                                    env_index = envs_df['environment_id'].tolist().index(detail['environment_id'])
                                except ValueError:
                                    pass
                                
                                edit_env = st.selectbox(
                                    "Environment", 
                                    envs_df['environment_id'],
                                    format_func=lambda x: envs_df[envs_df['environment_id'] == x]['environment_label'].iloc[0],
                                    index=env_index
                                )
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("Save Changes"):
                                        update_detail_query = """
                                        UPDATE pipeline.pipeline_details 
                                        SET detail_desc = %s, detail_data = %s, detail_type_cd = %s, environment_id = %s
                                        WHERE detail_id = %s;
                                        """
                                        if execute_query(update_detail_query, (edit_desc, edit_data, edit_type, edit_env, detail['detail_id']), fetch=False):
                                            st.success("Detail updated")
                                            st.session_state.pop(f'editing_detail_{detail["detail_id"]}', None)
                                            st.rerun()
                                
                                with col2:
                                    if st.form_submit_button("Cancel"):
                                        st.session_state.pop(f'editing_detail_{detail["detail_id"]}', None)
                                        st.rerun()

            # Add new detail
            st.markdown("#### Add New Detail")
            detail_codes_df = execute_query("""
                SELECT common_cd, code_description FROM admin.system_codes
                WHERE code_type_cd = 'FEED_RUN_DETAIL_TYPE' AND is_active = true
                ORDER BY sort_order;
            """)

            with st.form("add_detail"):
                detail_desc = st.text_area("Detail Description")
                detail_data = st.text_area("Detail Data (Text)")
                
                if not detail_codes_df.empty:
                    detail_type = st.selectbox(
                        "Detail Type Code", 
                        detail_codes_df['common_cd'],
                        format_func=lambda x: detail_codes_df[detail_codes_df['common_cd'] == x]['code_description'].iloc[0]
                    )

                    if not envs_df.empty:
                        environment_id = st.selectbox(
                            "Environment", 
                            envs_df['environment_id'],
                            format_func=lambda x: envs_df[envs_df['environment_id'] == x]['environment_label'].iloc[0]
                        )

                        if st.form_submit_button("Add Detail"):
                            if detail_desc.strip():
                                insert_detail_query = """
                                INSERT INTO pipeline.pipeline_details (
                                    pipeline_id, environment_id, detail_type_cd, detail_type_cd_type, detail_desc, detail_data
                                ) VALUES (%s, %s, %s, 'FEED_RUN_DETAIL_TYPE', %s, %s);
                                """
                                if execute_query(insert_detail_query, (selected_pipeline_id, environment_id, detail_type, detail_desc, detail_data), fetch=False):
                                    st.success("Detail added successfully")
                                    st.rerun()
                            else:
                                st.error("Detail description is required")
                    else:
                        st.warning("No environments found for this pipeline. Please add an environment first.")

        else:
            st.warning("No pipelines available. Please create a pipeline first.")


def dashboard():
    """Main dashboard with overview"""
    st.header("📊 Pipeline Management Dashboard")
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        pipelines_count = execute_query("SELECT COUNT(*) as count FROM pipeline.pipeline WHERE is_active = true;")
        count = pipelines_count.iloc[0, 0] if not pipelines_count.empty else 0
        st.metric("Active Pipelines", count)
    
    with col2:
        runs_today = execute_query("""
            SELECT COUNT(*) as count FROM pipeline.pipeline_run 
            WHERE DATE(start_dt) = CURRENT_DATE;
        """)
        count = runs_today.iloc[0, 0] if not runs_today.empty else 0
        st.metric("Runs Today", count)
    
    with col3:
        success_rate = execute_query("""
            SELECT 
                COALESCE(
                    ROUND(
                        COUNT(CASE WHEN status_cd = 'COMPLETED' THEN 1 END) * 100.0 / 
                        NULLIF(COUNT(*), 0), 
                        1
                    ), 0
                ) as success_rate
            FROM pipeline.pipeline_run 
            WHERE start_dt >= CURRENT_DATE - INTERVAL '30 days';
        """)
        rate = success_rate.iloc[0, 0] if not success_rate.empty else 0
        st.metric("30-Day Success Rate", f"{rate}%")
    
    with col4:
        system_codes_count = execute_query("SELECT COUNT(*) as count FROM admin.system_codes WHERE is_active = true;")
        count = system_codes_count.iloc[0, 0] if not system_codes_count.empty else 0
        st.metric("Active System Codes", count)
    
    # Recent activity
    st.subheader("🕒 Recent Pipeline Runs")
    recent_runs = execute_query("""
        SELECT fr.pipeline_run_id, f.pipeline_name, fr.start_dt, fr.end_dt, 
               sc.code_description as status, fr.description
        FROM pipeline.pipeline_run fr
        JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
        JOIN admin.system_codes sc ON fr.status_cd = sc.common_cd
        WHERE sc.code_type_cd = 'STATUS'
        ORDER BY fr.start_dt DESC
        LIMIT 10;
    """)
    
    if not recent_runs.empty:
        st.dataframe(recent_runs, use_container_width=True)
    else:
        st.info("No recent pipeline runs found.")

def main():
    """Main application"""
    st.title("🔧 Pipeline Management System - Admin Interface")
    
    # Sidebar navigation
    st.sidebar.title("🧭 Navigation")
    page = st.sidebar.selectbox(
        "Choose a section",
        ["Dashboard", "Database Setup", "System Codes", "Pipeline Management"]
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

if __name__ == "__main__":
    main()