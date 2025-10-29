-- Create schemas if they don't exist
CREATE SCHEMA IF NOT EXISTS admin;
CREATE SCHEMA IF NOT EXISTS pipeline;

-- Create code_type table in admin schema
CREATE TABLE IF NOT EXISTS admin.code_type (
    code_type_cd VARCHAR(50) PRIMARY KEY,
    code_type_description VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create system_codes table in admin schema
CREATE TABLE IF NOT EXISTS admin.system_codes (
    code_id SERIAL PRIMARY KEY,
    common_cd VARCHAR(50) NOT NULL,
    code_type_cd VARCHAR(50) NOT NULL,
    code_description VARCHAR(255) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (common_cd, code_type_cd),
    FOREIGN KEY (code_type_cd) REFERENCES admin.code_type(code_type_cd)
);

-- Create pipeline table in pipeline schema
CREATE TABLE IF NOT EXISTS pipeline.pipeline (
    pipeline_id SERIAL PRIMARY KEY,
    pipeline_type_cd VARCHAR(50) NOT NULL,
    pipeline_type_cd_type VARCHAR(50) NOT NULL DEFAULT 'PIPELINE_TYPE',
    pipeline_status_id INTEGER REFERENCES admin.system_codes(code_id),
    pipeline_name VARCHAR(255) NOT NULL,
    pipeline_description TEXT,
    pipeline_tag VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pipeline_type_cd, pipeline_type_cd_type)
    REFERENCES admin.system_codes(common_cd, code_type_cd)
);

-- Drop old table if needed (optional safety)
-- DROP TABLE IF EXISTS pipeline.pipeline_environment;
CREATE TABLE IF NOT EXISTS pipeline.pipeline_environment (
    environment_id SERIAL PRIMARY KEY,
    pipeline_id INTEGER NOT NULL,
    env_system_cd INTEGER NOT NULL,  -- references admin.system_codes(code_id)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pipeline_id) REFERENCES pipeline.pipeline(pipeline_id),
    FOREIGN KEY (env_system_cd) REFERENCES admin.system_codes(code_id)
);


-- Create pipeline_run table in pipeline schema
CREATE TABLE IF NOT EXISTS pipeline.pipeline_run (
    pipeline_run_id SERIAL PRIMARY KEY,
    pipeline_id INTEGER NOT NULL,
    environment_id INTEGER NOT NULL,
    start_dt TIMESTAMP NOT NULL,
    end_dt TIMESTAMP,
    description TEXT,
    status_cd VARCHAR(50) NOT NULL,
    status_cd_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pipeline_id) REFERENCES pipeline.pipeline(pipeline_id),
    FOREIGN KEY (environment_id) REFERENCES pipeline.pipeline_environment(environment_id),
    FOREIGN KEY (status_cd, status_cd_type)
        REFERENCES admin.system_codes(common_cd, code_type_cd)
);

-- Create pipeline_run_details table in pipeline schema
CREATE TABLE IF NOT EXISTS pipeline.pipeline_run_details (
    detail_id SERIAL PRIMARY KEY,
    parent_detail_id INTEGER,
    pipeline_run_id INTEGER NOT NULL,
    run_detail_type_cd INTEGER NOT NULL,  -- references admin.system_codes(code_id)
    detail_desc TEXT NOT NULL,
    detail_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_detail_id) REFERENCES pipeline.pipeline_run_details(detail_id),
    FOREIGN KEY (pipeline_run_id) REFERENCES pipeline.pipeline_run(pipeline_run_id),
    FOREIGN KEY (run_detail_type_cd) REFERENCES admin.system_codes(code_id)    
);

