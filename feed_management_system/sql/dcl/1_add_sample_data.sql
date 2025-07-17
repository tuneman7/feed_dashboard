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
    ('TOTAL_PROCESSED_COUNT', 'PIPELINE_RUN_DETAIL_TYPE', 'Pipeline maint jira ticket.', 7)


ON CONFLICT (common_cd, code_type_cd) DO NOTHING;
