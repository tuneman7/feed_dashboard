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


def dashboard():
    """Main dashboard with overview"""
    st.header("📊 Pipeline Management Dashboard")

    # Get environment selection first (moved from filters section)
    environments_query = """
    SELECT DISTINCT env_sc.common_cd as environment
    FROM pipeline.pipeline_environment pe
    JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
    ORDER BY env_sc.common_cd;
    """
    environments_df = execute_query(environments_query)

    # Create dropdown for environment selection at the top
    environment_options = ['All'] + environments_df['environment'].tolist()
    selected_environment = st.selectbox(
        "Select Environment:",
        options=environment_options,
        index=0  # Default to 'All'
    )

    # Build environment filter for stats queries
    stats_environment_filter = ""
    if selected_environment != 'All':
        stats_environment_filter = f"""
        JOIN pipeline.pipeline_environment pe ON p.pipeline_id = pe.pipeline_id
        JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
        AND env_sc.common_cd = '{selected_environment}'
        """

        runs_environment_filter = f"""
        JOIN pipeline.pipeline_environment pe ON pr.environment_id = pe.environment_id
        JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
        AND env_sc.common_cd = '{selected_environment}'
        """
    else:
        runs_environment_filter = ""

    # Quick stats (now reactive to environment)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        pipelines_count = execute_query(f"""
            SELECT COUNT(*) as count 
            FROM pipeline.pipeline p
            {stats_environment_filter}
            WHERE p.is_active = true;
        """)
        count = pipelines_count.iloc[0, 0] if not pipelines_count.empty else 0
        st.metric("Active Pipelines", count)

    with col2:
        runs_today = execute_query(f"""
            SELECT COUNT(*) as count 
            FROM pipeline.pipeline_run pr
            {runs_environment_filter}
            WHERE DATE(pr.start_dt) = CURRENT_DATE;
        """)
        count = runs_today.iloc[0, 0] if not runs_today.empty else 0
        st.metric("Runs Today", count)

    with col3:
        success_rate = execute_query(f"""
            SELECT 
                COALESCE(
                    ROUND(
                        COUNT(CASE WHEN pr.status_cd = 'COMPLETED' THEN 1 END) * 100.0 / 
                        NULLIF(COUNT(*), 0), 
                        1
                    ), 0
                ) as success_rate
            FROM pipeline.pipeline_run pr
            {runs_environment_filter}
            WHERE pr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
                AND pr.status_cd IN ('COMPLETED', 'FAILED');
        """)
        rate = success_rate.iloc[0, 0] if not success_rate.empty else 0
        st.metric("30-Day Success Rate", f"{rate}%")

    with col4:
        system_codes_count = execute_query("SELECT COUNT(*) as count FROM admin.system_codes WHERE is_active = true;")
        count = system_codes_count.iloc[0, 0] if not system_codes_count.empty else 0
        st.metric("Active System Codes", count)

    # Recent activity
    st.subheader("🕒 Recent Pipeline Runs")

    # Create column for pipeline filter (environment filter already selected above)
    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        st.write(f"**Environment:** {selected_environment}")

    with filter_col2:
        # Get available pipelines
        pipelines_query = """
        SELECT DISTINCT pipeline_name
        FROM pipeline.pipeline
        WHERE is_active = true
        ORDER BY pipeline_name;
        """
        pipelines_df = execute_query(pipelines_query)

        # Create multiselect for pipeline selection
        pipeline_options = pipelines_df['pipeline_name'].tolist()
        selected_pipelines = st.multiselect(
            "Select Pipeline(s):",
            options=pipeline_options,
            default=[],  # Default to empty (All)
            placeholder="All pipelines"
        )

    # Build the WHERE clause based on selections
    environment_filter = ""
    if selected_environment != 'All':
        environment_filter = f"AND env_sc.common_cd = '{selected_environment}'"

    pipeline_filter = ""
    if selected_pipelines:
        # Convert list to SQL IN clause
        pipeline_names = "', '".join(selected_pipelines)
        pipeline_filter = f"AND f.pipeline_name IN ('{pipeline_names}')"

    recent_runs = execute_query(f"""
-- Get top 10 failed runs plus other runs, limited to 60 total
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
    JOIN admin.system_codes sc ON fr.status_cd = sc.common_cd
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
    JOIN admin.system_codes sc ON fr.status_cd = sc.common_cd
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
    """)

    if not recent_runs.empty:
        st.dataframe(
            recent_runs.drop(columns=["status_desc"]),
            use_container_width=True,
            column_config={
                "cloudwatch_url": st.column_config.LinkColumn(
                    "CloudWatch Log",
                    display_text="View Logs"
                ),
                "pipeline_run_id": "Run ID"
            },
            hide_index=True
        )

        # Action section: show delete buttons ONLY for running/progress/active statuses
        st.markdown("### 🧹 Manage Running Runs")
        running_mask = recent_runs['status_desc'].str.upper().str.contains('RUNNING|PROGRESS|ACTIVE', regex=True, na=False)
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
                        if row.get('cloudwatch_url'):
                            st.link_button(f"View Logs: {row['pipeline_run_id']}", row['cloudwatch_url'])
                    with right:
                        if st.button("🗑️ Delete Run", key=f"del_{row['pipeline_run_id']}"):
                            if _delete_single_run(int(row['pipeline_run_id'])):
                                st.success(f"Deleted run {row['pipeline_run_id']}.")
                                st.rerun()
    else:
        st.info("No recent pipeline runs found.")
