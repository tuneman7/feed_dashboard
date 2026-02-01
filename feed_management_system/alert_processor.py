#!/usr/bin/env python3
"""
alert_processor.py
Runs once (hook via cron every minute).
Processes COMPLETION_ALERT definitions:
  * Detects new COMPLETED pipeline runs in a short lookback window
  * Creates alert_instance rows (deduped)
  * Sends EMAIL notifications via GmailSender (HTML + text rendered from external Jinja templates)
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
import os
import json
# add at top with the other MIME imports
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


import pandas as pd
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from database_utils_standalone import execute_query
from email_sender import GmailSender

from pathlib import Path
import base64
import re
import json


def transform_alert_to_notification(alert_data,schema_version = "1"):
    """
    Transform alert JSON to notification JSON format.
    Only includes keys that exist in both source and target.
    """
    # Create a mapping from detail_type to detail_data
    detail_map = {}
    for detail in alert_data.get('run_details', []):
        detail_type = detail.get('detail_type')
        detail_data = detail.get('detail_data')
        if detail_type and detail_data:
            detail_map[detail_type] = detail_data
    
    # Build output with only matching keys
    output = {}
    
    # Map the fields
    if 'JOB_TYPE' in detail_map:
        output['job_type'] = detail_map['JOB_TYPE']
    else:
        output['job_type'] = ""
    
    if 'JOB_FILE_NUMBER' in detail_map:
        output['job_file_number'] = detail_map['JOB_FILE_NUMBER']
    else:
        output['job_file_number'] = ""
    
    if 'BANK_FILE_NUMBER' in detail_map:
        output['bank_file_number'] = detail_map['BANK_FILE_NUMBER']
    else:
        output['bank_file_number'] = ""
    
    if 'SOURCE' in detail_map:
        output['source'] = detail_map['SOURCE']
    else:
        output['source'] = ""
    
    if 'ENV' in detail_map:
        output['env'] = detail_map['ENV']
    else:
        output['env'] = ""
    
    if 'REQUESTED_AT' in detail_map:
        output['requested_at'] = detail_map['REQUESTED_AT']
    else:
        output['requested_at'] = ""

    output['schema_version'] = schema_version
    
    return output


def send_sqs_notification(
    *,
    queue_url: str,
    message: Dict[str, Any],
    message_group_id: Optional[str] = None,
    message_deduplication_id: Optional[str] = None,
    region_name: str = "us-east-1",
) -> Dict[str, Any]:
    """
    Send a single alert message to SQS.

    - Standard queues: QueueUrl + MessageBody.
    - FIFO queues (.fifo): MessageGroupId required; MessageDeduplicationId optional.
    """

    import json
    import boto3
    from typing import Any, Dict, Optional

    sqs = boto3.client("sqs", region_name=region_name)

    kwargs: Dict[str, Any] = {
        "QueueUrl": queue_url,
        "MessageBody": json.dumps(message, default=str),
    }

    if queue_url.endswith(".fifo"):
        if not message_group_id:
            raise ValueError("FIFO queue requires message_group_id")

        kwargs["MessageGroupId"] = message_group_id

        if message_deduplication_id:
            kwargs["MessageDeduplicationId"] = message_deduplication_id

    return sqs.send_message(**kwargs)




def get_pipeline_run_details(pipeline_run_id: int) -> List[Dict[str, Any]]:
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
    WHERE prd.pipeline_run_id = %(rid)s
    ORDER BY prd.created_at, prd.detail_id;
    """

    df = execute_query(run_details_query, {"rid": pipeline_run_id}, fetch=True)
    if df is None or df.empty:
        return []

    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        out.append({
            "detail_id": int(row["detail_id"]) if row.get("detail_id") is not None else None,
            "parent_detail_id": int(row["parent_detail_id"]) if row.get("parent_detail_id") is not None else None,
            "detail_type": row.get("detail_type"),
            "detail_type_desc": row.get("detail_type_desc"),
            "detail_desc": row.get("detail_desc"),
            "detail_data": row.get("detail_data"),
            "created_at": str(row.get("created_at")) if row.get("created_at") is not None else None,
        })

    return out



def split_sqs_queue_urls(recipient_list: str) -> List[str]:
    """
    Treat recipient_list as a comma/semicolon/newline separated list of SQS QueueUrls.
    Example:
      https://sqs.us-east-1.amazonaws.com/123456789012/my-queue
      https://sqs.us-east-1.amazonaws.com/123456789012/my-queue.fifo
    """
    if not recipient_list:
        return []

    parts = re.split(r"[,\n;]+", recipient_list)
    urls = [p.strip() for p in parts if p and p.strip()]

    # Keep validation light (so we don't reject legit URLs due to minor format differences)
    urls = [u for u in urls if u.startswith("https://sqs.") and "amazonaws.com" in u]
    return urls