-- Create pipeline_details table in pipeline schema
CREATE TABLE IF NOT EXISTS pipeline.pipeline_details (
    detail_id SERIAL PRIMARY KEY,
    parent_detail_id INTEGER,
    pipeline_id INTEGER NOT NULL,
    environment_id INTEGER NOT NULL,
    detail_type_cd VARCHAR(50) NOT NULL,
    detail_type_cd_type VARCHAR(50) NOT NULL,
    detail_desc VARCHAR(500) NOT NULL,
    detail_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_detail_id) REFERENCES pipeline.pipeline_details(detail_id),
    FOREIGN KEY (pipeline_id) REFERENCES pipeline.pipeline(pipeline_id),
    FOREIGN KEY (environment_id) REFERENCES pipeline.pipeline_environment(environment_id),
    FOREIGN KEY (detail_type_cd, detail_type_cd_type)
        REFERENCES admin.system_codes(common_cd, code_type_cd)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_pipeline_run_pipeline_id ON pipeline.pipeline_run(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_run_status ON pipeline.pipeline_run(status_cd);
CREATE INDEX IF NOT EXISTS idx_pipeline_run_start_dt ON pipeline.pipeline_run(start_dt);
CREATE INDEX IF NOT EXISTS idx_pipeline_run_details_pipeline_run_id ON pipeline.pipeline_run_details(pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_run_details_parent ON pipeline.pipeline_run_details(parent_detail_id);
CREATE INDEX IF NOT EXISTS idx_system_codes_type ON admin.system_codes(code_type_cd);


-- ----------------------------------------------------------------------------
-- 3. Create alert_definition table
-- ----------------------------------------------------------------------------
-- Main table defining alerts for specific pipeline/environment combinations
CREATE TABLE IF NOT EXISTS pipeline.alert_definition (
    alert_definition_id SERIAL PRIMARY KEY,
    pipeline_id INTEGER NOT NULL,
    environment_id INTEGER NOT NULL,
    alert_type_cd INTEGER NOT NULL,  -- references system_codes (ALERT_TYPE)
    alert_name VARCHAR(255) NOT NULL,
    alert_description TEXT,
    severity_cd INTEGER NOT NULL,  -- references system_codes (ALERT_SEVERITY)
    notification_type_cd INTEGER NOT NULL,  -- references system_codes (ALERT_NOTIFICATION_TYPE)
    recipient_list TEXT NOT NULL,  -- Comma-delimited email addresses or Slack channels
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    
    FOREIGN KEY (pipeline_id) REFERENCES pipeline.pipeline(pipeline_id),
    FOREIGN KEY (environment_id) REFERENCES pipeline.pipeline_environment(environment_id),
    FOREIGN KEY (alert_type_cd) REFERENCES admin.system_codes(code_id),
    FOREIGN KEY (severity_cd) REFERENCES admin.system_codes(code_id),
    FOREIGN KEY (notification_type_cd) REFERENCES admin.system_codes(code_id),
    
    -- Ensure unique alert definitions per pipeline/environment/type
    UNIQUE (pipeline_id, environment_id, alert_type_cd, alert_name)
);

-- ----------------------------------------------------------------------------
-- 4. Create alert_definition_config table
-- ----------------------------------------------------------------------------
-- Flexible key-value configuration for each alert definition
-- This allows different alert types to have different configuration needs
CREATE TABLE IF NOT EXISTS pipeline.alert_definition_config (
    config_id SERIAL PRIMARY KEY,
    alert_definition_id INTEGER NOT NULL,
    config_key VARCHAR(100) NOT NULL,
    config_value TEXT NOT NULL,
    config_data_type VARCHAR(50) DEFAULT 'STRING',  -- STRING, INTEGER, DECIMAL, BOOLEAN, JSON
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (alert_definition_id) REFERENCES pipeline.alert_definition(alert_definition_id) ON DELETE CASCADE,
    
    -- Ensure unique keys per alert definition
    UNIQUE (alert_definition_id, config_key)
);

-- ----------------------------------------------------------------------------
-- 5. Create cadence_alert_config table
-- ----------------------------------------------------------------------------
-- Specific configuration for cadence-based alerts
CREATE TABLE IF NOT EXISTS pipeline.cadence_alert_config (
    cadence_config_id SERIAL PRIMARY KEY,
    alert_definition_id INTEGER NOT NULL,
    cadence_type_cd INTEGER NOT NULL,  -- references system_codes (CADENCE_TYPE)
    
    -- For HISTORICAL type
    lookback_period INTEGER,  -- How many runs to look back
    lookback_time_value INTEGER,  -- e.g., 30
    lookback_time_unit_cd INTEGER,  -- references system_codes (TIME_UNIT) - e.g., DAYS
    deviation_threshold DECIMAL(5,2),  -- Percentage deviation allowed (e.g., 20.00 = 20%)
    
    -- For FIXED_SCHEDULE type
    expected_completion_time TIME,  -- Expected completion time (UTC)
    expected_day_of_week INTEGER,  -- 0=Sunday, 1=Monday, etc. (NULL if not weekly)
    expected_day_of_month INTEGER,  -- 1-31 (NULL if not monthly)
    tolerance_minutes INTEGER,  -- Grace period in minutes
    
    -- For CUSTOM_EXPRESSION type
    cron_expression VARCHAR(100),  -- Cron-like expression
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (alert_definition_id) REFERENCES pipeline.alert_definition(alert_definition_id) ON DELETE CASCADE,
    FOREIGN KEY (cadence_type_cd) REFERENCES admin.system_codes(code_id),
    FOREIGN KEY (lookback_time_unit_cd) REFERENCES admin.system_codes(code_id),
    
    -- Only one cadence config per alert definition
    UNIQUE (alert_definition_id)
);

-- ----------------------------------------------------------------------------
-- 6. Create data_threshold_config table
-- ----------------------------------------------------------------------------
-- Configuration for data threshold alerts
CREATE TABLE IF NOT EXISTS pipeline.data_threshold_config (
    threshold_config_id SERIAL PRIMARY KEY,
    alert_definition_id INTEGER NOT NULL,
    threshold_name VARCHAR(100) NOT NULL,  -- e.g., "row_count", "file_size", "error_rate"
    
    -- Threshold boundaries
    min_value DECIMAL(20,4),
    max_value DECIMAL(20,4),
    expected_value DECIMAL(20,4),  -- Optional expected value
    deviation_percent DECIMAL(5,2),  -- Allowed deviation percentage
    
    -- Comparison operators
    comparison_operator VARCHAR(20),  -- GT, LT, GTE, LTE, EQ, BETWEEN, DEVIATION
    
    -- Historical comparison
    use_historical_baseline BOOLEAN DEFAULT FALSE,
    historical_lookback_runs INTEGER,  -- Number of runs to average
    
    -- Where to get the value from
    value_source VARCHAR(50) NOT NULL,  -- RUN_DETAIL, CUSTOM_QUERY, EXTERNAL_API
    value_source_key VARCHAR(255),  -- e.g., detail_type_cd for RUN_DETAIL
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (alert_definition_id) REFERENCES pipeline.alert_definition(alert_definition_id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- 7. Create processing_time_config table
-- ----------------------------------------------------------------------------
-- Configuration for processing time alerts
CREATE TABLE IF NOT EXISTS pipeline.processing_time_config (
    processing_config_id SERIAL PRIMARY KEY,
    alert_definition_id INTEGER NOT NULL,
    
    -- Historical baseline
    use_historical_baseline BOOLEAN DEFAULT TRUE,
    historical_lookback_runs INTEGER DEFAULT 20,  -- Number of runs to average
    historical_lookback_days INTEGER,  -- Alternative: lookback by time period
    
    -- Fixed threshold
    max_duration_minutes INTEGER,  -- Fixed maximum duration
    
    -- Threshold calculation
    deviation_multiplier DECIMAL(5,2),  -- e.g., 1.5 = 150% of average
    deviation_percent DECIMAL(5,2),  -- e.g., 50.00 = 50% over average
    
    -- Minimum duration filter (ignore very short runs)
    min_duration_minutes INTEGER DEFAULT 1,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (alert_definition_id) REFERENCES pipeline.alert_definition(alert_definition_id) ON DELETE CASCADE,
    
    UNIQUE (alert_definition_id)
);

-- ----------------------------------------------------------------------------
-- 8. Create alert_instance table
-- ----------------------------------------------------------------------------
-- Tracks actual triggered alerts
CREATE TABLE IF NOT EXISTS pipeline.alert_instance (
    alert_instance_id SERIAL PRIMARY KEY,
    alert_definition_id INTEGER NOT NULL,
    pipeline_run_id INTEGER,  -- NULL if alert not tied to specific run
    
    triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(100),
    
    alert_status_cd INTEGER NOT NULL,  -- references system_codes (ALERT_STATUS)
    
    -- Alert details
    alert_message TEXT NOT NULL,
    alert_data JSONB,  -- Store detailed alert data (actual vs expected values, etc.)
    
    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMP,
    notification_channels TEXT[],  -- Array of channels: email, slack, pagerduty, etc.
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (alert_definition_id) REFERENCES pipeline.alert_definition(alert_definition_id),
    FOREIGN KEY (pipeline_run_id) REFERENCES pipeline.pipeline_run(pipeline_run_id),
    FOREIGN KEY (alert_status_cd) REFERENCES admin.system_codes(code_id)
);

-- ----------------------------------------------------------------------------
-- 9. Create alert_history table
-- ----------------------------------------------------------------------------
-- Audit trail for alert state changes
CREATE TABLE IF NOT EXISTS pipeline.alert_history (
    history_id SERIAL PRIMARY KEY,
    alert_instance_id INTEGER NOT NULL,
    status_from_cd INTEGER,  -- Previous status
    status_to_cd INTEGER NOT NULL,  -- New status
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(100),
    change_comment TEXT,
    
    FOREIGN KEY (alert_instance_id) REFERENCES pipeline.alert_instance(alert_instance_id),
    FOREIGN KEY (status_from_cd) REFERENCES admin.system_codes(code_id),
    FOREIGN KEY (status_to_cd) REFERENCES admin.system_codes(code_id)
);

-- ----------------------------------------------------------------------------
-- 10. Create alert_suppression table
-- ----------------------------------------------------------------------------
-- Manage temporary alert suppressions (maintenance windows, known issues)
CREATE TABLE IF NOT EXISTS pipeline.alert_suppression (
    suppression_id SERIAL PRIMARY KEY,
    alert_definition_id INTEGER NOT NULL,
    
    suppress_from TIMESTAMP NOT NULL,
    suppress_until TIMESTAMP NOT NULL,
    
    suppression_reason TEXT NOT NULL,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    is_active BOOLEAN DEFAULT TRUE,
    
    FOREIGN KEY (alert_definition_id) REFERENCES pipeline.alert_definition(alert_definition_id)
);

-- ----------------------------------------------------------------------------
-- 11. Create indexes for performance
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_alert_definition_pipeline ON pipeline.alert_definition(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_alert_definition_environment ON pipeline.alert_definition(environment_id);
CREATE INDEX IF NOT EXISTS idx_alert_definition_enabled ON pipeline.alert_definition(is_enabled);
CREATE INDEX IF NOT EXISTS idx_alert_definition_type ON pipeline.alert_definition(alert_type_cd);

CREATE INDEX IF NOT EXISTS idx_alert_instance_definition ON pipeline.alert_instance(alert_definition_id);
CREATE INDEX IF NOT EXISTS idx_alert_instance_run ON pipeline.alert_instance(pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_alert_instance_status ON pipeline.alert_instance(alert_status_cd);
CREATE INDEX IF NOT EXISTS idx_alert_instance_triggered ON pipeline.alert_instance(triggered_at);

CREATE INDEX IF NOT EXISTS idx_alert_history_instance ON pipeline.alert_history(alert_instance_id);
CREATE INDEX IF NOT EXISTS idx_alert_suppression_active ON pipeline.alert_suppression(alert_definition_id, is_active, suppress_from, suppress_until);

-- JSONB index for alert_data queries
CREATE INDEX IF NOT EXISTS idx_alert_instance_data ON pipeline.alert_instance USING gin(alert_data);

-- ----------------------------------------------------------------------------
-- 12. Add helpful comments
-- ----------------------------------------------------------------------------
COMMENT ON TABLE pipeline.alert_definition IS 'Defines alert rules for pipeline/environment combinations with notification settings';
COMMENT ON TABLE pipeline.alert_definition_config IS 'Flexible key-value configuration for alerts';
COMMENT ON TABLE pipeline.cadence_alert_config IS 'Configuration for cadence-based alerts';
COMMENT ON TABLE pipeline.data_threshold_config IS 'Configuration for data threshold alerts';
COMMENT ON TABLE pipeline.processing_time_config IS 'Configuration for processing time alerts';
COMMENT ON TABLE pipeline.alert_instance IS 'Records of triggered alerts';
COMMENT ON TABLE pipeline.alert_history IS 'Audit trail of alert status changes';
COMMENT ON TABLE pipeline.alert_suppression IS 'Temporary alert suppression rules';

COMMENT ON COLUMN pipeline.alert_definition.notification_type_cd IS 'Type of notification: EMAIL or SLACK';
COMMENT ON COLUMN pipeline.alert_definition.recipient_list IS 'Comma-delimited list of email addresses (for EMAIL) or Slack channels (for SLACK), e.g., "user1@company.com,user2@company.com" or "#alerts,#data-team"';
COMMENT ON COLUMN pipeline.cadence_alert_config.deviation_threshold IS 'Percentage deviation allowed from historical pattern (e.g., 20.00 = 20%)';
COMMENT ON COLUMN pipeline.data_threshold_config.comparison_operator IS 'Valid values: GT, LT, GTE, LTE, EQ, BETWEEN, DEVIATION';
COMMENT ON COLUMN pipeline.alert_instance.alert_data IS 'JSONB field storing detailed alert context: actual values, expected values, calculations, etc.';
