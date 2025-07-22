# visualizations.py
"""
Visualizations and analytics page
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pandas as pd
from database_utils import execute_query

def visualizations_page():
    """Visualizations and analytics dashboard"""
    st.header("📈 Pipeline Analytics & Visualizations")
    
    # Pipeline Performance Overview
    st.subheader("📊 Pipeline Performance Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pipeline Success Rate by Type
        success_by_type = execute_query("""
            SELECT 
                f.pipeline_type_cd,
                COUNT(*) as total_runs,
                COUNT(CASE WHEN fr.status_cd = 'COMPLETED' THEN 1 END) as successful_runs,
                ROUND(
                    COUNT(CASE WHEN fr.status_cd = 'COMPLETED' THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(*), 0), 1
                ) as success_rate
            FROM pipeline.pipeline_run fr
            JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
            WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
                AND fr.status_cd IN ('COMPLETED', 'FAILED')
            GROUP BY f.pipeline_type_cd
            ORDER BY success_rate DESC;
        """)
        
        if not success_by_type.empty:
            fig = px.bar(
                success_by_type, 
                x='pipeline_type_cd', 
                y='success_rate',
                title='Success Rate by Pipeline Type (30 Days)',
                labels={'success_rate': 'Success Rate (%)', 'pipeline_type_cd': 'Pipeline Type'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for pipeline success rates")
    
    with col2:
        # Pipeline Runs by Environment
        runs_by_env = execute_query("""
            SELECT 
                env_sc.common_cd as environment,
                COUNT(*) as run_count
            FROM pipeline.pipeline_run fr
            JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
            JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
            WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY env_sc.common_cd
            ORDER BY run_count DESC;
        """)
        
        if not runs_by_env.empty:
            fig = px.pie(
                runs_by_env, 
                values='run_count', 
                names='environment',
                title='Pipeline Runs by Environment (30 Days)'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for runs by environment")
    
    # Time Series Analysis
    st.subheader("📈 Time Series Analysis")
    
    # Daily pipeline runs trend
    daily_runs = execute_query("""
        SELECT 
            DATE(fr.start_dt) as run_date,
            COUNT(*) as total_runs,
            COUNT(CASE WHEN fr.status_cd = 'COMPLETED' THEN 1 END) as successful_runs,
            COUNT(CASE WHEN fr.status_cd = 'FAILED' THEN 1 END) as failed_runs
        FROM pipeline.pipeline_run fr
        WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(fr.start_dt)
        ORDER BY run_date;
    """)
    
    if not daily_runs.empty:
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=daily_runs['run_date'],
            y=daily_runs['total_runs'],
            mode='lines+markers',
            name='Total Runs',
            line=dict(color='blue')
        ))
        
        fig.add_trace(go.Scatter(
            x=daily_runs['run_date'],
            y=daily_runs['successful_runs'],
            mode='lines+markers',
            name='Successful Runs',
            line=dict(color='green')
        ))
        
        fig.add_trace(go.Scatter(
            x=daily_runs['run_date'],
            y=daily_runs['failed_runs'],
            mode='lines+markers',
            name='Failed Runs',
            line=dict(color='red')
        ))
        
        fig.update_layout(
            title='Daily Pipeline Runs Trend (30 Days)',
            xaxis_title='Date',
            yaxis_title='Number of Runs',
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for daily runs trend")
    
    # Pipeline Execution Duration Analysis
    st.subheader("⏱️ Pipeline Execution Duration Analysis")
    
    duration_data = execute_query("""
        SELECT 
            f.pipeline_name,
            f.pipeline_type_cd,
            EXTRACT(EPOCH FROM (fr.end_dt - fr.start_dt))/60 as duration_minutes
        FROM pipeline.pipeline_run fr
        JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
        WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
            AND fr.end_dt IS NOT NULL
            AND fr.status_cd = 'COMPLETED'
        ORDER BY duration_minutes DESC;
    """)
    
    if not duration_data.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # Average duration by pipeline type
            avg_duration = duration_data.groupby('pipeline_type_cd')['duration_minutes'].mean().reset_index()
            avg_duration['duration_minutes'] = avg_duration['duration_minutes'].round(2)
            
            fig = px.bar(
                avg_duration,
                x='pipeline_type_cd',
                y='duration_minutes',
                title='Average Execution Duration by Pipeline Type',
                labels={'duration_minutes': 'Duration (Minutes)', 'pipeline_type_cd': 'Pipeline Type'}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Top 10 longest running pipelines
            top_long_runs = duration_data.nlargest(10, 'duration_minutes')
            
            fig = px.bar(
                top_long_runs,
                x='duration_minutes',
                y='pipeline_name',
                orientation='h',
                title='Top 10 Longest Running Pipelines (30 Days)',
                labels={'duration_minutes': 'Duration (Minutes)', 'pipeline_name': 'Pipeline Name'}
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No duration data available")
    
    # Processing Volume Analysis
    st.subheader("📊 Processing Volume Analysis")
    
    volume_data = execute_query("""
        SELECT 
            f.pipeline_name,
            f.pipeline_type_cd,
            DATE(fr.start_dt) as run_date,
            CAST(REPLACE(prd.detail_data, ',', '') AS INTEGER) as processed_count
        FROM pipeline.pipeline_run fr
        JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
        JOIN pipeline.pipeline_run_details prd ON fr.pipeline_run_id = prd.pipeline_run_id
        JOIN admin.system_codes sc ON prd.run_detail_type_cd = sc.code_id
        WHERE sc.common_cd = 'TOTAL_PROCESSED_COUNT'
            AND sc.code_type_cd = 'PIPELINE_RUN_DETAIL_TYPE'
            AND fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
            AND prd.detail_data ~ '^[0-9,]+$'  -- Only numeric values
        ORDER BY run_date DESC;
    """)
    
    if not volume_data.empty:
        # Daily processing volume trend
        daily_volume = volume_data.groupby('run_date')['processed_count'].sum().reset_index()
        
        fig = px.line(
            daily_volume,
            x='run_date',
            y='processed_count',
            title='Daily Processing Volume Trend (30 Days)',
            labels={'processed_count': 'Total Records Processed', 'run_date': 'Date'}
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Volume by pipeline type
        type_volume = volume_data.groupby('pipeline_type_cd')['processed_count'].sum().reset_index()
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(
                type_volume,
                values='processed_count',
                names='pipeline_type_cd',
                title='Processing Volume by Pipeline Type (30 Days)'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Top processing pipelines
            top_processors = volume_data.groupby('pipeline_name')['processed_count'].sum().reset_index()
            top_processors = top_processors.nlargest(10, 'processed_count')
            
            fig = px.bar(
                top_processors,
                x='processed_count',
                y='pipeline_name',
                orientation='h',
                title='Top 10 Processing Pipelines by Volume (30 Days)',
                labels={'processed_count': 'Total Records Processed', 'pipeline_name': 'Pipeline Name'}
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No processing volume data available")
    
    # Raw Data Tables
    st.subheader("📋 Raw Data")
    
    tab1, tab2, tab3 = st.tabs(["Recent Runs Summary", "Failure Analysis", "Performance Metrics"])
    
    with tab1:
        recent_summary = execute_query("""
            SELECT 
                f.pipeline_name,
                f.pipeline_type_cd,
                env_sc.common_cd as environment,
                fr.status_cd as status,
                fr.start_dt,
                fr.end_dt,
                CASE 
                    WHEN fr.end_dt IS NOT NULL 
                    THEN EXTRACT(EPOCH FROM (fr.end_dt - fr.start_dt))/60 
                    ELSE NULL 
                END as duration_minutes
            FROM pipeline.pipeline_run fr
            JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
            JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
            JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
            WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY fr.start_dt DESC
            LIMIT 50;
        """)
        
        if not recent_summary.empty:
            st.dataframe(recent_summary, use_container_width=True)
        else:
            st.info("No recent runs found")
    
    with tab2:
        failure_analysis = execute_query("""
            SELECT 
                f.pipeline_name,
                f.pipeline_type_cd,
                env_sc.common_cd as environment,
                fr.start_dt,
                fr.description as failure_reason,
                EXTRACT(EPOCH FROM (COALESCE(fr.end_dt, fr.start_dt) - fr.start_dt))/60 as duration_minutes
            FROM pipeline.pipeline_run fr
            JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
            JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
            JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
            WHERE fr.status_cd = 'FAILED'
                AND fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY fr.start_dt DESC
            LIMIT 50;
        """)
        
        if not failure_analysis.empty:
            st.dataframe(failure_analysis, use_container_width=True)
            
            # Failure summary stats
            st.subheader("Failure Summary")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_failures = len(failure_analysis)
                st.metric("Total Failures (30 days)", total_failures)
            
            with col2:
                if not failure_analysis.empty:
                    most_failed_pipeline = failure_analysis['pipeline_name'].value_counts().index[0]
                    failure_count = failure_analysis['pipeline_name'].value_counts().iloc[0]
                    st.metric("Most Failed Pipeline", f"{most_failed_pipeline} ({failure_count})")
            
            with col3:
                if not failure_analysis.empty:
                    most_failed_env = failure_analysis['environment'].value_counts().index[0]
                    env_failure_count = failure_analysis['environment'].value_counts().iloc[0]
                    st.metric("Most Failed Environment", f"{most_failed_env} ({env_failure_count})")
        else:
            st.info("No failures found in the last 30 days")
    
    with tab3:
        performance_metrics = execute_query("""
            SELECT 
                f.pipeline_name,
                f.pipeline_type_cd,
                COUNT(*) as total_runs,
                COUNT(CASE WHEN fr.status_cd = 'COMPLETED' THEN 1 END) as successful_runs,
                COUNT(CASE WHEN fr.status_cd = 'FAILED' THEN 1 END) as failed_runs,
                ROUND(
                    COUNT(CASE WHEN fr.status_cd = 'COMPLETED' THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(*), 0), 1
                ) as success_rate,
                ROUND(AVG(
                    CASE WHEN fr.end_dt IS NOT NULL 
                    THEN EXTRACT(EPOCH FROM (fr.end_dt - fr.start_dt))/60 
                    ELSE NULL END
                ), 2) as avg_duration_minutes,
                MIN(fr.start_dt) as first_run,
                MAX(fr.start_dt) as last_run
            FROM pipeline.pipeline_run fr
            JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
            WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY f.pipeline_id, f.pipeline_name, f.pipeline_type_cd
            ORDER BY total_runs DESC;
        """)
        
        if not performance_metrics.empty:
            st.dataframe(performance_metrics, use_container_width=True)
            
            # Performance insights
            st.subheader("Performance Insights")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Best performing pipelines (highest success rate)
                best_performers = performance_metrics[performance_metrics['total_runs'] >= 5].nlargest(5, 'success_rate')
                if not best_performers.empty:
                    st.write("**Top 5 Best Performing Pipelines (5+ runs):**")
                    for _, row in best_performers.iterrows():
                        st.write(f"• {row['pipeline_name']}: {row['success_rate']}% success rate")
            
            with col2:
                # Fastest pipelines (lowest average duration)
                fastest_pipelines = performance_metrics[performance_metrics['avg_duration_minutes'].notna()].nsmallest(5, 'avg_duration_minutes')
                if not fastest_pipelines.empty:
                    st.write("**Top 5 Fastest Pipelines:**")
                    for _, row in fastest_pipelines.iterrows():
                        st.write(f"• {row['pipeline_name']}: {row['avg_duration_minutes']} min avg")
        else:
            st.info("No performance metrics available")