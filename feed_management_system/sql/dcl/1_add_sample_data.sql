-- Insert base code types
INSERT INTO admin.code_type (code_type_cd, code_type_description) VALUES
    ('PIPELINE_TYPE', 'Pipeline Type Classifications'),
    ('STATUS', 'Processing Status Codes'),
    ('PRIORITY', 'Priority Levels'),
    ('PIPELINE_STATUS', 'Pipeline Lifecycle Status'),
    ('PIPELINE_ENVIRONMENT', 'Pipeline Execution Environment'),
    ('PIPELINE_RUN_DETAIL_TYPE', 'Pipeline Run Detail Type')
ON CONFLICT (code_type_cd) DO NOTHING;

-- Insert system codes
INSERT INTO admin.system_codes (common_cd, code_type_cd, code_description, sort_order) VALUES
    -- PIPELINE_TYPE
    ('SFTP_PIPELINE', 'PIPELINE_TYPE', 'SFTP based', 1),
    ('API_CALL', 'PIPELINE_TYPE', 'API Data Pipeline', 2),
    ('BATCH_PROC', 'PIPELINE_TYPE', 'Batch Processing Pipeline', 3),

    -- STATUS
    ('PENDING', 'STATUS', 'Pending Execution', 1),
    ('RUNNING', 'STATUS', 'Currently Running', 2),
    ('COMPLETED', 'STATUS', 'Successfully Completed', 3),
    ('FAILED', 'STATUS', 'Failed with Errors', 4),
    ('CANCELLED', 'STATUS', 'Cancelled by User', 5),

    -- PRIORITY
    ('HIGH', 'PRIORITY', 'High Priority', 1),
    ('MEDIUM', 'PRIORITY', 'Medium Priority', 2),
    ('LOW', 'PRIORITY', 'Low Priority', 3),

    -- PIPELINE_STATUS
    ('ACTIVE', 'PIPELINE_STATUS', 'Active and operational', 1),
    ('IN_DEVELOPMENT', 'PIPELINE_STATUS', 'Currently being built', 2),
    ('INACTIVE', 'PIPELINE_STATUS', 'Disabled or paused', 3),
    ('QA', 'PIPELINE_STATUS', 'In QA / staging phase', 4),
    ('BROKEN', 'PIPELINE_STATUS', 'Not working / broken', 5),

    -- PIPELINE_ENVIRONMENT
    ('DEV', 'PIPELINE_ENVIRONMENT', 'Development Environment', 1),
    ('TEST', 'PIPELINE_ENVIRONMENT', 'Testing Environment', 2),
    ('PROD', 'PIPELINE_ENVIRONMENT', 'Production Environment', 3),

    -- PIPELINE_RUN_DETAIL_TYPE
    ('CLOUDWATCH_LOG_LINK', 'PIPELINE_RUN_DETAIL_TYPE', 'Link to CloudWatch logs', 1),
    ('ECS_CONTAINER_LINK', 'PIPELINE_RUN_DETAIL_TYPE', 'Link to ECS container', 2),
    ('HTML_CHUNK', 'PIPELINE_RUN_DETAIL_TYPE', 'HTML snippet or result', 3),
    ('AWS_CLI_COMMAND', 'PIPELINE_RUN_DETAIL_TYPE', 'AWS cli batch command', 4),
    ('PYTHON_CODE_SNIPPET', 'PIPELINE_RUN_DETAIL_TYPE', 'Python code snippet', 5),
    ('JIRA_MAINT_PARENT_TICKET', 'PIPELINE_RUN_DETAIL_TYPE', 'Pipeline maint jira ticket.', 6),
    ('TOTAL_PROCESSED_COUNT', 'PIPELINE_RUN_DETAIL_TYPE', 'Total count processed.', 7)


ON CONFLICT (common_cd, code_type_cd) DO NOTHING;


-- ============================================================================
-- ALERT SYSTEM DATA MODEL EXTENSION
-- ============================================================================
-- This extends the existing pipeline schema to support comprehensive alerting
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Add new code types for alerts
-- ----------------------------------------------------------------------------
INSERT INTO admin.code_type (code_type_cd, code_type_description) VALUES
    ('ALERT_TYPE', 'Types of alerts that can be defined'),
    ('ALERT_SEVERITY', 'Severity levels for alerts'),
    ('ALERT_STATUS', 'Current status of alert instances'),
    ('ALERT_NOTIFICATION_TYPE', 'Types of notification channels for alerts'),
    ('CADENCE_TYPE', 'Types of cadence definitions (historical vs fixed)'),
    ('TIME_UNIT', 'Time units for cadence and thresholds')
ON CONFLICT (code_type_cd) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2. Add system codes for alert types
-- ----------------------------------------------------------------------------
INSERT INTO admin.system_codes (common_cd, code_type_cd, code_description, sort_order) VALUES
    -- ALERT_TYPE
    ('COMPLETION_ALERT', 'ALERT_TYPE', 'Pipeline execution cadence monitoring', 1),
    ('CADENCE_ALERT', 'ALERT_TYPE', 'Pipeline execution cadence monitoring', 2),
    ('DATA_THRESHOLD', 'ALERT_TYPE', 'Data volume/quality threshold monitoring', 3),
    ('HARD_FAILURE', 'ALERT_TYPE', 'Pipeline execution failure detection', 4),
    ('PROCESSING_TIME', 'ALERT_TYPE', 'Pipeline runtime duration monitoring', 5),

    -- ALERT_SEVERITY
    ('CRITICAL', 'ALERT_SEVERITY', 'Critical - immediate action required', 1),
    ('HIGH', 'ALERT_SEVERITY', 'High - urgent attention needed', 2),
    ('MEDIUM', 'ALERT_SEVERITY', 'Medium - investigate soon', 3),
    ('LOW', 'ALERT_SEVERITY', 'Low - informational', 4),

    -- ALERT_STATUS
    ('ACTIVE', 'ALERT_STATUS', 'Alert is currently active/triggered', 1),
    ('ACKNOWLEDGED', 'ALERT_STATUS', 'Alert has been acknowledged', 2),
    ('RESOLVED', 'ALERT_STATUS', 'Alert condition resolved', 3),
    ('SUPPRESSED', 'ALERT_STATUS', 'Alert temporarily suppressed', 4),
    ('CLOSED', 'ALERT_STATUS', 'Alert closed/archived', 5),

    -- ALERT_NOTIFICATION_TYPE
    ('EMAIL', 'ALERT_NOTIFICATION_TYPE', 'Email notification', 1),
    ('SLACK', 'ALERT_NOTIFICATION_TYPE', 'Slack channel notification', 2),

    -- CADENCE_TYPE
    ('HISTORICAL', 'CADENCE_TYPE', 'Based on historical run patterns', 1),
    ('FIXED_SCHEDULE', 'CADENCE_TYPE', 'Based on fixed schedule', 2),
    ('CUSTOM_EXPRESSION', 'CADENCE_TYPE', 'Custom cron-like expression', 3),

    -- TIME_UNIT
    ('MINUTES', 'TIME_UNIT', 'Minutes', 1),
    ('HOURS', 'TIME_UNIT', 'Hours', 2),
    ('DAYS', 'TIME_UNIT', 'Days', 3),
    ('WEEKS', 'TIME_UNIT', 'Weeks', 4),
    ('MONTHS', 'TIME_UNIT', 'Months', 5)
ON CONFLICT (common_cd, code_type_cd) DO NOTHING;
