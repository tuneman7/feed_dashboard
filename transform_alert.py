import json

def transform_alert_to_notification(alert_data):
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
    
    if 'JOB_FILE_NUMBER' in detail_map:
        output['job_file_number'] = detail_map['JOB_FILE_NUMBER']
    
    if 'BANK_FILE_NUMBER' in detail_map:
        output['bank_file_number'] = detail_map['BANK_FILE_NUMBER']
    
    if 'SOURCE' in detail_map:
        output['source'] = detail_map['SOURCE']
    
    if 'ENV' in detail_map:
        output['env'] = detail_map['ENV']
    
    if 'REQUESTED_AT' in detail_map:
        output['requested_at'] = detail_map['REQUESTED_AT']
    
    return output


# Load sample data
sample_input = {
  "alert_type": "COMPLETION_ALERT",
  "alert_instance_id": 3259,
  "alert_definition_id": 76,
  "pipeline_id": 62,
  "environment_id": 153,
  "pipeline_run_id": 56032,
  "severity": "CRITICAL",
  "subject": "[CRITICAL][Completion] ach — DEV completed at 2026-01-28 21:08:32.271541",
  "alert_data": {
    "type": "COMPLETION_ALERT",
    "pipeline_id": 62,
    "environment_id": 153,
    "pipeline_run_id": 56032,
    "start_dt": "2026-01-28 21:08:22.278238",
    "end_dt": "2026-01-28 21:08:32.271541",
    "duration_minutes": 0,
    "total_processed_count": 48294,
    "alert_name": "SQS ACH",
    "severity_cd": 59
  },
  "run_details": [
    {
      "detail_id": 158658,
      "parent_detail_id": None,
      "detail_type": "ECS_CONTAINER_LINK",
      "detail_type_desc": "Link to ECS container",
      "detail_desc": "Link to ECS container",
      "detail_data": "https://us-east-1.console.aws.amazon.com/ecs/home?region=us-east-1#/clusters/DST-Data-Movement-dev/tasks/c6a9ed14c701490cab069f92b46b673e/details",
      "created_at": "2026-01-28 21:08:22.285714"
    },
    {
      "detail_id": 158659,
      "parent_detail_id": None,
      "detail_type": "CLOUDWATCH_LOG_LINK",
      "detail_type_desc": "Link to CloudWatch logs",
      "detail_desc": "Link to CloudWatch logs",
      "detail_data": "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/%2Fecs%2Fdata-movement-ach-dev/log-events?filterPattern=%22c6a9ed14c701490cab069f92b46b673e%22",
      "created_at": "2026-01-28 21:08:22.288298"
    },
    {
      "detail_id": 158660,
      "parent_detail_id": None,
      "detail_type": "TOTAL_PROCESSED_COUNT",
      "detail_type_desc": "Total count processed.",
      "detail_desc": "Total count processed.",
      "detail_data": "48,294",
      "created_at": "2026-01-28 21:08:23.657864"
    },
    {
      "detail_id": 158661,
      "parent_detail_id": None,
      "detail_type": "RAW_INPUT_FILE",
      "detail_type_desc": "Raw Input File from source (s3, or other)",
      "detail_desc": "Raw Input File from source (s3, or other)",
      "detail_data": "apps-folder/HARBORTO.6888_ACH7_DET_01272026_071717.TSYSO",
      "created_at": "2026-01-28 21:08:32.258705"
    },
    {
      "detail_id": 158662,
      "parent_detail_id": None,
      "detail_type": "JOB_TYPE",
      "detail_type_desc": "Job type for SQS notification",
      "detail_desc": "Job type for SQS notification",
      "detail_data": "ACH",
      "created_at": "2026-01-28 21:08:32.260908"
    },
    {
      "detail_id": 158663,
      "parent_detail_id": None,
      "detail_type": "JOB_FILE_NUMBER",
      "detail_type_desc": "Job file number for SQS notification.",
      "detail_desc": "Job file number for SQS notification.",
      "detail_data": "20260127003",
      "created_at": "2026-01-28 21:08:32.262913"
    },
    {
      "detail_id": 158664,
      "parent_detail_id": None,
      "detail_type": "BANK_FILE_NUMBER",
      "detail_type_desc": "Bank file number for SQS notification.",
      "detail_desc": "Bank file number for SQS notification.",
      "detail_data": "6888",
      "created_at": "2026-01-28 21:08:32.264903"
    },
    {
      "detail_id": 158665,
      "parent_detail_id": None,
      "detail_type": "SOURCE",
      "detail_type_desc": "Source number for SQS notification.",
      "detail_desc": "Source number for SQS notification.",
      "detail_data": "DST",
      "created_at": "2026-01-28 21:08:32.266526"
    },
    {
      "detail_id": 158666,
      "parent_detail_id": None,
      "detail_type": "ENV",
      "detail_type_desc": "Env for sqs notification",
      "detail_desc": "Env for sqs notification",
      "detail_data": "dev",
      "created_at": "2026-01-28 21:08:32.268218"
    },
    {
      "detail_id": 158667,
      "parent_detail_id": None,
      "detail_type": "REQUESTED_AT",
      "detail_type_desc": "Requested at for sqs notification",
      "detail_desc": "Requested at for sqs notification",
      "detail_data": "2026-01-28T21:08:32Z",
      "created_at": "2026-01-28 21:08:32.269897"
    }
  ],
  "triggered_at": "2026-01-28 21:08:32.271541"
}

# Transform the data
result = transform_alert_to_notification(sample_input)

# Pretty print the result
print(json.dumps(result, indent=2))