def get_pipeline_run_details(pipeline_run_id: int) -> List[Dict[str, Any]]:
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
    WHERE prd.pipeline_run_id = %(rid)s
    ORDER BY prd.created_at, prd.detail_id;
    """

    df = execute_query(run_details_query, {"rid": pipeline_run_id}, fetch=True)
    if df is None or df.empty:
        return []

    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        out.append({
            "detail_id": int(row["detail_id"]) if row.get("detail_id") is not None else None,
            "parent_detail_id": int(row["parent_detail_id"]) if row.get("parent_detail_id") is not None else None,
            "detail_type": row.get("detail_type"),
            "detail_type_desc": row.get("detail_type_desc"),
            "detail_desc": row.get("detail_desc"),
            "detail_data": row.get("detail_data"),
            "created_at": str(row.get("created_at")) if row.get("created_at") is not None else None,
        })

    return out



def load_shift4_logo_base64(filename: str = "shift4_data_systems_team.png") -> str:
    """
    Load the Shift4 banner from templates/images/<filename> and return base64.
    Returns "" if missing (graceful no-op for templates).
    """
    images_dir = _templates_dir() / "images"
    logo_path = images_dir / filename
    try:
        if not logo_path.exists():
            print(f"Shift4 logo not found at {logo_path}; skipping logo embedding")
            return ""
        return base64.b64encode(logo_path.read_bytes()).decode("ascii")
    except Exception as ex:
        print(f"Error reading Shift4 logo at {logo_path}: {ex}")
        return ""


def _templates_dir() -> Path:
    return Path(__file__).resolve().parent / "templates"

def load_shift4_logo_bytes(filename: str = "shift4_data_systems_team.png") -> bytes | None:
    p = _templates_dir() / "images" / filename
    try:
        if not p.exists():
            print(f"Shift4 logo not found at {p}; skipping logo embedding")
            return None
        return p.read_bytes()
    except Exception as ex:
        print(f"Error reading Shift4 logo at {p}: {ex}")
        return None



# ---------------------------
# Config
# ---------------------------
LOOKBACK_MINUTES = int(os.getenv("ALERT_LOOKBACK_MINUTES", "180"))  # window for detecting fresh completions

# Template base directory (relative to this file)
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "alerts"

# ---------------------------
# Built-in fallback templates (used only if files are missing)
# ---------------------------
FALLBACK_TEMPLATES: Dict[str, Dict[str, str]] = {
    "COMPLETION_ALERT": {
        "subject": "[{{ severity_text }}][Completion] {{ pipeline_name }} — {{ environment_cd }} completed at {{ end_dt }}",
        "text": """Pipeline completed successfully.

Pipeline: {{ pipeline_name }}
Environment: {{ environment_cd }} ({{ environment_desc }})
Run ID: {{ pipeline_run_id }}
Started: {{ start_dt }}
Ended: {{ end_dt }}
Duration: {{ duration_minutes }} minute(s)
{% if total_processed_count is not none %}
Total Rows Processed: {{ total_processed_count }}
{% endif %}

Alert: {{ alert_name }}
Description: {{ alert_description or "-" }}

This is an automated notification.
""",
        "html": """<div style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; line-height:1.5; color:#111;">
  <h3>Pipeline Completed</h3>
  <table style="border-collapse:collapse; width:100%; max-width:640px;">
    <tr><td style="padding:4px 8px;"><strong>Pipeline</strong></td><td style="padding:4px 8px;">{{ pipeline_name }}</td></tr>
    <tr><td style="padding:4px 8px;"><strong>Environment</strong></td><td style="padding:4px 8px;">{{ environment_cd }} — {{ environment_desc }}</td></tr>
    <tr><td style="padding:4px 8px;"><strong>Run ID</strong></td><td style="padding:4px 8px;">{{ pipeline_run_id }}</td></tr>
    <tr><td style="padding:4px 8px;"><strong>Started</strong></td><td style="padding:4px 8px;">{{ start_dt }}</td></tr>
    <tr><td style="padding:4px 8px;"><strong>Ended</strong></td><td style="padding:4px 8px;">{{ end_dt }}</td></tr>
    <tr><td style="padding:4px 8px;"><strong>Duration</strong></td><td style="padding:4px 8px;">{{ duration_minutes }} minute(s)</td></tr>
    {% if total_processed_count is not none %}
    <tr><td style="padding:4px 8px;"><strong>Total Rows Processed</strong></td><td style="padding:4px 8px;">{{ total_processed_count }}</td></tr>
    {% endif %}
  </table>
  <p><strong>Alert:</strong> {{ alert_name }}</p>
  {% if alert_description %}
  <p style="white-space:pre-line">{{ alert_description }}</p>
  {% endif %}
  <p style="margin-top:16px; color:#555;">This is an automated notification.</p>
