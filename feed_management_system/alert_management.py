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


def _codes_to_select(df: pd.DataFrame, label_col: str = "common_cd", value_col: str = "code_id") -> Dict[str, int]:
    """Map label -> id (labels shown to user, IDs hidden)."""
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


# -----------------------------
# Database operations
# -----------------------------
def upsert_alert_definition(payload: Dict[str, Any]) -> Optional[int]:
    """
    Insert or update alert_definition, then return alert_definition_id.
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
    execute_query(insert_sql, payload, fetch=False)

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


def delete_alert_cascade(alert_definition_id: int) -> None:
    """
    Delete an alert definition and all related instance/config rows.
    """
    sql = """
    DELETE FROM pipeline.alert_instance
     WHERE alert_definition_id = %(adid)s;

    DELETE FROM pipeline.data_threshold_config
     WHERE alert_definition_id = %(adid)s;

    DELETE FROM pipeline.cadence_alert_config
     WHERE alert_definition_id = %(adid)s;

    DELETE FROM pipeline.processing_time_config
     WHERE alert_definition_id = %(adid)s;

    DELETE FROM pipeline.alert_definition
     WHERE alert_definition_id = %(adid)s;
    """
    execute_query(sql, {"adid": alert_definition_id}, fetch=False)


def upsert_cadence_config(alert_definition_id: int, payload: Dict[str, Any]) -> None:
    """Insert or update cadence alert configuration."""
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


def upsert_threshold_config(alert_definition_id: int, payload: Dict[str, Any]) -> None:
    """Insert or update data threshold configuration."""
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


def upsert_processing_config(alert_definition_id: int, payload: Dict[str, Any]) -> None:
    """Insert or update processing time configuration."""
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
# State management
# -----------------------------
def clear_alert_form_state() -> None:
    """Clear all alert form-related session state."""
    keys_to_clear = [
        "af_alert_name",
        "af_alert_desc",
        "af_alert_type_label",
        "af_severity_label",
        "af_notif_label",
        "af_is_enabled",
        "af_recipient_list",
        "af_seed_alert_id",
        "current_adid",
        "current_alert_type_cd",
        "last_selected_alert_id",
        "alert_selector",
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)


def check_context_change(pipeline_id: int, environment_id: int) -> bool:
    """
    Check if pipeline or environment has changed.
    Returns True if context changed (and clears state).
    """
    last_pipeline = st.session_state.get("last_pipeline_id")
    last_environment = st.session_state.get("last_environment_id")
    
    context_changed = (last_pipeline != pipeline_id) or (last_environment != environment_id)
    
    if context_changed:
        # Clear all alert-related state
        clear_alert_form_state()
        # Update tracking
        st.session_state["last_pipeline_id"] = pipeline_id
        st.session_state["last_environment_id"] = environment_id
        return True
    
    return False


def _seed_alert_form_state(
    selected_alert_id: Optional[int],
    existing: Optional[pd.DataFrame],
    alert_type_id2label: Dict[int, str],
    severity_id2label: Dict[int, str],
    notif_id2label: Dict[int, str],
) -> None:
    """
    Seed Streamlit widget state for the create/edit form from the selected alert.
    """
    seed_key = "af_seed_alert_id"
    last = st.session_state.get(seed_key)

    # Create New: clear seeded values once
    if not selected_alert_id:
        if last is not None:
            st.session_state[seed_key] = None
            clear_alert_form_state()
        else:
            if "af_is_enabled" not in st.session_state:
                st.session_state["af_is_enabled"] = True
        return

    # Only reseed when selection changes
    if last == selected_alert_id:
        return
    st.session_state[seed_key] = selected_alert_id

    if existing is None or existing.empty:
        return

    m = existing[existing["alert_definition_id"] == selected_alert_id]
    if m.empty:
        return
    row = m.iloc[0]

    # Seed text fields
    st.session_state["af_alert_name"] = str(row.get("alert_name") or "")
    st.session_state["af_alert_desc"] = str(row.get("alert_description") or "")
    st.session_state["af_is_enabled"] = bool(row.get("is_enabled")) if row.get("is_enabled") is not None else True
    st.session_state["af_recipient_list"] = str(row.get("recipient_list") or "")

    # Seed dropdown labels
    try:
        lbl = alert_type_id2label.get(int(row["alert_type_cd"]))
        if lbl:
            st.session_state["af_alert_type_label"] = lbl
        else:
            st.session_state.pop("af_alert_type_label", None)
    except Exception:
        st.session_state.pop("af_alert_type_label", None)

    try:
        lbl = severity_id2label.get(int(row["severity_cd"]))
        if lbl:
            st.session_state["af_severity_label"] = lbl
        else:
            st.session_state.pop("af_severity_label", None)
    except Exception:
        st.session_state.pop("af_severity_label", None)

    try:
        lbl = notif_id2label.get(int(row["notification_type_cd"]))
        if lbl:
            st.session_state["af_notif_label"] = lbl
        else:
            st.session_state.pop("af_notif_label", None)
    except Exception:
        st.session_state.pop("af_notif_label", None)


# -----------------------------
# UI Components
# -----------------------------
def render_existing_alerts_section(
    existing: pd.DataFrame,
    alert_type_id2label: Dict[int, str],
    severity_id2label: Dict[int, str],
    notif_id2label: Dict[int, str],
) -> Optional[int]:
    """Render existing alerts table and selection dropdown. Returns selected alert ID."""
    selected_alert_id = None

    with st.expander("Existing Alerts", expanded=True):
        if existing is not None and not existing.empty:
            # Display table
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

            # Selection dropdown
            select_map = {
                f"{r.alert_name} — [{alert_type_id2label.get(int(r.alert_type_cd), 'Unknown')}]": int(
                    r.alert_definition_id
                )
                for _, r in existing.iterrows()
            }
            
            # Track last selected alert to detect changes
            last_selected = st.session_state.get("last_selected_alert_id")
            
            select_label = st.selectbox(
                "Select an alert to edit (optional)",
                options=["(Create New)"] + list(select_map.keys()),
                index=0,
                key="alert_selector"
            )
            
            if select_label != "(Create New)":
                selected_alert_id = select_map[select_label]
                row = existing[existing["alert_definition_id"] == selected_alert_id].iloc[0]
                st.session_state["current_alert_type_cd"] = int(row["alert_type_cd"])
                
                # Force rerun if selection changed
                if last_selected != selected_alert_id:
                    st.session_state["last_selected_alert_id"] = selected_alert_id
                    st.rerun()

                # Delete section
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
                        clear_alert_form_state()
                        st.cache_data.clear()
                        st.rerun()
            else:
                # Clear tracking when "(Create New)" is selected
                if last_selected is not None:
                    st.session_state["last_selected_alert_id"] = None
                    st.rerun()
        else:
            st.caption("No alerts yet for this pipeline & environment.")

    return selected_alert_id


def render_alert_definition_form(
    pipeline_id: int,
    environment_id: int,
    code_maps: Dict[str, pd.DataFrame],
) -> None:
    """Render the alert definition create/edit form."""
    with st.form("alert_form", clear_on_submit=False, border=True):
        st.subheader("Alert Definition")

        # Text inputs
        alert_name = st.text_input("Alert Name", key="af_alert_name")
        alert_desc = st.text_area("Alert Description", key="af_alert_desc")

        # Dropdown options
        alert_type_opt = _codes_to_select(code_maps["ALERT_TYPE"])
        severity_opt = _codes_to_select(code_maps["ALERT_SEVERITY"])
        notif_opt = _codes_to_select(code_maps["ALERT_NOTIFICATION_TYPE"])

        # Dropdowns (session state only, no index parameter)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            alert_type_label = st.selectbox(
                "Alert Type",
                options=list(alert_type_opt.keys()),
                key="af_alert_type_label"
            )
        with col2:
            severity_label = st.selectbox(
                "Severity",
                options=list(severity_opt.keys()),
                key="af_severity_label"
            )
        with col3:
            notification_type_label = st.selectbox(
                "Notification Type",
                options=list(notif_opt.keys()),
                key="af_notif_label"
            )
        with col4:
            is_enabled = st.toggle("Enabled", key="af_is_enabled")

        recipient_list = st.text_input(
            "Recipients (comma-separated emails or Slack channels)",
            key="af_recipient_list",
        )

        # Submit button
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
                    "recipient_list": recipient_list.strip(),
                    "is_enabled": is_enabled,
                    "user": st.session_state.get("user", {}).get("email", "system"),
                }
                adid = upsert_alert_definition(payload)
                if adid:
                    st.success("Alert saved. Configure details below (if required).")
                    st.session_state["current_adid"] = adid
                    st.session_state["current_alert_type_cd"] = payload["alert_type_cd"]
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Failed to save alert definition.")


def render_cadence_config_tab(alert_definition_id: int, code_maps: Dict[str, pd.DataFrame]) -> None:
    """Render the Cadence configuration tab."""
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
            upsert_cadence_config(alert_definition_id, payload)
            st.success("Cadence configuration saved.")


def render_data_threshold_config_tab(alert_definition_id: int, code_maps: Dict[str, pd.DataFrame]) -> None:
    """Render the Data Threshold configuration tab."""
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
                upsert_threshold_config(alert_definition_id, payload)
                st.success("Threshold configuration upserted.")


def render_processing_time_config_tab(alert_definition_id: int) -> None:
    """Render the Processing Time configuration tab."""
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
            upsert_processing_config(alert_definition_id, payload)
            st.success("Processing-time configuration saved.")


def render_configuration_tabs(
    alert_definition_id: int,
    alert_type_common: str,
    code_maps: Dict[str, pd.DataFrame],
) -> None:
    """Render configuration tabs based on alert type."""
    show_cadence = alert_type_common == "CADENCE_ALERT"
    show_threshold = alert_type_common == "DATA_THRESHOLD"
    show_processing = alert_type_common == "PROCESSING_TIME"

    if not any([show_cadence, show_threshold, show_processing]):
        st.success("This alert type does not require additional configuration.")
        return

    st.markdown("### Configure Alert Details")

    # Build tabs
    tab_names = []
    if show_cadence:
        tab_names.append("Cadence")
    if show_threshold:
        tab_names.append("Data Threshold")
    if show_processing:
        tab_names.append("Processing Time")
    
    tabs = st.tabs(tab_names)
    ti = 0

    if show_cadence:
        with tabs[ti]:
            render_cadence_config_tab(alert_definition_id, code_maps)
        ti += 1

    if show_threshold:
        with tabs[ti]:
            render_data_threshold_config_tab(alert_definition_id, code_maps)
        ti += 1

    if show_processing:
        with tabs[ti]:
            render_processing_time_config_tab(alert_definition_id)


# -----------------------------
# Main Page
# -----------------------------
def alert_management_page():
    """Main entry point for the Alert Management page."""
    st.header("🚨 Alert Management")
    st.caption("Define, edit, and configure alerts for specific pipelines & environments.")

    # Load system codes
    code_maps = get_system_codes_map(
        [
            "ALERT_TYPE",
            "ALERT_SEVERITY",
            "ALERT_NOTIFICATION_TYPE",
            "CADENCE_TYPE",
            "TIME_UNIT",
            "PIPELINE_RUN_DETAIL_TYPE",
            "ALERT_STATUS",
        ]
    )

    # Create lookup maps
    alert_type_id2label = _codes_id_to_label(code_maps["ALERT_TYPE"])
    severity_id2label = _codes_id_to_label(code_maps["ALERT_SEVERITY"])
    notif_id2label = _codes_id_to_label(code_maps["ALERT_NOTIFICATION_TYPE"])
    alert_type_id2common = _codes_id_to_common(code_maps["ALERT_TYPE"])

    # Pipeline selector
    pipes = get_active_pipelines()
    if pipes is None or pipes.empty:
        st.info("No active pipelines found.")
        return

    pipe_label_to_id = {str(r.pipeline_name): int(r.pipeline_id) for _, r in pipes.iterrows()}
    pipe_label = st.selectbox("Pipeline", options=list(pipe_label_to_id.keys()))
    pipeline_id = pipe_label_to_id[pipe_label]

    # Environment selector
    envs = get_environments_for_pipeline(pipeline_id)
    if envs is None or envs.empty:
        st.warning("Selected pipeline has no configured environments.")
        return

    env_label_to_id: Dict[str, int] = {}
    for _, r in envs.iterrows():
        desc = str(r["code_description"]).strip() if pd.notna(r["code_description"]) else ""
        base = str(r["environment"])
        label = f"{base} — {desc}".strip(" —")
        env_label_to_id[label] = int(r["environment_id"])

    env_label = st.selectbox("Environment", options=list(env_label_to_id.keys()))
    environment_id = env_label_to_id[env_label]

    # Check if pipeline/environment context changed
    if check_context_change(pipeline_id, environment_id):
        st.rerun()

    st.markdown("---")

    # Load existing alerts
    existing = get_existing_alerts(pipeline_id, environment_id)

    # Render existing alerts section
    selected_alert_id = render_existing_alerts_section(
        existing,
        alert_type_id2label,
        severity_id2label,
        notif_id2label,
    )

    # Seed form state
    _seed_alert_form_state(
        selected_alert_id=selected_alert_id,
        existing=existing,
        alert_type_id2label=alert_type_id2label,
        severity_id2label=severity_id2label,
        notif_id2label=notif_id2label,
    )

    st.markdown("---")

    # Render alert definition form
    render_alert_definition_form(pipeline_id, environment_id, code_maps)

    # Determine current alert for configuration
    adid = st.session_state.get("current_adid", selected_alert_id)
    
    if not adid:
        st.info("Save an alert first to configure any additional details.")
        return

    # Get current alert type
    current_type_cd = st.session_state.get("current_alert_type_cd")
    if current_type_cd is None and adid and existing is not None and not existing.empty:
        m = existing[existing["alert_definition_id"] == adid]
        if not m.empty:
            current_type_cd = int(m.iloc[0]["alert_type_cd"])

    current_type_common = (
        alert_type_id2common.get(int(current_type_cd), "").upper() if current_type_cd is not None else ""
    )

    # Render configuration tabs
    render_configuration_tabs(adid, current_type_common, code_maps)