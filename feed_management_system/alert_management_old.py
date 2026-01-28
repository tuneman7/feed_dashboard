# alert_management.py
"""
Alert Management page
- Create / edit alert definitions for a pipeline+environment
- Type-specific config editors (Cadence, Data Threshold, Processing Time)
"""
from typing import Any, Dict, List, Optional
import datetime as dt

import pandas as pd
import streamlit as st

from database_utils import execute_query


# -----------------------------
# Helpers: lookups & utilities
# -----------------------------
@st.cache_data(ttl=60)
def get_system_codes_map(code_types: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Return {code_type_cd: DataFrame[code_id, common_cd, code_description, sort_order]}
    """
    in_list = "', '".join(code_types)
    q = f"""
        SELECT code_id, common_cd, code_type_cd, code_description, sort_order
        FROM admin.system_codes
        WHERE code_type_cd IN ('{in_list}')
          AND is_active = true
        ORDER BY code_type_cd, sort_order, common_cd;
    """
    df = execute_query(q)
    out: Dict[str, pd.DataFrame] = {}
    if df is not None and not df.empty:
        for ct in code_types:
            out[ct] = df[df["code_type_cd"] == ct].copy()
    else:
        for ct in code_types:
            out[ct] = pd.DataFrame(columns=["code_id", "common_cd", "code_type_cd", "code_description", "sort_order"])
    return out


@st.cache_data(ttl=60)
def get_active_pipelines() -> pd.DataFrame:
    return execute_query(
        """
        SELECT pipeline_id, pipeline_name
        FROM pipeline.pipeline
        WHERE is_active = true
        ORDER BY pipeline_name;
        """
    )


@st.cache_data(ttl=60)
def get_environments_for_pipeline(pipeline_id: int) -> pd.DataFrame:
    # Join environment rows & their readable label via system_codes
    return execute_query(
        f"""
        SELECT pe.environment_id,
               sc.code_id as env_code_id,
               sc.common_cd as environment,
               sc.code_description
        FROM pipeline.pipeline_environment pe
        JOIN admin.system_codes sc ON pe.env_system_cd = sc.code_id
        WHERE pe.pipeline_id = {pipeline_id}
        ORDER BY sc.sort_order, sc.common_cd;
        """
    )


def _codes_to_select(df: pd.DataFrame, label_col: str = "common_cd", value_col: str = "code_id") -> Dict[str, int]:
    """Map label -> id (labels only shown to user, IDs hidden)."""
    if df is None or df.empty:
        return {}
    out: Dict[str, int] = {}
    for _, row in df.iterrows():
        try:
            val = int(row[value_col])
        except Exception:
            continue
        desc = str(row.get("code_description") or "").strip()
        base = str(row.get(label_col) or "").strip()
        label = f"{base} — {desc}".strip(" —")
        out[label] = val
    return out


def _codes_id_to_label(df: pd.DataFrame, label_col: str = "common_cd", value_col: str = "code_id") -> Dict[int, str]:
    """Map id -> label (for rendering human-readable values in tables)."""
    if df is None or df.empty:
        return {}
    out: Dict[int, str] = {}
    for _, row in df.iterrows():
        try:
            key = int(row[value_col])
        except Exception:
            continue
        desc = str(row.get("code_description") or "").strip()
        base = str(row.get(label_col) or "").strip()
        out[key] = f"{base} — {desc}".strip(" —")
    return out


def _codes_id_to_common(df: pd.DataFrame) -> Dict[int, str]:
    """Map id -> common_cd (for business logic)."""
    if df is None or df.empty:
        return {}
    out: Dict[int, str] = {}
    for _, row in df.iterrows():
        try:
            key = int(row["code_id"])
        except Exception:
            continue
        out[key] = str(row.get("common_cd") or "").strip()
    return out


@st.cache_data(ttl=30)
def get_existing_alerts(pipeline_id: int, environment_id: int) -> pd.DataFrame:
    q = f"""
        SELECT ad.alert_definition_id,
               ad.alert_name,
               ad.alert_description,
               ad.is_enabled,
               ad.recipient_list,
               ad.pipeline_id,
               ad.environment_id,
               ad.alert_type_cd,
               ad.severity_cd,
               ad.notification_type_cd
        FROM pipeline.alert_definition ad
        WHERE ad.pipeline_id = {pipeline_id}
          AND ad.environment_id = {environment_id}
        ORDER BY ad.alert_name;
    """
    return execute_query(q)


def upsert_alert_definition(payload: Dict[str, Any]) -> Optional[int]:
    """
    Insert or update alert_definition, then return alert_definition_id.

    Two-step approach to guarantee COMMIT across helper implementations:
      1) INSERT ... ON CONFLICT DO UPDATE (fetch=False) -> ensures commit in many helpers
      2) SELECT alert_definition_id by natural key (unique constraint)
    """
    insert_sql = """
        INSERT INTO pipeline.alert_definition
            (pipeline_id, environment_id, alert_type_cd, alert_name, alert_description,
             severity_cd, notification_type_cd, recipient_list, is_enabled, created_by, updated_by)
        VALUES (%(pipeline_id)s, %(environment_id)s, %(alert_type_cd)s, %(alert_name)s, %(alert_description)s,
                %(severity_cd)s, %(notification_type_cd)s, %(recipient_list)s, %(is_enabled)s, %(user)s, %(user)s)
        ON CONFLICT (pipeline_id, environment_id, alert_type_cd, alert_name)
        DO UPDATE SET
            alert_description = EXCLUDED.alert_description,
            severity_cd = EXCLUDED.severity_cd,
            notification_type_cd = EXCLUDED.notification_type_cd,
            recipient_list = EXCLUDED.recipient_list,
            is_enabled = EXCLUDED.is_enabled,
            updated_at = CURRENT_TIMESTAMP,
            updated_by = EXCLUDED.updated_by;
    """
    # Step 1: perform write (commit via fetch=False pattern)
    execute_query(insert_sql, payload, fetch=False)

    # Step 2: read back id by unique key
    select_sql = """
        SELECT alert_definition_id
        FROM pipeline.alert_definition
        WHERE pipeline_id = %(pipeline_id)s
          AND environment_id = %(environment_id)s
          AND alert_type_cd = %(alert_type_cd)s
          AND alert_name = %(alert_name)s
        LIMIT 1;
    """
    df = execute_query(select_sql, payload)
    if df is not None and not df.empty:
        try:
            return int(df.iloc[0, 0])
        except Exception:
            return None
    return None


def delete_alert_definition(alert_definition_id: int) -> None:
    """Legacy single-table delete (kept for compatibility if you still call it elsewhere)."""
    execute_query(
        "DELETE FROM pipeline.alert_definition WHERE alert_definition_id = %s;",
        (alert_definition_id,),
        fetch=False,
    )


def delete_alert_cascade(alert_definition_id: int) -> None:
    """
    Delete an alert definition and all related instance/config rows.
    Order is explicit to avoid FK issues if cascades aren't declared.
    Executed as one multi-statement call so it commits atomically via execute_query(fetch=False).
    """
    sql = """
    -- Remove alert instances
    DELETE FROM pipeline.alert_instance
     WHERE alert_definition_id = %(adid)s;

    -- Remove per-type configs
    DELETE FROM pipeline.data_threshold_config
     WHERE alert_definition_id = %(adid)s;

    DELETE FROM pipeline.cadence_alert_config
     WHERE alert_definition_id = %(adid)s;

    DELETE FROM pipeline.processing_time_config
     WHERE alert_definition_id = %(adid)s;

    -- Finally remove definition
    DELETE FROM pipeline.alert_definition
     WHERE alert_definition_id = %(adid)s;
    """
    execute_query(sql, {"adid": alert_definition_id}, fetch=False)


# ---------- Cadence config ----------
def upsert_cadence_config(alert_definition_id: int, payload: Dict[str, Any]) -> None:
    q = """
        INSERT INTO pipeline.cadence_alert_config
            (alert_definition_id, cadence_type_cd, lookback_period, lookback_time_value, lookback_time_unit_cd,
             deviation_threshold, expected_completion_time, expected_day_of_week, expected_day_of_month,
             tolerance_minutes, cron_expression, created_at, updated_at)
        VALUES (%(adid)s, %(cadence_type_cd)s, %(lookback_period)s, %(lookback_time_value)s, %(lookback_time_unit_cd)s,
                %(deviation_threshold)s, %(expected_completion_time)s, %(expected_day_of_week)s, %(expected_day_of_month)s,
                %(tolerance_minutes)s, %(cron_expression)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (alert_definition_id)
        DO UPDATE SET
            cadence_type_cd = EXCLUDED.cadence_type_cd,
            lookback_period = EXCLUDED.lookback_period,
            lookback_time_value = EXCLUDED.lookback_time_value,
            lookback_time_unit_cd = EXCLUDED.lookback_time_unit_cd,
            deviation_threshold = EXCLUDED.deviation_threshold,
            expected_completion_time = EXCLUDED.expected_completion_time,
            expected_day_of_week = EXCLUDED.expected_day_of_week,
            expected_day_of_month = EXCLUDED.expected_day_of_month,
            tolerance_minutes = EXCLUDED.tolerance_minutes,
            cron_expression = EXCLUDED.cron_expression,
            updated_at = CURRENT_TIMESTAMP;
    """
    params = {"adid": alert_definition_id, **payload}
    execute_query(q, params, fetch=False)


# ---------- Data threshold config ----------
def upsert_threshold_config(alert_definition_id: int, payload: Dict[str, Any]) -> None:
    """
    UPSERT by (alert_definition_id, threshold_name) so users can manage multiple thresholds per alert.
    """
    q = """
        INSERT INTO pipeline.data_threshold_config
            (alert_definition_id, threshold_name, min_value, max_value, expected_value, deviation_percent,
             comparison_operator, use_historical_baseline, historical_lookback_runs, value_source, value_source_key,
             created_at, updated_at)
        VALUES (%(adid)s, %(threshold_name)s, %(min_value)s, %(max_value)s, %(expected_value)s, %(deviation_percent)s,
                %(comparison_operator)s, %(use_historical_baseline)s, %(historical_lookback_runs)s,
                %(value_source)s, %(value_source_key)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (alert_definition_id, threshold_name)
        DO UPDATE SET
            min_value = EXCLUDED.min_value,
            max_value = EXCLUDED.max_value,
            expected_value = EXCLUDED.expected_value,
            deviation_percent = EXCLUDED.deviation_percent,
            comparison_operator = EXCLUDED.comparison_operator,
            use_historical_baseline = EXCLUDED.use_historical_baseline,
            historical_lookback_runs = EXCLUDED.historical_lookback_runs,
            value_source = EXCLUDED.value_source,
            value_source_key = EXCLUDED.value_source_key,
            updated_at = CURRENT_TIMESTAMP;
    """
    params = {"adid": alert_definition_id, **payload}
    execute_query(q, params, fetch=False)


# ---------- Processing time config ----------
def upsert_processing_config(alert_definition_id: int, payload: Dict[str, Any]) -> None:
    q = """
        INSERT INTO pipeline.processing_time_config
            (alert_definition_id, use_historical_baseline, historical_lookback_runs, historical_lookback_days,
             max_duration_minutes, deviation_multiplier, deviation_percent, min_duration_minutes,
             created_at, updated_at)
        VALUES (%(adid)s, %(use_historical_baseline)s, %(historical_lookback_runs)s, %(historical_lookback_days)s,
                %(max_duration_minutes)s, %(deviation_multiplier)s, %(deviation_percent)s, %(min_duration_minutes)s,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (alert_definition_id)
        DO UPDATE SET
            use_historical_baseline = EXCLUDED.use_historical_baseline,
            historical_lookback_runs = EXCLUDED.historical_lookback_runs,
            historical_lookback_days = EXCLUDED.historical_lookback_days,
            max_duration_minutes = EXCLUDED.max_duration_minutes,
            deviation_multiplier = EXCLUDED.deviation_multiplier,
            deviation_percent = EXCLUDED.deviation_percent,
            min_duration_minutes = EXCLUDED.min_duration_minutes,
            updated_at = CURRENT_TIMESTAMP;
    """
    params = {"adid": alert_definition_id, **payload}
    execute_query(q, params, fetch=False)


# -----------------------------
# Main Page
# -----------------------------
def alert_management_page():
    st.header("🚨 Alert Management")
    st.caption("Define, edit, and configure alerts for specific pipelines & environments.")

    # Load lookups
    code_maps = get_system_codes_map(
        [
            "ALERT_TYPE",
            "ALERT_SEVERITY",
            "ALERT_NOTIFICATION_TYPE",
            "CADENCE_TYPE",
            "TIME_UNIT",
            "PIPELINE_RUN_DETAIL_TYPE",  # for sources
            "ALERT_STATUS",
        ]
    )

    # Reverse maps for rendering / logic
    alert_type_id2label = _codes_id_to_label(code_maps["ALERT_TYPE"])
    severity_id2label = _codes_id_to_label(code_maps["ALERT_SEVERITY"])
    notif_id2label = _codes_id_to_label(code_maps["ALERT_NOTIFICATION_TYPE"])
    alert_type_id2common = _codes_id_to_common(code_maps["ALERT_TYPE"])

    # ---------- Pipeline selector (labels only; IDs hidden) ----------
    pipes = get_active_pipelines()
    if pipes is None or pipes.empty:
        st.info("No active pipelines found.")
        return

    pipe_label_to_id = {str(r.pipeline_name): int(r.pipeline_id) for _, r in pipes.iterrows()}
    pipe_label = st.selectbox("Pipeline", options=list(pipe_label_to_id.keys()))
    pipeline_id = pipe_label_to_id[pipe_label]

    # ---------- Environment selector (labels only; IDs hidden) ----------
    envs = get_environments_for_pipeline(pipeline_id)
    if envs is None or envs.empty:
        st.warning("Selected pipeline has no configured environments.")
        return

    env_label_to_id: Dict[str, int] = {}
    for _, r in envs.iterrows():
        # use key access for robustness
        desc = str(r["code_description"]).strip() if pd.notna(r["code_description"]) else ""
        base = str(r["environment"])
        label = f"{base} — {desc}".strip(" —")
        env_label_to_id[label] = int(r["environment_id"])

    env_label = st.selectbox("Environment", options=list(env_label_to_id.keys()))
    environment_id = env_label_to_id[env_label]

    st.markdown("---")

    # ---------- Existing alerts table + select for edit ----------
    existing = get_existing_alerts(pipeline_id, environment_id)
    selected_alert_id: Optional[int] = None

    with st.expander("Existing Alerts", expanded=True):
        if existing is not None and not existing.empty:
            # Render human-readable columns (hide code IDs)
            display = existing.copy()
            display["Type"] = display["alert_type_cd"].map(alert_type_id2label).fillna("")
            display["Severity"] = display["severity_cd"].map(severity_id2label).fillna("")
            display["Notification"] = display["notification_type_cd"].map(notif_id2label).fillna("")
            display = display[
                [
                    "alert_name",
                    "alert_description",
                    "is_enabled",
                    "recipient_list",
                    "Type",
                    "Severity",
                    "Notification",
                ]
            ]
            st.dataframe(display, hide_index=True, use_container_width=True)

            # Selection label: show clean title; persist ID via hidden map
            select_map = {
                f"{r.alert_name} — [{alert_type_id2label.get(int(r.alert_type_cd), 'Unknown')}]": int(
                    r.alert_definition_id
                )
                for _, r in existing.iterrows()
            }
            select_label = st.selectbox(
                "Select an alert to edit (optional)",
                options=["(Create New)"] + list(select_map.keys()),
                index=0,
            )
            if select_label != "(Create New)":
                selected_alert_id = select_map[select_label]
                # remember its type id for conditional tabs
                row = existing[existing["alert_definition_id"] == selected_alert_id].iloc[0]
                st.session_state["current_alert_type_cd"] = int(row["alert_type_cd"])

                # ---- Danger zone: cascade delete ----
                st.divider()
                col_d1, col_d2 = st.columns([3, 1])
                with col_d1:
                    confirm_delete = st.checkbox(
                        "I understand this will permanently delete the alert definition, all its alert instances, and all related config records."
                    )
                with col_d2:
                    if st.button("Delete Selected Alert", type="primary", disabled=not confirm_delete):
                        delete_alert_cascade(selected_alert_id)
                        st.success("Alert and all related records deleted.")
                        # clear session + refresh
                        st.session_state.pop("current_adid", None)
                        st.session_state.pop("current_alert_type_cd", None)
                        st.cache_data.clear()
                        st.rerun()
        else:
            st.caption("No alerts yet for this pipeline & environment.")

    st.markdown("---")

    # ---------- Create/Edit form ----------
    with st.form("alert_form", clear_on_submit=False, border=True):
        st.subheader("Alert Definition")

        # Pre-fill if editing
        editing_row = None
        if selected_alert_id and existing is not None and not existing.empty:
            editing_row = existing[existing["alert_definition_id"] == selected_alert_id]
            editing_row = editing_row.iloc[0] if not editing_row.empty else None

        alert_name = st.text_input("Alert Name", value=(editing_row["alert_name"] if editing_row is not None else ""))
        alert_desc = st.text_area(
            "Alert Description", value=(editing_row["alert_description"] if editing_row is not None else "")
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            alert_type_opt = _codes_to_select(code_maps["ALERT_TYPE"])
            alert_type_label = st.selectbox("Alert Type", options=list(alert_type_opt.keys()))
        with col2:
            severity_opt = _codes_to_select(code_maps["ALERT_SEVERITY"])
            severity_label = st.selectbox("Severity", options=list(severity_opt.keys()))
        with col3:
            notif_opt = _codes_to_select(code_maps["ALERT_NOTIFICATION_TYPE"])
            notification_type_label = st.selectbox("Notification Type", options=list(notif_opt.keys()))
        with col4:
            is_enabled = st.toggle(
                "Enabled", value=(bool(editing_row["is_enabled"]) if editing_row is not None else True)
            )

        recipient_list = st.text_input(
            "Recipients (comma-separated emails or Slack channels)",
            value=(editing_row["recipient_list"] if editing_row is not None else ""),
        )

        submitted = st.form_submit_button("💾 Save / Update Alert")
        if submitted:
            if not alert_name.strip():
                st.error("Alert name is required.")
            else:
                payload = {
                    "pipeline_id": pipeline_id,
                    "environment_id": environment_id,
                    "alert_type_cd": alert_type_opt[alert_type_label],
                    "alert_name": alert_name.strip(),
                    "alert_description": alert_desc.strip(),
                    "severity_cd": severity_opt[severity_label],
                    "notification_type_cd": notif_opt[notification_type_label],
                    "recipient_list": recipient_list.strip(),  # NOT NULL in schema
                    "is_enabled": is_enabled,
                    "user": st.session_state.get("user", {}).get("email", "system"),
                }
                adid = upsert_alert_definition(payload)
                if adid:
                    st.success("Alert saved. Configure details below (if required).")
                    st.session_state["current_adid"] = adid
                    st.session_state["current_alert_type_cd"] = payload["alert_type_cd"]
                    st.cache_data.clear()
                    st.rerun()  # force re-query & show new row immediately
                else:
                    st.error("Failed to save alert definition.")

    # ---------- Conditional detail editors ----------
    adid = st.session_state.get("current_adid", selected_alert_id)

    # Resolve current alert type id (prefer session; fall back to the 'existing' df)
    current_type_cd = st.session_state.get("current_alert_type_cd")
    if current_type_cd is None and adid and existing is not None and not existing.empty:
        m = existing[existing["alert_definition_id"] == adid]
        if not m.empty:
            current_type_cd = int(m.iloc[0]["alert_type_cd"])

    if not adid:
        st.info("Save an alert first to configure any additional details.")
        return

    # Map id -> common_cd to drive which editors are visible
    current_type_common = (
        alert_type_id2common.get(int(current_type_cd), "").upper() if current_type_cd is not None else ""
    )

    # Finalized alert types:
    # COMPLETION_ALERT, CADENCE_ALERT, DATA_THRESHOLD, HARD_FAILURE, PROCESSING_TIME
    show_cadence = current_type_common == "CADENCE_ALERT"
    show_threshold = current_type_common == "DATA_THRESHOLD"
    show_processing = current_type_common == "PROCESSING_TIME"

    if not any([show_cadence, show_threshold, show_processing]):
        st.success("This alert type does not require additional configuration.")
        return

    st.markdown("### Configure Alert Details")

    # Build only the tabs we need, in a stable order
    tab_names = []
    if show_cadence:
        tab_names.append("Cadence")
    if show_threshold:
        tab_names.append("Data Threshold")
    if show_processing:
        tab_names.append("Processing Time")
    tabs = st.tabs(tab_names)
    ti = 0

    # ------- Cadence (for CADENCE_ALERT) -------
    if show_cadence:
        with tabs[ti]:
            st.caption("Use for schedule/cadence-based alerts.")
            cad_opt = _codes_to_select(code_maps["CADENCE_TYPE"])
            time_unit_opt = _codes_to_select(code_maps["TIME_UNIT"])

            with st.form("cadence_form", border=True):
                colA, colB, colC = st.columns(3)
                with colA:
                    cadence_type = st.selectbox("Cadence Type", list(cad_opt.keys()))
                with colB:
                    lookback_period = st.number_input("Lookback Period (# runs)", min_value=0, value=0, step=1)
                with colC:
                    deviation_threshold = st.number_input("Deviation Threshold (%)", min_value=0.0, value=0.0, step=0.5)

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    lookback_time_value = st.number_input("Lookback Time Value", min_value=0, value=0, step=1)
                with col2:
                    lookback_time_unit = st.selectbox("Lookback Time Unit", list(time_unit_opt.keys()))
                with col3:
                    # Use a safe default time; None can blank the app in some Streamlit versions
                    expected_completion_time = st.time_input("Expected Completion Time (UTC)", value=dt.time(0, 0))
                with col4:
                    tolerance_minutes = st.number_input("Tolerance Minutes", min_value=0, value=0, step=5)

                col5, col6 = st.columns(2)
                with col5:
                    expected_dow = st.selectbox("Expected Day of Week (0=Sun)", options=[None, 0, 1, 2, 3, 4, 5, 6], index=0)
                with col6:
                    expected_dom = st.selectbox("Expected Day of Month", options=[None] + list(range(1, 32)), index=0)

                cron_expr = st.text_input("Cron Expression (optional)")

                if st.form_submit_button("💾 Save Cadence Config"):
                    payload = {
                        "cadence_type_cd": cad_opt[cadence_type],
                        "lookback_period": None if lookback_period == 0 else lookback_period,
                        "lookback_time_value": None if lookback_time_value == 0 else lookback_time_value,
                        "lookback_time_unit_cd": None if lookback_time_value == 0 else time_unit_opt[lookback_time_unit],
                        "deviation_threshold": None if deviation_threshold == 0 else deviation_threshold,
                        "expected_completion_time": expected_completion_time,
                        "expected_day_of_week": expected_dow,
                        "expected_day_of_month": expected_dom,
                        "tolerance_minutes": None if tolerance_minutes == 0 else tolerance_minutes,
                        "cron_expression": cron_expr or None,
                    }
                    upsert_cadence_config(adid, payload)
                    st.success("Cadence configuration saved.")
        ti += 1

    # ------- Data Threshold (for DATA_THRESHOLD) -------
    if show_threshold:
        with tabs[ti]:
            st.caption("Define one or more value thresholds to evaluate.")
            with st.form("threshold_form", border=True):
                threshold_name = st.text_input("Threshold Name (e.g., row_count, error_rate)")
                col1, col2, col3 = st.columns(3)
                with col1:
                    min_value = st.number_input("Min Value", value=0.0, step=1.0, format="%.4f")
                with col2:
                    max_value = st.number_input("Max Value", value=0.0, step=1.0, format="%.4f")
                with col3:
                    expected_value = st.number_input("Expected Value", value=0.0, step=1.0, format="%.4f")

                col4, col5 = st.columns(2)
                with col4:
                    deviation_percent = st.number_input("Allowed Deviation (%)", value=0.0, step=0.5)
                with col5:
                    comparison_operator = st.selectbox(
                        "Comparison Operator", ["", "GT", "LT", "GTE", "LTE", "EQ", "BETWEEN", "DEVIATION"]
                    )

                st.divider()
                st.caption("Value Source")
                col6, col7, col8 = st.columns(3)
                with col6:
                    value_source = st.selectbox("Source", ["RUN_DETAIL", "CUSTOM_QUERY", "EXTERNAL_API"])
                with col7:
                    rd_map = _codes_to_select(code_maps["PIPELINE_RUN_DETAIL_TYPE"])
                    run_detail_type = st.selectbox("Run Detail Type (if RUN_DETAIL)", [""] + list(rd_map.keys()))
                with col8:
                    use_hist = st.toggle("Use Historical Baseline", value=False)

                hist_lookback = st.number_input("Historical Lookback Runs", min_value=0, value=0, step=1)

                if st.form_submit_button("➕ Add / Update Threshold"):
                    if not threshold_name.strip():
                        st.error("Threshold Name is required.")
                    else:
                        payload = {
                            "threshold_name": threshold_name.strip(),
                            "min_value": None if min_value == 0 else min_value,
                            "max_value": None if max_value == 0 else max_value,
                            "expected_value": None if expected_value == 0 else expected_value,
                            "deviation_percent": None if deviation_percent == 0 else deviation_percent,
                            "comparison_operator": (comparison_operator or None),
                            "use_historical_baseline": bool(use_hist),
                            "historical_lookback_runs": None if hist_lookback == 0 else hist_lookback,
                            "value_source": value_source,
                            "value_source_key": (
                                rd_map.get(run_detail_type) if (value_source == "RUN_DETAIL" and run_detail_type) else None
                            ),
                        }
                        upsert_threshold_config(adid, payload)
                        st.success("Threshold configuration upserted.")
        ti += 1

    # ------- Processing Time (for PROCESSING_TIME) -------
    if show_processing:
        with tabs[ti]:
            st.caption("Alert when processing time deviates from baseline or exceeds a fixed threshold.")
            with st.form("processing_form", border=True):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    use_hist = st.toggle("Use Historical Baseline", value=True)
                with col2:
                    hist_runs = st.number_input("Historical Lookback Runs", min_value=0, value=20, step=1)
                with col3:
                    hist_days = st.number_input("Historical Lookback Days", min_value=0, value=0, step=1)
                with col4:
                    min_duration = st.number_input("Min Duration (minutes)", min_value=0, value=1, step=1)

                col5, col6, col7 = st.columns(3)
                with col5:
                    max_duration = st.number_input("Max Duration (minutes)", min_value=0, value=0, step=1)
                with col6:
                    dev_mult = st.number_input("Deviation Multiplier (e.g. 1.5)", min_value=0.0, value=0.0, step=0.1)
                with col7:
                    dev_pct = st.number_input("Deviation Percent (e.g. 50)", min_value=0.0, value=0.0, step=0.5)

                if st.form_submit_button("💾 Save Processing Time Config"):
                    payload = {
                        "use_historical_baseline": bool(use_hist),
                        "historical_lookback_runs": None if hist_runs == 0 else hist_runs,
                        "historical_lookback_days": None if hist_days == 0 else hist_days,
                        "max_duration_minutes": None if max_duration == 0 else max_duration,
                        "deviation_multiplier": None if dev_mult == 0 else dev_mult,
                        "deviation_percent": None if dev_pct == 0 else dev_pct,
                        "min_duration_minutes": None if min_duration == 0 else min_duration,
                    }
                    upsert_processing_config(adid, payload)
                    st.success("Processing-time configuration saved.")
