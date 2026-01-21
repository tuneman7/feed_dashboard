"""
Main dashboard functionality (with delete-run action for running pipelines)
"""
import streamlit as st
from database_utils import execute_query


def _delete_single_run(run_id: int) -> bool:
    """Delete a single pipeline run and its descendant attributes."""
    try:
        # Delete details first (FK to pipeline_run)
        execute_query(
            "DELETE FROM pipeline.pipeline_run_details WHERE pipeline_run_id = %s;",
            (run_id,),
            fetch=False,
        )
        # Delete the run itself
        execute_query(
            "DELETE FROM pipeline.pipeline_run WHERE pipeline_run_id = %s;",
            (run_id,),
            fetch=False,
        )
        return True
    except Exception as e:
        st.error(f"Failed to delete run {run_id}: {e}")
        return False


def show_run_details(run_id: int):
    """Display detailed information for a specific pipeline run."""
    # Add a back button
    if st.button("← Back to Dashboard"):
        st.session_state.selected_run_id = None
        st.rerun()

    st.header(f"📋 Pipeline Run Details - Run ID: {run_id}")
    st.markdown("---")

    try:
        # Get run summary
        run_summary_query = """
        SELECT 
            pr.pipeline_run_id,
            p.pipeline_name,
            p.pipeline_description,
            env_sc.common_cd as environment,
            pr.start_dt,
            pr.end_dt,
            CASE 
                WHEN pr.end_dt IS NOT NULL THEN 
                    EXTRACT(EPOCH FROM (pr.end_dt - pr.start_dt))/60.0
                ELSE NULL
            END as duration_minutes,
            sc.common_cd as status,
            sc.code_description as status_desc,
            pr.description as run_description,
            pr.created_at,
            pr.updated_at
        FROM pipeline.pipeline_run pr
        JOIN pipeline.pipeline p ON pr.pipeline_id = p.pipeline_id
        JOIN pipeline.pipeline_environment pe ON pr.environment_id = pe.environment_id
        JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
        JOIN admin.system_codes sc ON pr.status_cd = sc.common_cd AND sc.code_type_cd = pr.status_cd_type
        WHERE pr.pipeline_run_id = %s;
        """

        run_summary = execute_query(run_summary_query, (run_id,))

        if run_summary.empty:
            st.error(f"No run found with ID: {run_id}")
            return

        run_data = run_summary.iloc[0]

        # Display run summary
        st.subheader("Run Summary")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Pipeline Name", run_data["pipeline_name"])
            st.metric("Environment", run_data["environment"])
            st.metric("Status", run_data["status_desc"])

        with col2:
            st.metric(
                "Start Time",
                run_data["start_dt"].strftime("%Y-%m-%d %H:%M:%S") if run_data["start_dt"] else "N/A",
            )
            st.metric(
                "End Time",
                run_data["end_dt"].strftime("%Y-%m-%d %H:%M:%S") if run_data["end_dt"] else "Running",
            )
            if run_data["duration_minutes"] is not None:
                st.metric("Duration", f"{run_data['duration_minutes']:.2f} min")
            else:
                st.metric("Duration", "N/A")

        with col3:
            st.metric("Run ID", run_data["pipeline_run_id"])
            st.metric(
                "Created At",
                run_data["created_at"].strftime("%Y-%m-%d %H:%M:%S") if run_data["created_at"] else "N/A",
            )
            st.metric(
                "Updated At",
                run_data["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if run_data["updated_at"] else "N/A",
            )

        # Display descriptions
        st.markdown("---")
        if run_data["pipeline_description"]:
            st.write(f"**Pipeline Description:** {run_data['pipeline_description']}")
        if run_data["run_description"]:
            st.write(f"**Run Description:** {run_data['run_description']}")

        # Get run details
        st.markdown("---")
        st.subheader("Run Details")

        run_details_query = """
        SELECT 
            prd.detail_id,
            prd.parent_detail_id,
            sc.common_cd as detail_type,
            sc.code_description as detail_type_desc,
            prd.detail_desc,
            prd.detail_data,
            prd.created_at
        FROM pipeline.pipeline_run_details prd
        JOIN admin.system_codes sc ON prd.run_detail_type_cd = sc.code_id
        WHERE prd.pipeline_run_id = %s
        ORDER BY prd.created_at, prd.detail_id;
        """

        run_details = execute_query(run_details_query, (run_id,))

        if not run_details.empty:
            # Display quick links and metrics dynamically
            st.write("**Quick Links & Key Metrics:**")

            # Separate details into links and metrics
            link_details = []
            metric_details = []

            for _, detail in run_details.iterrows():
                detail_data_str = str(detail["detail_data"]) if detail["detail_data"] else ""

                # Check if it's a URL
                if detail_data_str.startswith(("http://", "https://")):
                    link_details.append(detail)
                # Check if it's numeric (count, error count, etc.)
                elif detail_data_str.replace(".", "", 1).replace("-", "", 1).isdigit():
                    metric_details.append(detail)

            # Display links (limit to 4 columns for better layout)
            if link_details:
                st.write("*Links:*")
                num_cols = min(len(link_details), 4)
                cols = st.columns(num_cols)
                for idx, detail in enumerate(link_details):
                    with cols[idx % num_cols]:
                        st.link_button(f"📝 {detail['detail_type_desc']}", detail["detail_data"])

            # Display metrics (limit to 4 columns for better layout)
            if metric_details:
                if link_details:  # Add spacing if links exist
                    st.write("")
                st.write("*Metrics:*")
                num_cols = min(len(metric_details), 4)
                cols = st.columns(num_cols)
                for idx, detail in enumerate(metric_details):
                    with cols[idx % num_cols]:
                        st.metric(detail["detail_type_desc"], detail["detail_data"])

            # If no links or metrics were found, show a message
            if not link_details and not metric_details:
                st.info("No quick links or metrics available.")

            st.markdown("---")
            st.write("**All Run Details:**")

            # Display all details in an expandable dataframe
            display_df = run_details.copy()

            # For very long detail_data, truncate for display but show full in expander
            for idx, row in display_df.iterrows():
                if row["detail_data"] and len(str(row["detail_data"])) > 100:
                    display_df.at[idx, "detail_data_preview"] = str(row["detail_data"])[:100] + "..."
                else:
                    display_df.at[idx, "detail_data_preview"] = row["detail_data"]

            st.dataframe(
                display_df[
                    [
                        "detail_id",
                        "parent_detail_id",
                        "detail_type",
                        "detail_type_desc",
                        "detail_desc",
                        "detail_data_preview",
                        "created_at",
                    ]
                ],
                use_container_width=True,
                column_config={
                    "detail_id": "Detail ID",
                    "parent_detail_id": "Parent ID",
                    "detail_type": "Type",
                    "detail_type_desc": "Type Description",
                    "detail_desc": "Description",
                    "detail_data_preview": "Data",
                    "created_at": "Created At",
                },
                hide_index=True,
            )

            # Show full details in expanders for long data
            st.markdown("---")
            st.write("**View Full Detail Data:**")
            for _, detail in run_details.iterrows():
                if detail["detail_data"] and len(str(detail["detail_data"])) > 100:
                    with st.expander(
                        f"Detail {detail['detail_id']}: {detail['detail_type']} - {detail['detail_desc']}"
                    ):
                        st.code(detail["detail_data"], language=None)
        else:
            st.info("No detailed information available for this run.")

    except Exception as e:
        st.error(f"Error loading run details: {e}")
        st.exception(e)


def dashboard():
    """Main dashboard with overview"""
    # Check if we should show run details
    if "selected_run_id" in st.session_state and st.session_state.selected_run_id is not None:
        show_run_details(st.session_state.selected_run_id)
        return

    st.header("📊 Pipeline Management Dashboard")

    # Add refresh button at the top
    col_refresh, col_spacer = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 Refresh", type="secondary"):
            st.rerun()

    st.markdown("---")

    # Get environment selection (changed to multiselect with prod default)
    environments_query = """
    SELECT DISTINCT env_sc.common_cd as environment
    FROM pipeline.pipeline_environment pe
    JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
    ORDER BY env_sc.common_cd;
    """

    # --- CHANGED: put Environment + Pipeline on the same row ---
    filter_top_col1, filter_top_col2 = st.columns(2)

    # --- CHANGED: state helpers to persist dropdowns across reruns / details page ---
    ENV_WIDGET_KEY = "dashboard_selected_environments"
    PIPE_WIDGET_KEY = "dashboard_selected_pipeline"
    PERSIST_ENV_KEY = "persisted_selected_environments"
    PERSIST_PIPE_KEY = "persisted_selected_pipeline"

    def _on_env_change():
        st.session_state[PERSIST_ENV_KEY] = st.session_state.get(ENV_WIDGET_KEY, [])

    def _on_pipe_change():
        st.session_state[PERSIST_PIPE_KEY] = st.session_state.get(PIPE_WIDGET_KEY, "All")
    # --- END CHANGED ---

    try:
        environments_df = execute_query(environments_query)
        environment_options = environments_df["environment"].tolist()

        # Set default to 'prod' (case insensitive) if it exists, otherwise first environment
        prod_env = next((env for env in environment_options if env.lower() == "prod"), None)
        computed_default_env = [prod_env] if prod_env else ([environment_options[0]] if environment_options else [])

        # --- CHANGED: seed persisted env on first load, and seed widget key before rendering ---
        if PERSIST_ENV_KEY not in st.session_state:
            st.session_state[PERSIST_ENV_KEY] = computed_default_env

        if ENV_WIDGET_KEY not in st.session_state:
            st.session_state[ENV_WIDGET_KEY] = st.session_state[PERSIST_ENV_KEY]
        # --- END CHANGED ---

        with filter_top_col1:
            selected_environments = st.multiselect(
                "Select Environment(s):",
                options=environment_options,
                key=ENV_WIDGET_KEY,
                placeholder="Select environments",
                on_change=_on_env_change,
            )
    except Exception as e:
        st.error(f"Error loading environments: {e}")
        selected_environments = []

    # Pipeline selection moved up to same row
    try:
        pipelines_query = """
        SELECT DISTINCT pipeline_name
        FROM pipeline.pipeline
        WHERE is_active = true
        ORDER BY pipeline_name;
        """
        pipelines_df = execute_query(pipelines_query)
        pipeline_options = ["All"] + pipelines_df["pipeline_name"].tolist()

        # --- CHANGED: seed persisted pipeline on first load, and seed widget key before rendering ---
        if PERSIST_PIPE_KEY not in st.session_state:
            st.session_state[PERSIST_PIPE_KEY] = "All"

        if PIPE_WIDGET_KEY not in st.session_state:
            st.session_state[PIPE_WIDGET_KEY] = st.session_state[PERSIST_PIPE_KEY]

        # If stored value is no longer valid, fall back to "All"
        if st.session_state[PIPE_WIDGET_KEY] not in pipeline_options:
            st.session_state[PIPE_WIDGET_KEY] = "All"
            st.session_state[PERSIST_PIPE_KEY] = "All"
        # --- END CHANGED ---

        with filter_top_col2:
            selected_pipeline = st.selectbox(
                "Filter by Pipeline:",
                pipeline_options,
                key=PIPE_WIDGET_KEY,
                on_change=_on_pipe_change,
            )
    except Exception as e:
        st.error(f"Error loading pipelines: {e}")
        selected_pipeline = "All"
    # --- END CHANGED ---

    env_display = ", ".join(selected_environments) if selected_environments else "All"

    # Build environment filter for queries
    def build_environment_filter(table_alias="env_sc", join_required=True):
        if not selected_environments:
            return "", ""

        env_list = "', '".join(selected_environments)

        if join_required:
            join_clause = """
            JOIN pipeline.pipeline_environment pe ON p.pipeline_id = pe.pipeline_id
            JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
            """
            where_clause = f"AND {table_alias}.common_cd IN ('{env_list}')"
        else:
            join_clause = ""
            where_clause = f"AND {table_alias}.common_cd IN ('{env_list}')"

        return join_clause, where_clause

    def build_runs_environment_filter():
        if not selected_environments:
            return "", ""

        env_list = "', '".join(selected_environments)
        join_clause = """
        JOIN pipeline.pipeline_environment pe ON pr.environment_id = pe.environment_id
        JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
        """
        where_clause = f"AND env_sc.common_cd IN ('{env_list}')"

        return join_clause, where_clause

    # Quick stats (now reactive to selected environments)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        try:
            env_join, env_filter = build_environment_filter()
            pipelines_count = execute_query(
                f"""
                SELECT COUNT(*) as count 
                FROM pipeline.pipeline p
                {env_join}
                WHERE p.is_active = true
                {env_filter};
            """
            )
            count = pipelines_count.iloc[0, 0] if not pipelines_count.empty else 0
            st.metric("Active Pipelines", count)
        except Exception as e:
            st.metric("Active Pipelines", "Error")
            st.caption(f"Error: {str(e)[:50]}...")

    with col2:
        try:
            runs_join, runs_filter = build_runs_environment_filter()
            runs_today = execute_query(
                f"""
                SELECT COUNT(*) as count 
                FROM pipeline.pipeline_run pr
                {runs_join}
                WHERE DATE(pr.start_dt) = CURRENT_DATE
                {runs_filter};
            """
            )
            count = runs_today.iloc[0, 0] if not runs_today.empty else 0
            st.metric("Runs Today", count)
        except Exception as e:
            st.metric("Runs Today", "Error")
            st.caption(f"Error: {str(e)[:50]}...")

    with col3:
        try:
            runs_join, runs_filter = build_runs_environment_filter()
            success_rate = execute_query(
                f"""
                SELECT 
                    COALESCE(
                        ROUND(
                            COUNT(CASE WHEN pr.status_cd = 'COMPLETED' THEN 1 END) * 100.0 / 
                            NULLIF(COUNT(*), 0), 
                            1
                        ), 0
                    ) as success_rate
                FROM pipeline.pipeline_run pr
                {runs_join}
                WHERE pr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
                    AND pr.status_cd IN ('COMPLETED', 'FAILED')
                    {runs_filter};
            """
            )
            rate = success_rate.iloc[0, 0] if not success_rate.empty else 0
            st.metric("30-Day Success Rate", f"{rate}%")
        except Exception as e:
            st.metric("30-Day Success Rate", "Error")
            st.caption(f"Error: {str(e)[:50]}...")

    with col4:
        try:
            system_codes_count = execute_query(
                "SELECT COUNT(*) as count FROM admin.system_codes WHERE is_active = true;"
            )
            count = system_codes_count.iloc[0, 0] if not system_codes_count.empty else 0
            st.metric("Active System Codes", count)
        except Exception as e:
            st.metric("Active System Codes", "Error")
            st.caption(f"Error: {str(e)[:50]}...")

    # Recent activity
    st.subheader("🕒 Recent Pipeline Runs")

    # Build pipeline filter
    if selected_pipeline and selected_pipeline != "All":
        pipeline_filter = f"AND f.pipeline_name = '{selected_pipeline}'"
    else:
        pipeline_filter = ""

    # Build environment filter for the runs query
    if selected_environments:
        env_list = "', '".join(selected_environments)
        environment_filter = f"AND env_sc.common_cd IN ('{env_list}')"
    else:
        environment_filter = ""

    # --- CHANGED: placeholder to render "View Details" ABOVE the grid ---
    view_details_placeholder = st.empty()
    # --- END CHANGED ---

    try:
        recent_runs = execute_query(
            f"""
        WITH failed_runs AS (
            SELECT 
                fr.pipeline_run_id,
                f.pipeline_name, 
                env_sc.common_cd as environment,                                
                sc.common_cd as status,
                sc.code_description as status_desc,
                cw_detail.detail_data as cloudwatch_url,
                count_detail.detail_data AS total_processed_count,
                fr.start_dt, 
                fr.end_dt,
                1 as priority_order
            FROM pipeline.pipeline_run fr
            JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
            JOIN admin.system_codes sc ON fr.status_cd = sc.common_cd AND sc.code_type_cd = fr.status_cd_type
            JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
            JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
            LEFT JOIN (
                SELECT DISTINCT prd.pipeline_run_id, prd.detail_data
                FROM pipeline.pipeline_run_details prd
                JOIN admin.system_codes sc_detail ON prd.run_detail_type_cd = sc_detail.code_id
                WHERE sc_detail.common_cd = 'CLOUDWATCH_LOG_LINK'
            ) cw_detail ON fr.pipeline_run_id = cw_detail.pipeline_run_id
            LEFT JOIN (
                SELECT DISTINCT prd.pipeline_run_id, prd.detail_data
                FROM pipeline.pipeline_run_details prd
                JOIN admin.system_codes sc_detail ON prd.run_detail_type_cd = sc_detail.code_id
                WHERE sc_detail.common_cd = 'TOTAL_PROCESSED_COUNT'
            ) count_detail ON fr.pipeline_run_id = count_detail.pipeline_run_id
            WHERE sc.code_type_cd = 'STATUS'
                AND (UPPER(sc.code_description) LIKE '%FAIL%' OR UPPER(sc.code_description) LIKE '%ERROR%')
                {environment_filter}
                {pipeline_filter}
            ORDER BY fr.start_dt DESC
            LIMIT 10
        ),
        other_runs AS (
            SELECT 
                fr.pipeline_run_id,
                f.pipeline_name, 
                env_sc.common_cd as environment,                                
                sc.common_cd as status,
                sc.code_description as status_desc,
                cw_detail.detail_data as cloudwatch_url,
                count_detail.detail_data AS total_processed_count,
                fr.start_dt, 
                fr.end_dt,
                CASE 
                    WHEN UPPER(sc.code_description) LIKE '%RUNNING%' OR UPPER(sc.code_description) LIKE '%PROGRESS%' OR UPPER(sc.code_description) LIKE '%ACTIVE%' THEN 2
                    WHEN UPPER(sc.code_description) LIKE '%COMPLETE%' OR UPPER(sc.code_description) LIKE '%SUCCESS%' OR UPPER(sc.code_description) LIKE '%FINISH%' THEN 3
                    ELSE 4
                END as priority_order
            FROM pipeline.pipeline_run fr
            JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
            JOIN admin.system_codes sc ON fr.status_cd = sc.common_cd AND sc.code_type_cd = fr.status_cd_type
            JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
            JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
            LEFT JOIN (
                SELECT DISTINCT prd.pipeline_run_id, prd.detail_data
                FROM pipeline.pipeline_run_details prd
                JOIN admin.system_codes sc_detail ON prd.run_detail_type_cd = sc_detail.code_id
                WHERE sc_detail.common_cd = 'CLOUDWATCH_LOG_LINK'
            ) cw_detail ON fr.pipeline_run_id = cw_detail.pipeline_run_id
            LEFT JOIN (
                SELECT DISTINCT prd.pipeline_run_id, prd.detail_data
                FROM pipeline.pipeline_run_details prd
                JOIN admin.system_codes sc_detail ON prd.run_detail_type_cd = sc_detail.code_id
                WHERE sc_detail.common_cd = 'TOTAL_PROCESSED_COUNT'
                    AND sc_detail.code_type_cd = 'PIPELINE_RUN_DETAIL_TYPE'
            ) count_detail ON fr.pipeline_run_id = count_detail.pipeline_run_id
            WHERE sc.code_type_cd = 'STATUS'
                AND NOT (UPPER(sc.code_description) LIKE '%FAIL%' OR UPPER(sc.code_description) LIKE '%ERROR%')
                {environment_filter}
                {pipeline_filter}
            ORDER BY priority_order, fr.start_dt DESC
            LIMIT 50
        )
        SELECT 
            pipeline_run_id,
            pipeline_name,
            environment,
            status,
            status_desc,
            cloudwatch_url,
            total_processed_count,
            start_dt,
            end_dt
        FROM (
            SELECT * FROM failed_runs
            UNION ALL
            SELECT * FROM other_runs
        ) combined_results
        ORDER BY priority_order, start_dt DESC;
        """
        )

        if not recent_runs.empty:
            # Add a clickable dataframe with on_select
            event = st.dataframe(
                recent_runs.drop(columns=["status_desc"]),
                use_container_width=True,
                column_config={
                    "cloudwatch_url": st.column_config.LinkColumn("CloudWatch Log", display_text="View Logs"),
                    "pipeline_run_id": "Run ID",
                    "pipeline_name": "Pipeline Name",
                    "environment": "Environment",
                    "status": "Status",
                    "total_processed_count": "Records Processed",
                    "start_dt": "Start Time",
                    "end_dt": "End Time",
                },
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="recent_runs_grid",
            )

            # Update session state with current selection and show button immediately
            if event.selection.rows:
                selected_idx = event.selection.rows[0]
                st.session_state.selected_row_idx = selected_idx

                try:
                    selected_run_id = int(recent_runs.iloc[selected_idx]["pipeline_run_id"])
                    selected_pipeline_name = recent_runs.iloc[selected_idx]["pipeline_name"]

                    # Store run info in session state for the button above the grid
                    st.session_state.selected_run_info = {
                        "run_id": selected_run_id,
                        "pipeline_name": selected_pipeline_name,
                    }

                    # Show immediate feedback below the grid
                    st.markdown("---")
                    st.caption(
                        f"✓ Selected: **{selected_pipeline_name}** (Run ID: {selected_run_id}) - Scroll down to view details"
                    )
                    st.markdown("---")
                except (IndexError, KeyError):
                    # Selection is invalid, clear it
                    st.session_state.selected_row_idx = None
                    if "selected_run_info" in st.session_state:
                        del st.session_state.selected_run_info
            else:
                st.session_state.selected_row_idx = None
                if "selected_run_info" in st.session_state:
                    del st.session_state.selected_run_info

            # --- CHANGED: render the "View Details" UI in the placeholder ABOVE the grid ---
            if "selected_row_idx" in st.session_state and st.session_state.selected_row_idx is not None:
                try:
                    if "selected_run_info" in st.session_state and st.session_state.selected_run_info:
                        selected_run_id = st.session_state.selected_run_info["run_id"]
                        selected_pipeline_name = st.session_state.selected_run_info["pipeline_name"]

                        with view_details_placeholder.container():
                            st.markdown("---")
                            col_button, col_spacer = st.columns([1, 4])
                            with col_button:
                                if st.button(
                                    f"📋 View Details for Run {selected_run_id}",
                                    type="primary",
                                    key="view_details_top",
                                ):
                                    st.session_state.selected_run_id = selected_run_id
                                    st.rerun()

                            st.caption(f"Selected: **{selected_pipeline_name}** (Run ID: {selected_run_id})")
                            st.markdown("---")
                except Exception:
                    pass
            else:
                # If nothing selected, clear placeholder content
                view_details_placeholder.empty()
            # --- END CHANGED ---

            # Action section: show delete buttons ONLY for running/progress/active statuses
            st.markdown("### 🧹 Manage Running Runs")
            running_mask = recent_runs["status_desc"].str.upper().str.contains(
                "RUNNING|PROGRESS|ACTIVE", regex=True, na=False
            )
            running_rows = recent_runs[running_mask]

            if running_rows.empty:
                st.caption("No runs are currently in a running/active state.")
            else:
                for _, row in running_rows.iterrows():
                    with st.container(border=True):
                        left, mid, right = st.columns([3, 3, 2])
                        with left:
                            st.write(f"**{row['pipeline_name']}** · {row['environment']}")
                            st.write(f"Run ID: `{row['pipeline_run_id']}` · Status: {row['status_desc']}")
                        with mid:
                            if row.get("cloudwatch_url"):
                                st.link_button(f"View Logs: {row['pipeline_run_id']}", row["cloudwatch_url"])
                        with right:
                            if st.button("🗑️ Delete Run", key=f"del_{row['pipeline_run_id']}"):
                                if _delete_single_run(int(row["pipeline_run_id"])):
                                    st.success(f"Deleted run {row['pipeline_run_id']}.")
                                    st.rerun()
        else:
            st.info("No recent pipeline runs found for the selected filters.")

    except Exception as e:
        st.error(f"Error loading recent runs: {e}")
        st.caption("Please check your database connection and try refreshing.")

    # Active Pipelines List for Selected Environments
    st.subheader(f"🔗 Active Pipelines - {env_display}")

    try:
        if selected_environments:
            env_list = "', '".join(selected_environments)
            active_pipelines = execute_query(
                f"""
                SELECT 
                    p.pipeline_id,
                    p.pipeline_name,
                    p.pipeline_description,
                    env_sc.common_cd as environment,
                    p.created_at,
                    p.updated_at
                FROM pipeline.pipeline p
                JOIN pipeline.pipeline_environment pe ON p.pipeline_id = pe.pipeline_id
                JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
                WHERE p.is_active = true
                    AND env_sc.common_cd IN ('{env_list}')
                ORDER BY p.pipeline_name;
            """
            )
        else:
            active_pipelines = execute_query(
                """
                SELECT 
                    p.pipeline_id,
                    p.pipeline_name,
                    p.pipeline_description,
                    'All Environments' as environment,
                    p.created_at,
                    p.updated_at
                FROM pipeline.pipeline p
                WHERE p.is_active = true
                ORDER BY p.pipeline_name;
            """
            )

        if not active_pipelines.empty:
            st.dataframe(
                active_pipelines,
                use_container_width=True,
                column_config={
                    "pipeline_id": "Pipeline ID",
                    "pipeline_name": "Pipeline Name",
                    "pipeline_description": "Description",
                    "environment": "Environment",
                    "created_at": "Created",
                    "updated_at": "Last Updated",
                },
                hide_index=True,
            )
        else:
            st.info(f"No active pipelines found for selected environments: {env_display}")
    except Exception as e:
        st.error(f"Error loading active pipelines: {e}")
