-- Insert base code types
INSERT INTO admin.code_type (code_type_cd, code_type_description) VALUES
    ('FEED_TYPE', 'Pipeline Type Classifications'),
    ('STATUS', 'Processing Status Codes'),
    ('PRIORITY', 'Priority Levels'),
    ('FEED_STATUS', 'Pipeline Lifecycle Status'),
    ('FEED_ENVIRONMENT', 'Pipeline Execution Environment'),
    ('FEED_RUN_DETAIL_TYPE', 'Pipeline Run Detail Type')
ON CONFLICT (code_type_cd) DO NOTHING;

-- Insert system codes
INSERT INTO admin.system_codes (common_cd, code_type_cd, code_description, sort_order) VALUES
    -- FEED_TYPE
    ('SFTP_FEED', 'FEED_TYPE', 'SFTP based', 1),
    ('API_CALL', 'FEED_TYPE', 'API Data Pipeline', 2),
    ('BATCH_PROC', 'FEED_TYPE', 'Batch Processing Pipeline', 3),

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

    -- FEED_STATUS
    ('ACTIVE', 'FEED_STATUS', 'Active and operational', 1),
    ('IN_DEVELOPMENT', 'FEED_STATUS', 'Currently being built', 2),
    ('INACTIVE', 'FEED_STATUS', 'Disabled or paused', 3),
    ('QA', 'FEED_STATUS', 'In QA / staging phase', 4),
    ('BROKEN', 'FEED_STATUS', 'Not working / broken', 5),

    -- FEED_ENVIRONMENT
    ('DEV', 'FEED_ENVIRONMENT', 'Development Environment', 1),
    ('TEST', 'FEED_ENVIRONMENT', 'Testing Environment', 2),
    ('PROD', 'FEED_ENVIRONMENT', 'Production Environment', 3),

    -- FEED_RUN_DETAIL_TYPE
    ('CLOUDWATCH_LOG_LINK', 'FEED_RUN_DETAIL_TYPE', 'Link to CloudWatch logs', 1),
    ('ECS_CONTAINER_LINK', 'FEED_RUN_DETAIL_TYPE', 'Link to ECS container', 2),
    ('HTML_CHUNK', 'FEED_RUN_DETAIL_TYPE', 'HTML snippet or result', 3),
    ('AWS_CLI_COMMAND', 'FEED_RUN_DETAIL_TYPE', 'AWS cli batch command', 4),
    ('PYTHON_CODE_SNIPPET', 'FEED_RUN_DETAIL_TYPE', 'Python code snippet', 5)


ON CONFLICT (common_cd, code_type_cd) DO NOTHING;
