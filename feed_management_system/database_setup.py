# database_setup.py
"""
Database setup and initialization functionality
"""
import streamlit as st
import glob
import os
from database_utils import init_connection, execute_query

def clear_database():
    """Clear all user-defined objects by running sql/clear_database/*.sql in order"""
    clear_path = os.path.join("sql", "clear_database", "*.sql")
    clear_files = sorted(glob.glob(clear_path))

    for file_path in clear_files:
        try:
            with open(file_path, "r") as f:
                sql_block = f.read()
                if sql_block.strip():
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