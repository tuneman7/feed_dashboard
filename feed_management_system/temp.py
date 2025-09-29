# visualizations.py
"""
Visualizations and analytics page
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from database_utils import execute_query

def visualizations_page():
    """Visualizations and analytics dashboard"""
    st.header("📈 Pipeline Analytics & Visualizations")
    
    # Add filters at the top
    st.subheader("🔍 Filters")
    
    # Get available pipelines and environments for filters
    pipelines_data = execute_query("""
        SELECT DISTINCT f.pipeline_name, f.pipeline_type_cd
        FROM pipeline.pipeline f
        JOIN pipeline.pipeline_run fr ON f.pipeline_id = fr.pipeline_id
        WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
        ORDER BY f.pipeline_name;
    """)
    
    environments_data = execute_query("""
        SELECT DISTINCT env_sc.common_cd as environment
        FROM pipeline.pipeline_run fr
        JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
        JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
        WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
        ORDER BY env_sc.common_cd;
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not pipelines_data.empty:
            selected_pipelines = st.multiselect(
                "Select Pipelines (leave empty for all)",
                options=pipelines_data['pipeline_name'].tolist(),
                default=[]
            )
        else:
            selected_pipelines = []
            st.info("No pipelines available for selection")
    
    with col2:
        if not environments_data.empty:
            selected_environments = st.multiselect(
                "Select Environments (leave empty for all)",
                options=environments_data['environment'].tolist(),
                default=[]
            )
        else:
            selected_environments = []
            st.info("No environments available for selection")
    
    # Build filter conditions for SQL queries
    pipeline_filter = ""
    env_filter = ""
    
    if selected_pipelines:
        pipeline_names_str = "', '".join(selected_pipelines)
        pipeline_filter = f" AND f.pipeline_name IN ('{pipeline_names_str}')"
    
    if selected_environments:
        env_names_str = "', '".join(selected_environments)
        env_filter = f" AND env_sc.common_cd IN ('{env_names_str}')"
    
    # Pipeline Performance Overview
    st.subheader("📊 Pipeline Performance Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pipeline Success Rate by Type
        success_by_type = execute_query(f"""
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
            JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
            JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
            WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
                AND fr.status_cd IN ('COMPLETED', 'FAILED')
                {pipeline_filter}
                {env_filter}
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
        runs_by_env = execute_query(f"""
            SELECT 
                env_sc.common_cd as environment,
                COUNT(*) as run_count
            FROM pipeline.pipeline_run fr
            JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
            JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
            JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
            WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
                {pipeline_filter}
                {env_filter}
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
    
    # Daily pipeline runs trend by environment
    daily_runs = execute_query(f"""
        SELECT 
            DATE(fr.start_dt) as run_date,
            env_sc.common_cd as environment,
            COUNT(*) as total_runs,
            COUNT(CASE WHEN fr.status_cd = 'COMPLETED' THEN 1 END) as successful_runs,
            COUNT(CASE WHEN fr.status_cd = 'FAILED' THEN 1 END) as failed_runs
        FROM pipeline.pipeline_run fr
        JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
        JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
        JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
        WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
            {pipeline_filter}
            {env_filter}
        GROUP BY DATE(fr.start_dt), env_sc.common_cd
        ORDER BY run_date, environment;
    """)
    
    if not daily_runs.empty:
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["Total Runs", "Successful Runs", "Failed Runs"])
        
        # Get color palette for environments
        colors = px.colors.qualitative.Set1 + px.colors.qualitative.Set2
        unique_environments = daily_runs['environment'].unique()
        
        with tab1:
            fig = go.Figure()
            
            for i, env in enumerate(unique_environments):
                env_data = daily_runs[daily_runs['environment'] == env]
                
                fig.add_trace(go.Scatter(
                    x=env_data['run_date'],
                    y=env_data['total_runs'],
                    mode='lines+markers',
                    name=env,
                    line=dict(color=colors[i % len(colors)])
                ))
            
            fig.update_layout(
                title='Daily Total Pipeline Runs by Environment (30 Days)',
                xaxis_title='Date',
                yaxis_title='Number of Runs',
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            fig = go.Figure()
            
            for i, env in enumerate(unique_environments):
                env_data = daily_runs[daily_runs['environment'] == env]
                
                fig.add_trace(go.Scatter(
                    x=env_data['run_date'],
                    y=env_data['successful_runs'],
                    mode='lines+markers',
                    name=env,
                    line=dict(color=colors[i % len(colors)])
                ))
            
            fig.update_layout(
                title='Daily Successful Pipeline Runs by Environment (30 Days)',
                xaxis_title='Date',
                yaxis_title='Number of Successful Runs',
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            fig = go.Figure()
            
            for i, env in enumerate(unique_environments):
                env_data = daily_runs[daily_runs['environment'] == env]
                
                fig.add_trace(go.Scatter(
                    x=env_data['run_date'],
                    y=env_data['failed_runs'],
                    mode='lines+markers',
                    name=env,
                    line=dict(color=colors[i % len(colors)])
                ))
            
            fig.update_layout(
                title='Daily Failed Pipeline Runs by Environment (30 Days)',
                xaxis_title='Date',
                yaxis_title='Number of Failed Runs',
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for daily runs trend")
    
    # Pipeline Execution Duration Analysis
    st.subheader("⏱️ Pipeline Execution Duration Analysis")

    duration_data = execute_query(f"""
        SELECT 
            f.pipeline_name,
            f.pipeline_type_cd,
            EXTRACT(EPOCH FROM (fr.end_dt - fr.start_dt))/60 as duration_minutes
        FROM pipeline.pipeline_run fr
        JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
        JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
        JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
        WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
            AND fr.end_dt IS NOT NULL
            AND fr.status_cd = 'COMPLETED'
            {pipeline_filter}
            {env_filter}
        ORDER BY duration_minutes DESC;
    """)

    if not duration_data.empty:
        # Ensure duration_minutes is numeric and handle any conversion errors
        duration_data['duration_minutes'] = pd.to_numeric(duration_data['duration_minutes'], errors='coerce')
        
        # Remove any rows where duration couldn't be converted to numeric
        duration_data = duration_data.dropna(subset=['duration_minutes'])
        
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
            st.info("No valid duration data available after data cleaning")
    else:
        st.info("No duration data available")

    # Processing Volume Analysis
    st.subheader("📊 Processing Volume Analysis")

    volume_data = execute_query(f"""
        SELECT 
            f.pipeline_name,
            f.pipeline_type_cd,
            env_sc.common_cd as environment,
            DATE(fr.start_dt) as run_date,
            CAST(REPLACE(prd.detail_data, ',', '') AS BIGINT) as processed_count
        FROM pipeline.pipeline_run fr
        JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
        JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
        JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
        JOIN pipeline.pipeline_run_details prd ON fr.pipeline_run_id = prd.pipeline_run_id
        JOIN admin.system_codes sc ON prd.run_detail_type_cd = sc.code_id
        WHERE sc.common_cd = 'TOTAL_PROCESSED_COUNT'
            AND sc.code_type_cd = 'PIPELINE_RUN_DETAIL_TYPE'
            AND fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
            AND prd.detail_data ~ '^[0-9,]+$'  -- Only numeric values
            {pipeline_filter}
            {env_filter}
        ORDER BY run_date DESC;
    """)

    if not volume_data.empty:
        # Ensure processed_count is numeric (additional safety check)
        volume_data['processed_count'] = pd.to_numeric(volume_data['processed_count'], errors='coerce')
        volume_data = volume_data.dropna(subset=['processed_count'])
        
        if not volume_data.empty:
            # Add day of week column
            volume_data['run_date'] = pd.to_datetime(volume_data['run_date'])
            volume_data['day_of_week'] = volume_data['run_date'].dt.day_name()
            
            # Daily processing volume trend by environment - always show multiple lines
            daily_volume_env = volume_data.groupby(['run_date', 'environment', 'day_of_week'])['processed_count'].sum().reset_index()
            
            fig = go.Figure()
            
            # Use a color palette for environments
            colors = px.colors.qualitative.Set1 + px.colors.qualitative.Set2
            
            for i, env in enumerate(daily_volume_env['environment'].unique()):
                env_data = daily_volume_env[daily_volume_env['environment'] == env]
                
                fig.add_trace(go.Scatter(
                    x=env_data['run_date'],
                    y=env_data['processed_count'],
                    mode='lines+markers',
                    name=env,
                    line=dict(color=colors[i % len(colors)]),
                    hovertemplate='<b>%{fullData.name}</b><br>' +
                                'Date: %{x}<br>' +
                                'Day: %{customdata}<br>' +
                                'Records: %{y:,.0f}<extra></extra>',
                    customdata=env_data['day_of_week']
                ))
            
            fig.update_layout(
                title='Daily Processing Volume Trend by Environment (30 Days)',
                xaxis_title='Date',
                yaxis_title='Total Records Processed',
                yaxis_tickformat=',.0f',
                hovermode='x unified'
            )
            
            # Add day of week to x-axis labels
            fig.update_xaxes(
                tickformat='%Y-%m-%d',
                tickmode='linear',
                dtick=86400000.0 * 2  # Show every 2 days to avoid crowding
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
                fig.update_traces(texttemplate='%{label}<br>%{value:,.0f}')  # Format pie chart labels
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
                # Correct method for Plotly Express figures
                fig.update_layout(xaxis_tickformat=',.0f')  # Format x-axis with commas
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No valid processing volume data available after data cleaning")
    else:
        st.info("No processing volume data available")        

    # Time Series by Pipeline
    st.subheader("📈 Records Processed by Pipeline (Time Series)")

    pipeline_timeseries_data = execute_query(f"""
        SELECT 
            f.pipeline_name,
            f.pipeline_type_cd,
            DATE(fr.start_dt) as run_date,
            CAST(REPLACE(prd.detail_data, ',', '') AS BIGINT) as processed_count
        FROM pipeline.pipeline_run fr
        JOIN pipeline.pipeline f ON fr.pipeline_id = f.pipeline_id
        JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
        JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
        JOIN pipeline.pipeline_run_details prd ON fr.pipeline_run_id = prd.pipeline_run_id
        JOIN admin.system_codes sc ON prd.run_detail_type_cd = sc.code_id
        WHERE sc.common_cd = 'TOTAL_PROCESSED_COUNT'
            AND sc.code_type_cd = 'PIPELINE_RUN_DETAIL_TYPE'
            AND fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
            AND prd.detail_data ~ '^[0-9,]+$'  -- Only numeric values
            AND fr.status_cd = 'COMPLETED'  -- Only successful runs
            {pipeline_filter}
            {env_filter}
        ORDER BY f.pipeline_name, run_date;
    """)

    if not pipeline_timeseries_data.empty:
        # Ensure processed_count is numeric and handle any conversion errors
        pipeline_timeseries_data['processed_count'] = pd.to_numeric(pipeline_timeseries_data['processed_count'], errors='coerce')
        pipeline_timeseries_data = pipeline_timeseries_data.dropna(subset=['processed_count'])
        
        # Filter out zero values for log scale (can't take log of 0)
        pipeline_timeseries_data = pipeline_timeseries_data[pipeline_timeseries_data['processed_count'] > 0]
        
        if not pipeline_timeseries_data.empty:
            # Apply log transformation to handle vastly different scales
            pipeline_timeseries_data['log_processed_count'] = np.log10(pipeline_timeseries_data['processed_count'])
            
            # Create the time series line chart with separate lines for each pipeline
            fig = go.Figure()
            
            # Get unique pipelines and add a line for each
            unique_pipelines = pipeline_timeseries_data['pipeline_name'].unique()
            
            # Use a color palette that cycles through colors
            colors = px.colors.qualitative.Set1 + px.colors.qualitative.Set2 + px.colors.qualitative.Pastel1
            
            for i, pipeline in enumerate(unique_pipelines):
                pipeline_data = pipeline_timeseries_data[pipeline_timeseries_data['pipeline_name'] == pipeline]
                
                # Group by date and sum in case there are multiple runs per day
                daily_pipeline_data = pipeline_data.groupby('run_date').agg({
                    'processed_count': 'sum',
                    'log_processed_count': lambda x: np.log10(x.sum() if (x.sum() > 0) else 1)  # Recalculate log for summed values
                }).reset_index()
                
                fig.add_trace(go.Scatter(
                    x=daily_pipeline_data['run_date'],
                    y=daily_pipeline_data['log_processed_count'],
                    mode='lines+markers',
                    name=pipeline,
                    line=dict(color=colors[i % len(colors)]),
                    hovertemplate='<b>%{fullData.name}</b><br>' +
                                'Date: %{x}<br>' +
                                'Records: %{customdata:,.0f}<br>' +
                                'Log₁₀(Records): %{y:.2f}<extra></extra>',
                    customdata=daily_pipeline_data['processed_count']
                ))
            
            fig.update_layout(
                title='Records Processed by Pipeline Over Time (Log Scale)',
                xaxis_title='Date',
                yaxis_title='Log₁₀(Records Processed)',
                hovermode='x unified',
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                ),
                margin=dict(r=150, b=100)  # Add right margin for legend and bottom margin for note
            )
            
            # Add annotation explaining the log scale
            fig.add_annotation(
                text="Note: Y-axis uses log₁₀ scale to handle vastly different processing volumes.<br>" +
                    "Hover over points to see actual record counts.",
                xref="paper", yref="paper",
                x=0, y=-0.25,
                showarrow=False,
                font=dict(size=10, color="gray"),
                align="left"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Add a summary table showing the scale differences
            st.subheader("Pipeline Processing Scale Summary")
            
            scale_summary = pipeline_timeseries_data.groupby('pipeline_name').agg({
                'processed_count': ['min', 'max', 'mean', 'sum']
            }).round(0)
            
            # Flatten column names
            scale_summary.columns = ['Min Records', 'Max Records', 'Avg Records', 'Total Records']
            scale_summary = scale_summary.reset_index()
            
            # Format large numbers with commas
            for col in ['Min Records', 'Max Records', 'Avg Records', 'Total Records']:
                scale_summary[col] = scale_summary[col].apply(lambda x: f"{int(x):,}")
            
            st.dataframe(scale_summary, use_container_width=True)
            
        else:
            st.info("No valid processing data available after filtering for positive values")
    else:
        st.info("No pipeline processing time series data available")

    # Raw Data Tables
    st.subheader("📋 Raw Data")
    
    tab1, tab2, tab3 = st.tabs(["Recent Runs Summary", "Failure Analysis", "Performance Metrics"])
    
    with tab1:
        recent_summary = execute_query(f"""
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
                {pipeline_filter}
                {env_filter}
            ORDER BY fr.start_dt DESC
            LIMIT 50;
        """)
        
        if not recent_summary.empty:
            st.dataframe(recent_summary, use_container_width=True)
        else:
            st.info("No recent runs found")
    
    with tab2:
        failure_analysis = execute_query(f"""
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
                {pipeline_filter}
                {env_filter}
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
        performance_metrics = execute_query(f"""
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
            JOIN pipeline.pipeline_environment pe ON fr.environment_id = pe.environment_id
            JOIN admin.system_codes env_sc ON pe.env_system_cd = env_sc.code_id
            WHERE fr.start_dt >= CURRENT_DATE - INTERVAL '30 days'
                {pipeline_filter}
                {env_filter}
            GROUP BY f.pipeline_id, f.pipeline_name, f.pipeline_type_cd
            ORDER BY total_runs DESC;
        """)
        
        if not performance_metrics.empty:
            # Convert numeric columns to proper data types
            performance_metrics['success_rate'] = pd.to_numeric(performance_metrics['success_rate'], errors='coerce')
            performance_metrics['avg_duration_minutes'] = pd.to_numeric(performance_metrics['avg_duration_minutes'], errors='coerce')
            performance_metrics['total_runs'] = pd.to_numeric(performance_metrics['total_runs'], errors='coerce')
            
            st.dataframe(performance_metrics, use_container_width=True)
            
            # Performance insights
            st.subheader("Performance Insights")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Best performing pipelines (highest success rate)
                # Filter for pipelines with at least 5 runs and non-null success rates
                eligible_performers = performance_metrics[
                    (performance_metrics['total_runs'] >= 5) & 
                    (performance_metrics['success_rate'].notna())
                ]
                
                if not eligible_performers.empty:
                    best_performers = eligible_performers.nlargest(5, 'success_rate')
                    st.write("**Top 5 Best Performing Pipelines (5+ runs):**")
                    for _, row in best_performers.iterrows():
                        success_rate = row['success_rate']
                        if pd.notna(success_rate):
                            st.write(f"• {row['pipeline_name']}: {success_rate}% success rate")
                else:
                    st.write("**Top 5 Best Performing Pipelines (5+ runs):**")
                    st.write("No pipelines with sufficient runs found")
            
            with col2:
                # Fastest pipelines (lowest average duration)
                eligible_fastest = performance_metrics[performance_metrics['avg_duration_minutes'].notna()]
                
                if not eligible_fastest.empty:
                    fastest_pipelines = eligible_fastest.nsmallest(5, 'avg_duration_minutes')
                    st.write("**Top 5 Fastest Pipelines:**")
                    for _, row in fastest_pipelines.iterrows():
                        duration = row['avg_duration_minutes']
                        if pd.notna(duration):
                            st.write(f"• {row['pipeline_name']}: {duration} min avg")
                else:
                    st.write("**Top 5 Fastest Pipelines:**")
                    st.write("No duration data available")
        else:
            st.info("No performance metrics available")