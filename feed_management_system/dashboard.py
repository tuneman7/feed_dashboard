# dashboard.py
"""
Main dashboard functionality
"""
import streamlit as st
from database_utils import execute_query

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
            WHERE start_dt >= CURRENT_DATE - INTERVAL '30 days'
                AND status_cd IN ('COMPLETED', 'FAILED');
        """)
        rate = success_rate.iloc[0, 0] if not success_rate.empty else 0
        st.metric("30-Day Success Rate", f"{rate}%")
    
    with col4:
        system_codes_count = execute_query("SELECT COUNT(*) as count FROM admin.system_codes WHERE is_active = true;")
        count = system_codes_count.iloc[0, 0] if not system_codes_count.empty else 0
        st.metric("Active System Codes", count)
    
    # Recent activity
    st.subheader("🕒 Recent Pipeline Runs")

    # Get available environments
    environments_query = """
    SELECT DISTINCT env_sc.common_cd as environment
    FROM pipeline.pipeline_environment pe
    JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
    ORDER BY env_sc.common_cd;
    """
    environments_df = execute_query(environments_query)

    # Create dropdown for environment selection
    environment_options = ['All'] + environments_df['environment'].tolist()
    selected_environment = st.selectbox(
        "Select Environment:",
        options=environment_options,
        index=0  # Default to 'All'
    )

    # Build the WHERE clause based on selection
    environment_filter = ""
    if selected_environment != 'All':
        environment_filter = f"AND env_sc.common_cd = '{selected_environment}'"

    recent_runs = execute_query(f"""
    SELECT 
        f.pipeline_name, 
        env_sc.common_cd as environment,                                
        sc.common_cd as status,                                 
        cw_detail.detail_data as cloudwatch_url,
        count_detail.detail_data AS total_processed_count,
        fr.start_dt, 
        fr.end_dt 
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
    {environment_filter}
    ORDER BY 
        CASE 
            WHEN UPPER(sc.code_description) LIKE '%FAIL%' OR UPPER(sc.code_description) LIKE '%ERROR%' THEN 1
            WHEN UPPER(sc.code_description) LIKE '%RUNNING%' OR UPPER(sc.code_description) LIKE '%PROGRESS%' OR UPPER(sc.code_description) LIKE '%ACTIVE%' THEN 2
            WHEN UPPER(sc.code_description) LIKE '%COMPLETE%' OR UPPER(sc.code_description) LIKE '%SUCCESS%' OR UPPER(sc.code_description) LIKE '%FINISH%' THEN 3
            ELSE 2
        END,
        fr.start_dt DESC
    LIMIT 60;
    """)

    if not recent_runs.empty:
        st.dataframe(
            recent_runs,
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
    else:
        st.info("No recent pipeline runs found.")