# pipeline_management.py
"""
Pipeline management functionality
"""
import streamlit as st
import pandas as pd
from database_utils import execute_query

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
        JOIN admin.system_codes sc ON f.pipeline_type_cd = sc.common_cd AND sc.code_type_cd = 'PIPELINE_TYPE'
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
            WHERE code_type_cd = 'PIPELINE_TYPE' AND is_active = true
            ORDER BY sort_order, common_cd;
        """)
        
        pipeline_status_df = execute_query("""
            SELECT code_id, code_description
            FROM admin.system_codes
            WHERE code_type_cd = 'PIPELINE_STATUS' AND is_active = true
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

            # Pipeline tag input
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
                            VALUES (%s, %s, 'PIPELINE_TYPE', %s, %s, %s, %s);
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
                    if st.button("🗑️ DELETE PIPELINE", type="secondary"):
                        try:
                            # Delete in correct order to handle foreign key constraints
                            delete_queries = [
                                # First: Delete pipeline_run_details (references pipeline_run)
                                "DELETE FROM pipeline.pipeline_run_details WHERE pipeline_run_id IN (SELECT pipeline_run_id FROM pipeline.pipeline_run WHERE pipeline_id = %s);",
                                # Second: Delete pipeline_run (references pipeline and pipeline_environment)
                                "DELETE FROM pipeline.pipeline_run WHERE pipeline_id = %s;",
                                # Third: Delete pipeline_details (references pipeline and pipeline_environment)
                                "DELETE FROM pipeline.pipeline_details WHERE pipeline_id = %s;",
                                # Fourth: Delete pipeline_environment (references pipeline)
                                "DELETE FROM pipeline.pipeline_environment WHERE pipeline_id = %s;",
                                # Finally: Delete the pipeline itself
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
                WHERE code_type_cd = 'PIPELINE_ENVIRONMENT' AND is_active = true
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
                                WHERE code_type_cd = 'PIPELINE_RUN_DETAIL_TYPE' AND is_active = true
                                ORDER BY sort_order;
                            """)
                            
                            with st.form(f"edit_detail_{detail['detail_id']}"):
                                edit_desc = st.text_area("Detail Description", value=detail['detail_desc'])
                                edit_data = st.text_area("Detail Data", value=detail['detail_data'])
                                
                                # Detail type
                                type_index = 0
                                
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
                WHERE code_type_cd = 'PIPELINE_RUN_DETAIL_TYPE' AND is_active = true
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
                                ) VALUES (%s, %s, %s, 'PIPELINE_RUN_DETAIL_TYPE', %s, %s);
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