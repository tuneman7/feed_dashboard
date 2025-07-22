# system_codes.py
"""
System codes management functionality
"""
import streamlit as st
import pandas as pd
from database_utils import execute_query

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