</div>""",
    }
}


def _int_with_commas(v) -> Optional[str]:
    try:
        if v is None:
            return None
        return f"{int(v):,}"
    except Exception:
        return None

def _duration_seconds(start_ts, end_ts) -> int:
    try:
        delta = pd.to_datetime(end_ts) - pd.to_datetime(start_ts)
        return max(0, int(delta.total_seconds()))
    except Exception:
        return 0



# ---------------------------
# Jinja loader (file-based, with graceful fallback)
# ---------------------------
def render_email_templates(alert_type_common_cd: str, context: Dict[str, Any]) -> Dict[str, str]:
    """
    Try to render subject/text/html using filesystem templates:
      templates/alerts/<ALERT_TYPE>/subject.j2
      templates/alerts/<ALERT_TYPE>/text.j2
      templates/alerts/<ALERT_TYPE>/html.j2
    Falls back to built-in strings if any template is missing.
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    atype = alert_type_common_cd.upper().strip()

    # ---- NEW: custom filters ----
    def comma(n):
        try:
            return f"{int(n):,}"
        except Exception:
            return n

    def hms(seconds):
        try:
            s = int(seconds or 0)
            h = s // 3600
            m = (s % 3600) // 60
            sec = s % 60
            return f"{h:01d}:{m:02d}:{sec:02d}"
        except Exception:
            return seconds

    def fmt_dt(dt):
        try:
            return pd.to_datetime(dt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(dt)

    env.filters["comma"] = comma
    env.filters["hms"] = hms
    env.filters["fmt_dt"] = fmt_dt
    # ---- end filters ----

    def _render(name: str) -> str:
        template_rel_path = f"{atype}/{name}.j2"
        try:
            tpl = env.get_template(template_rel_path)
            fname = getattr(tpl, "filename", template_rel_path)
            print(f"Loaded email template file: {fname}")
            return tpl.render(**context)
        except TemplateNotFound:
            print(f"Template file not found for {atype}/{name}.j2; using fallback template")
            fb = FALLBACK_TEMPLATES.get(atype, {}).get(name)
            if fb is None:
                if name == "subject":
                    s = f"[{context.get('severity_text','INFO')}][{atype}] {context.get('pipeline_name','Pipeline')} — {context.get('environment_cd','ENV')}"
                    print(f"No fallback subject available; returning minimal subject: {s}")
                    return s
                elif name == "text":
                    print("No fallback text available; returning minimal text")
                    return "No template available."
                else:
                    print("No fallback html available; returning minimal html")
                    return "<p>No template available.</p>"
            from jinja2 import Template as _T
            return _T(fb).render(**context)

    return {
        "subject": _render("subject"),
        "text": _render("text"),
        "html": _render("html"),
    }

# ---------------------------
# Helpers
# ---------------------------
def get_code_id(common_cd: str, code_type: str) -> Optional[int]:
    df = execute_query(
        """
        SELECT code_id
        FROM admin.system_codes
        WHERE common_cd = %(common_cd)s
          AND code_type_cd = %(code_type)s
          AND is_active = true
        LIMIT 1;
        """,
        {"common_cd": common_cd, "code_type": code_type},
        fetch=True,
    )
    if df is not None and not df.empty:
        cid = int(df.iloc[0]["code_id"])
        print(f"Resolved code id for {code_type}.{common_cd}: {cid}")
        return cid
    print(f"Failed to resolve code id for {code_type}.{common_cd}")
    return None

def split_email_recipients(recips: str) -> List[str]:
    if not recips:
        return []
    lst = [r.strip() for r in recips.split(",") if r.strip() and "@" in r]
    print(f"Parsed {len(lst)} email recipient(s)")
    return lst

def minutes_between(start_ts, end_ts) -> int:
    try:
        delta = pd.to_datetime(end_ts) - pd.to_datetime(start_ts)
        mins = max(0, int(delta.total_seconds() // 60))
        return mins
    except Exception:
        return 0

def _to_int_or_none(v) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, (int,)):
            return v
        s = str(v).strip().replace(",", "")
        return int(float(s))  # supports "12345.0"
    except Exception:
        return None

# ---------------------------
# Core: Completion Alerts
# ---------------------------
def process_completion_alerts(lookback_minutes: int = LOOKBACK_MINUTES) -> int:
    print(f"Starting process_completion_alerts with lookback_minutes={lookback_minutes}")
    created = 0

    # Resolve required codes (IDs only where needed)
    completion_type_id   = get_code_id("COMPLETION_ALERT", "ALERT_TYPE")
    active_status_id     = get_code_id("ACTIVE", "ALERT_STATUS")
    email_type_id        = get_code_id("EMAIL", "ALERT_NOTIFICATION_TYPE")
    total_count_type_id  = get_code_id("TOTAL_PROCESSED_COUNT", "PIPELINE_RUN_DETAIL_TYPE")
    sqs_type_id          = get_code_id("SQS", "ALERT_NOTIFICATION_TYPE")

    if completion_type_id is None or active_status_id is None:
        print("Required system codes missing; exiting without processing")
        return 0

    alerts_query = f"""
        SELECT
          ad.alert_definition_id,
          ad.pipeline_id,
          ad.environment_id,
          ad.alert_name,
          ad.alert_description,
          ad.severity_cd,                -- numeric code_id
          ad.notification_type_cd,       -- numeric code_id
          ad.recipient_list,
          p.pipeline_name,
          sc_env.common_cd        AS environment_cd,
          sc_env.code_description AS environment_desc,
          sc_sev.common_cd        AS severity_common_cd,      -- decoded severity (e.g., MEDIUM)
          sc_sev.code_description AS severity_desc            -- optional
        FROM pipeline.alert_definition ad
        JOIN pipeline.pipeline p               ON p.pipeline_id = ad.pipeline_id
        JOIN pipeline.pipeline_environment pe  ON pe.environment_id = ad.environment_id
        JOIN admin.system_codes sc_env         ON sc_env.code_id  = pe.env_system_cd
        LEFT JOIN admin.system_codes sc_sev    ON sc_sev.code_id  = ad.severity_cd
                                              AND sc_sev.code_type_cd = 'ALERT_SEVERITY'
        WHERE ad.is_enabled = true
          AND ad.alert_type_cd = {completion_type_id}
        ORDER BY p.pipeline_name, ad.alert_name;
        """

    alerts = execute_query(alerts_query, fetch=True)
    if alerts is None or alerts.empty:
        print("No enabled completion alerts found")
        return 0

    print(f"Loaded {len(alerts)} enabled completion alert definition(s)")
    mailer = GmailSender()

    for _, a in alerts.iterrows():
        adid = int(a["alert_definition_id"])
        pipeline_id = int(a["pipeline_id"])
        environment_id = int(a["environment_id"])
        recipient_list_raw = (a.get("recipient_list") or "").strip()

        print(f"Processing alert_definition_id={adid} pipeline_id={pipeline_id} environment_id={environment_id}")

        # --- Determine channel ---
        is_sqs_alert = False
        if sqs_type_id is not None and int(a["notification_type_cd"]) == sqs_type_id:
            is_sqs_alert = True

        is_email_alert = False
        if email_type_id is not None and int(a["notification_type_cd"]) == email_type_id:
            is_email_alert = True

        if not is_sqs_alert and not is_email_alert:
            print(
                f"Skipping alert_definition_id={adid} due to unsupported notification_type_cd={a['notification_type_cd']}"
            )
            continue

        # --- Parse recipients based on channel ---
        recipients: List[str] = []
        queue_urls: List[str] = []

        if is_email_alert:
            recipients = split_email_recipients(recipient_list_raw)
            if not recipients:
                print(f"Skipping alert_definition_id={adid} because email recipient list is empty or invalid")
                continue

        if is_sqs_alert:
            queue_urls = split_sqs_queue_urls(recipient_list_raw)
            if not queue_urls:
                print(f"Skipping alert_definition_id={adid} because SQS QueueUrl(s) not found in recipient_list")
                continue

        # Find recent COMPLETED runs + total_processed_count
        print(f"Querying recent COMPLETED runs for pipeline_id={pipeline_id} environment_id={environment_id}")
        runs = execute_query(
            """
            SELECT
              pr.pipeline_run_id,
              pr.start_dt,
              pr.end_dt,
              prd_count.detail_data AS total_processed_count
            FROM pipeline.pipeline_run pr
            LEFT JOIN pipeline.pipeline_run_details prd_count
              ON prd_count.pipeline_run_id = pr.pipeline_run_id
             AND prd_count.run_detail_type_cd = %(count_type_id)s
            WHERE pr.pipeline_id = %(pid)s
              AND pr.environment_id = %(eid)s
              AND pr.status_cd = 'COMPLETED'
              AND pr.status_cd_type = 'STATUS'
              AND pr.end_dt IS NOT NULL
              AND pr.end_dt >= (CURRENT_TIMESTAMP - INTERVAL %(mins)s)
            ORDER BY pr.end_dt DESC;
            """,
            {
                "pid": pipeline_id,
                "eid": environment_id,
                "mins": f"'{lookback_minutes} minutes'",
                "count_type_id": total_count_type_id,
            },
            fetch=True,
        )
        if runs is None or runs.empty:
            print("No recent completed runs found")
            continue

        print(f"Found {len(runs)} completed run(s) within lookback window")

        for _, r in runs.iterrows():
            run_id = int(r["pipeline_run_id"])

            # Dedup: skip if already alerted for this (adid, run_id)
            already = execute_query(
                """
                SELECT 1
                FROM pipeline.alert_instance
                WHERE alert_definition_id = %(adid)s
                  AND pipeline_run_id = %(rid)s
                LIMIT 1;
                """,
                {"adid": adid, "rid": run_id},
                fetch=True,
            )
            if already is not None and not already.empty:
                print(f"Skipping run_id={run_id} for alert_definition_id={adid} because an alert_instance already exists")
                continue

            start_dt = r["start_dt"]
            end_dt = r["end_dt"]

            duration_min = minutes_between(start_dt, end_dt)
            duration_sec = _duration_seconds(start_dt, end_dt)

            total_processed_count_raw = r.get("total_processed_count")
            total_processed_count = _to_int_or_none(total_processed_count_raw)
            if total_processed_count is None and total_processed_count_raw is not None:
                print(f"Could not parse total_processed_count='{total_processed_count_raw}' for run_id={run_id}")
            elif total_processed_count is not None:
                print(f"Resolved total_processed_count={total_processed_count} for run_id={run_id}")

            # Severity: rely on SQL-decoded common_cd; fallback to INFO if missing
            severity_text = (a.get("severity_common_cd") or "INFO").upper()
            print(
                "Severity check: "
                f"alert_definition_id={adid} "
                f"severity_cd={a['severity_cd']} "
                f"severity_common_cd={a.get('severity_common_cd')} "
                f"severity_desc={a.get('severity_desc')}"
            )

            context = {
                "severity_text": severity_text,
                "pipeline_name": a.get("pipeline_name"),
                "environment_cd": a.get("environment_cd"),
                "environment_desc": a.get("environment_desc"),
                "pipeline_run_id": run_id,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "duration_minutes": duration_min,
                "duration_seconds": duration_sec,
                "total_processed_count": total_processed_count,
                "alert_name": a.get("alert_name"),
                "alert_description": a.get("alert_description"),
            }

            logo_bytes = load_shift4_logo_bytes()
            inline_images = {"shift4logo": logo_bytes} if logo_bytes else None

            # Render subject/text/html via external templates (fallback-safe)
            rendered = render_email_templates("COMPLETION_ALERT", context)
            subject = rendered["subject"]
            text_body = rendered["text"]
            html_body = rendered["html"]

            # Insert alert_instance
            alert_message = f"Pipeline completed at {end_dt} (duration {duration_min}m)"
            alert_data = {
                "type": "COMPLETION_ALERT",
                "pipeline_id": pipeline_id,
                "environment_id": environment_id,
                "pipeline_run_id": run_id,
                "start_dt": str(start_dt),
                "end_dt": str(end_dt),
                "duration_minutes": duration_min,
                "total_processed_count": total_processed_count,
                "alert_name": a.get("alert_name"),
                "severity_cd": int(a.get("severity_cd")),
            }

            # Store intended channel in notification_channels on insert (so DB truth matches branch)
            channels = ["sqs"] if is_sqs_alert else ["email"]

            ins = execute_query(
                """
                INSERT INTO pipeline.alert_instance
                  (alert_definition_id, pipeline_run_id,
                   triggered_at, alert_status_cd,
                   alert_message, alert_data,
                   notification_sent, notification_sent_at, notification_channels,
                   created_at, updated_at)
                VALUES
                  (%(adid)s, %(rid)s,
                   CURRENT_TIMESTAMP, %(status_id)s,
                   %(msg)s, %(j)s::jsonb,
                   FALSE, NULL, %(channels)s,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING alert_instance_id;
                """,
                {
                    "adid": adid,
                    "rid": run_id,
                    "status_id": active_status_id,
                    "msg": alert_message,
                    "j": json.dumps(alert_data),
                    "channels": channels,
                },
                fetch=True,
            )
            if ins is None or ins.empty:
                print("Failed to insert alert_instance")
                continue

            alert_instance_id = int(ins.iloc[0]["alert_instance_id"])
            print(f"Inserted alert_instance_id={alert_instance_id}")

            # -------------------------
            # TRANSMIT (branch)
            # -------------------------
            if is_sqs_alert:
                try:
                    # Pull run details for message payload
                    run_details = get_pipeline_run_details(run_id)


                    sqs_message = {
                        "alert_type": "COMPLETION_ALERT",
                        "alert_instance_id": alert_instance_id,
                        "alert_definition_id": adid,
                        "pipeline_id": pipeline_id,
                        "environment_id": environment_id,
                        "pipeline_run_id": run_id,
                        "severity": severity_text,
                        "subject": subject,
                        "alert_data": alert_data,
                        "run_details": run_details,
                        "triggered_at": str(end_dt),
                    }

                    message_ids: List[str] = []
                    for qurl in queue_urls:
                        print("*"*40)
                        print(f"Sending SQS Message to: {qurl}.")
                        print("*"*40)
                        transformed_message = transform_alert_to_notification(sqs_message)
                        print(transformed_message)
                        print("*"*40)                        
                        resp = send_sqs_notification(queue_url=qurl, message=transformed_message)
                        mid = (resp or {}).get("MessageId")
                        if mid:
                            message_ids.append(mid)

                    execute_query(
                        """
                        UPDATE pipeline.alert_instance
                           SET notification_sent = TRUE,
                               notification_sent_at = CURRENT_TIMESTAMP,
                               alert_data = COALESCE(alert_data, '{}'::jsonb)
                                          || jsonb_build_object('sqs_message_ids', %(mids)s)
                         WHERE alert_instance_id = %(id)s;
                        """,
                        {"id": alert_instance_id, "mids": json.dumps(message_ids)},
                        fetch=False,
                    )
                    print(
                        f"SQS sent and alert_instance marked sent: alert_instance_id={alert_instance_id} "
                        f"(queues={len(queue_urls)}, message_ids={len(message_ids)})"
                    )

                except Exception as ex:
                    print(f"Error sending SQS for alert_instance_id={alert_instance_id}: {ex}")
                    execute_query(
                        """
                        UPDATE pipeline.alert_instance
                           SET alert_data = COALESCE(alert_data, '{}'::jsonb)
                                        || jsonb_build_object('sqs_error', %(err)s)
                         WHERE alert_instance_id = %(id)s;
                        """,
                        {"id": alert_instance_id, "err": str(ex)},
                        fetch=False,
                    )

            elif is_email_alert:
                try:
                    print(f"Sending email to {len(recipients)} recipient(s) for alert_instance_id={alert_instance_id}")
                    mailer.send_mail(
                        recipients=recipients,
                        subject=subject,
                        text_body=text_body,
                        html_body=html_body,
                        inline_images=inline_images,
                    )

                    execute_query(
                        """
                        UPDATE pipeline.alert_instance
                           SET notification_sent = TRUE,
                               notification_sent_at = CURRENT_TIMESTAMP
                         WHERE alert_instance_id = %(id)s;
                        """,
                        {"id": alert_instance_id},
                        fetch=False,
                    )
                    print(f"Email sent and alert_instance marked sent: alert_instance_id={alert_instance_id}")
                except Exception as ex:
                    print(f"Error sending email for alert_instance_id={alert_instance_id}: {ex}")
                    execute_query(
                        """
                        UPDATE pipeline.alert_instance
                           SET alert_data = COALESCE(alert_data, '{}'::jsonb)
                                        || jsonb_build_object('email_error', %(err)s)
                         WHERE alert_instance_id = %(id)s;
                        """,
                        {"id": alert_instance_id, "err": str(ex)},
                        fetch=False,
                    )

            created += 1

    print(f"Finished process_completion_alerts; created {created} alert_instance row(s)")
    return created


def process_hardfailure_alerts(lookback_minutes: int = LOOKBACK_MINUTES) -> int:
    """
    Identical flow to process_completion_alerts, but for hard failures.
    - Pulls HARDFAILURE_ALERT definitions
    - Filters to EMAIL-only and requires recipients
    - Finds FAILED/ERROR/HARD_FAILURE runs in lookback window
    - Dedupes by (alert_definition_id, pipeline_run_id)
    - Renders HARDFAILURE_ALERT templates (subject/text/html)
    - Inserts alert_instance and sends email
    - Adds CloudWatch log URL using run_detail_type code lookup
    """
    print(f"Starting process_hardfailure_alerts with lookback_minutes={lookback_minutes}")
    created = 0

    # Required system codes (same pattern you already use)
    hardfailure_type_id   = get_code_id("HARDFAILURE_ALERT", "ALERT_TYPE")
    active_status_id      = get_code_id("ACTIVE", "ALERT_STATUS")
    email_type_id         = get_code_id("EMAIL", "ALERT_NOTIFICATION_TYPE")
    total_count_type_id   = get_code_id("TOTAL_PROCESSED_COUNT", "PIPELINE_RUN_DETAIL_TYPE")
    cloudwatch_link_type_id = get_code_id("CLOUDWATCH_LOG_LINK", "PIPELINE_RUN_DETAIL_TYPE")

    if hardfailure_type_id is None or active_status_id is None:
        print("Required system codes missing; exiting without processing (hardfailure)")
        return 0

    # Load alert definitions for this type (unchanged pattern)
    alerts_query = f"""
        SELECT
          ad.alert_definition_id,
          ad.pipeline_id,
          ad.environment_id,
          ad.alert_name,
          ad.alert_description,
          ad.severity_cd,
          ad.notification_type_cd,
          ad.recipient_list,
          p.pipeline_name,
          sc_env.common_cd        AS environment_cd,
          sc_env.code_description AS environment_desc,
          sc_sev.common_cd        AS severity_common_cd,
          sc_sev.code_description AS severity_desc
        FROM pipeline.alert_definition ad
        JOIN pipeline.pipeline p               ON p.pipeline_id = ad.pipeline_id
        JOIN pipeline.pipeline_environment pe  ON pe.environment_id = ad.environment_id
        JOIN admin.system_codes sc_env         ON sc_env.code_id  = pe.env_system_cd
        LEFT JOIN admin.system_codes sc_sev    ON sc_sev.code_id  = ad.severity_cd
                                             AND sc_sev.code_type_cd = 'ALERT_SEVERITY'
        WHERE ad.is_enabled = true
          AND ad.alert_type_cd = {hardfailure_type_id}
        ORDER BY p.pipeline_name, ad.alert_name;
    """
    df_alerts = execute_query(alerts_query, fetch=True)
    if df_alerts is None or df_alerts.empty:
        print("No HARDFAILURE_ALERT definitions found; nothing to do")
        return 0

    print(f"Loaded {len(df_alerts)} HARDFAILURE alert definition(s)")

    for _, a in df_alerts.iterrows():
        adid = int(a["alert_definition_id"])
        pipeline_id = int(a["pipeline_id"])
        environment_id = int(a["environment_id"])

        # --- REQUIRED PARITY: email-only + recipients guard (your existing behavior) ---
        if email_type_id is not None and int(a["notification_type_cd"]) != email_type_id:
            print(f"Skipping alert_definition_id={adid} due to non-email notification_type_cd={a['notification_type_cd']}")
            continue

        recipients = split_email_recipients(a.get("recipient_list", ""))
        if not recipients:
            print(f"Skipping alert_definition_id={adid} because recipient list is empty or invalid")
            continue
        # -------------------------------------------------------------------------------

        severity_text = a.get("severity_common_cd") or "INFO"

        # Pull failed/error runs in window; join both count and cloudwatch link by type code
        runs = execute_query(
            """
            SELECT
              pr.pipeline_run_id,
              pr.start_dt,
              pr.end_dt,
              prd_count.detail_data AS total_processed_count,
              prd_log.detail_data   AS cloudwatch_log_url
            FROM pipeline.pipeline_run pr
            LEFT JOIN pipeline.pipeline_run_details prd_count
              ON prd_count.pipeline_run_id = pr.pipeline_run_id
             AND prd_count.run_detail_type_cd = %(count_type_id)s
            LEFT JOIN pipeline.pipeline_run_details prd_log
              ON prd_log.pipeline_run_id = pr.pipeline_run_id
             AND prd_log.run_detail_type_cd = %(cw_type_id)s
            WHERE pr.pipeline_id = %(pid)s
              AND pr.environment_id = %(eid)s
              AND pr.status_cd IN ('FAILED','ERROR','HARD_FAILURE')
              AND pr.status_cd_type = 'STATUS'
              AND pr.end_dt IS NOT NULL
              AND pr.end_dt >= (CURRENT_TIMESTAMP - INTERVAL %(mins)s)
            ORDER BY pr.end_dt DESC;
            """,
            {
                "pid": pipeline_id,
                "eid": environment_id,
                "mins": f"'{lookback_minutes} minutes'",
                "count_type_id": total_count_type_id,
                "cw_type_id": cloudwatch_link_type_id,
            },
            fetch=True,
        )
        if runs is None or runs.empty:
            print("No recent hardfailure runs found")
            continue

        print(f"Found {len(runs)} hardfailure run(s) within lookback window")

        for _, r in runs.iterrows():
            run_id = int(r["pipeline_run_id"])

            # De-dupe: skip if we already created an alert for this definition/run pair
            already = execute_query(
                """
                SELECT 1
                FROM pipeline.alert_instance
                WHERE alert_definition_id = %(adid)s
                  AND pipeline_run_id = %(rid)s
                LIMIT 1;
                """,
                {"adid": adid, "rid": run_id},
                fetch=True,
            )
            if already is not None and not already.empty:
                print(f"Skipping run_id={run_id} for alert_definition_id={adid} because an alert_instance already exists")
                continue

            start_dt = r["start_dt"]
            end_dt = r["end_dt"]
            duration_min = minutes_between(start_dt, end_dt)
            duration_sec = _duration_seconds(start_dt, end_dt)
            total_processed_count_raw = r.get("total_processed_count")
            total_processed_count = _to_int_or_none(total_processed_count_raw)
            if total_processed_count is None and total_processed_count_raw is not None:
                print(f"Could not parse total_processed_count='{total_processed_count_raw}' for run_id={run_id}")
            elif total_processed_count is not None:
                print(f"Resolved total_processed_count={total_processed_count} for run_id={run_id}")

            cloudwatch_log_url = (r.get("cloudwatch_log_url") or "").strip() or None

            # Email context (keys consistent with your completion templates + new log URL)
            context = {
                "severity_text": severity_text,
                "pipeline_name": a.get("pipeline_name"),
                "environment_cd": a.get("environment_cd"),
                "environment_desc": a.get("environment_desc"),
                "pipeline_run_id": run_id,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "duration_minutes": duration_min,
                "duration_seconds": duration_sec,
                "total_processed_count": total_processed_count,
                "alert_name": a.get("alert_name"),
                "alert_description": a.get("alert_description"),
                "cloudwatch_log_url": cloudwatch_log_url,  # NEW for templates
            }

            logo_bytes = load_shift4_logo_bytes()
            inline_images = {"shift4logo": logo_bytes} if logo_bytes else None

            # Render HARDFAILURE templates (separate from completion)
            rendered = render_email_templates("HARDFAILURE_ALERT", context)
            subject = rendered["subject"]
            text_body = rendered["text"]
            html_body = rendered["html"]

            # Insert alert_instance (same structure)
            alert_message = f"Pipeline hard failure at {end_dt} (duration {duration_min}m)"
            alert_data = {
                "type": "HARDFAILURE_ALERT",
                "pipeline_id": pipeline_id,
                "environment_id": environment_id,
                "pipeline_run_id": run_id,
                "start_dt": str(start_dt),
                "end_dt": str(end_dt),
                "duration_minutes": duration_min,
                "total_processed_count": total_processed_count,
                "alert_name": a.get("alert_name"),
                "severity_cd": int(a.get("severity_cd")) if a.get("severity_cd") is not None else None,
                "cloudwatch_log_url": cloudwatch_log_url,
            }

            ins = execute_query(
                """
                INSERT INTO pipeline.alert_instance
                  (alert_definition_id, pipeline_run_id,
                   triggered_at, alert_status_cd,
                   alert_message, alert_data,
                   notification_sent, notification_sent_at, notification_channels,
                   created_at, updated_at)
                VALUES
                  (%(adid)s, %(rid)s,
                   CURRENT_TIMESTAMP, %(status_id)s,
                   %(msg)s, %(j)s::jsonb,
                   FALSE, NULL, %(channels)s,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING alert_instance_id;
                """,
                {
                    "adid": adid,
                    "rid": run_id,
                    "status_id": active_status_id,
                    "msg": alert_message,
                    "j": json.dumps(alert_data),
                    "channels": ["email"],
                },
                fetch=True,
            )
            if ins is None or ins.empty:
                print("Failed to insert alert_instance (hardfailure)")
                continue

            alert_instance_id = int(ins.iloc[0]["alert_instance_id"])
            print(f"Inserted alert_instance_id={alert_instance_id} (hardfailure)")

            mailer = GmailSender()

            # Send email + mark sent
            try:
                print(f"Sending email to {len(recipients)} recipient(s) for HARDFAILURE alert_instance_id={alert_instance_id}")
                mailer.send_mail(
                    recipients=recipients,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                    inline_images=inline_images,
                )

                execute_query(
                    """
                    UPDATE pipeline.alert_instance
                       SET notification_sent = TRUE,
                           notification_sent_at = CURRENT_TIMESTAMP
                     WHERE alert_instance_id = %(id)s;
                    """,
                    {"id": alert_instance_id},
                    fetch=False,
                )
                print(f"Email sent and alert_instance marked sent (hardfailure): alert_instance_id={alert_instance_id}")
            except Exception as ex:
                print(f"Error sending HARDFAILURE email for alert_instance_id={alert_instance_id}: {ex}")
                execute_query(
                    """
                    UPDATE pipeline.alert_instance
                       SET alert_data = COALESCE(alert_data, '{}'::jsonb) || jsonb_build_object('email_error', %(err)s)
                     WHERE alert_instance_id = %(id)s;
                    """,
                    {"id": alert_instance_id, "err": str(ex)},
                    fetch=False,
                )

            created += 1

    print(f"Finished process_hardfailure_alerts; created {created} alert_instance row(s)")
    return created



def main():
    print(f"{datetime.utcnow().isoformat()}Z - Starting alert processor")
    print(f"Running alert_processor from: {Path(__file__).resolve()}")
    count = process_completion_alerts()
    print(f"{datetime.utcnow().isoformat()}Z - Processed completion alerts: created {count} alert_instance row(s).")

    # NEW: also process hardfailure alerts
    hf_count = process_hardfailure_alerts()
    print(f"{datetime.utcnow().isoformat()}Z - Processed hardfailure alerts: created {hf_count} alert_instance row(s).")



if __name__ == "__main__":
    main()
