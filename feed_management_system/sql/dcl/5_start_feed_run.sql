-- Create stored procedure: start_pipeline_run
CREATE OR REPLACE FUNCTION start_pipeline_run(
    p_environment VARCHAR(10),
    p_pipeline_tag VARCHAR(255)
) RETURNS INTEGER AS $$
DECLARE
    v_pipeline_id INTEGER;
    v_environment_id INTEGER;
    v_env_system_cd INTEGER;
    v_pipeline_status_id INTEGER;
    v_pipeline_run_id INTEGER;
    v_status_cd_id INTEGER;
BEGIN
    -- Validate environment parameter
    IF p_environment NOT IN ('dev', 'test', 'prod') THEN
        RAISE EXCEPTION 'Invalid environment. Must be dev, test, or prod';
    END IF;
    
    -- Get environment system code ID
    SELECT code_id INTO v_env_system_cd
    FROM admin.system_codes
    WHERE UPPER(common_cd) = UPPER(p_environment)
    AND code_type_cd = 'FEED_ENVIRONMENT';
    
    IF v_env_system_cd IS NULL THEN
        RAISE EXCEPTION 'Environment system code not found for: %', p_environment;
    END IF;
    
    -- Get default pipeline status (ACTIVE) for new pipelines
    SELECT code_id INTO v_pipeline_status_id
    FROM admin.system_codes
    WHERE common_cd = 'ACTIVE'
    AND code_type_cd = 'FEED_STATUS';
    
    IF v_pipeline_status_id IS NULL THEN
        RAISE EXCEPTION 'ACTIVE pipeline status code not found in system_codes';
    END IF;
    
    -- Get default status for pipeline runs (RUNNING)
    SELECT code_id INTO v_status_cd_id
    FROM admin.system_codes
    WHERE common_cd = 'RUNNING'
    AND code_type_cd = 'STATUS';
    
    IF v_status_cd_id IS NULL THEN
        RAISE EXCEPTION 'RUNNING status code not found in system_codes';
    END IF;
    
    -- Check if pipeline exists
    SELECT pipeline_id INTO v_pipeline_id
    FROM pipeline.pipeline
    WHERE pipeline_tag = p_pipeline_tag;
    
    -- If pipeline doesn't exist, create it
    IF v_pipeline_id IS NULL THEN
        INSERT INTO pipeline.pipeline (
            pipeline_type_cd,
            pipeline_type_cd_type,
            pipeline_status_id,
            pipeline_name,
            pipeline_description,
            pipeline_tag,
            is_active
        ) VALUES (
            'SFTP_FEED',
            'FEED_TYPE',
            v_pipeline_status_id,
            'Auto Created for: ' || p_pipeline_tag,
            'Auto Created for: ' || p_pipeline_tag,
            p_pipeline_tag,
            TRUE
        ) RETURNING pipeline_id INTO v_pipeline_id;
        
        RAISE NOTICE 'Created new pipeline with ID: % for tag: %', v_pipeline_id, p_pipeline_tag;
    END IF;
    
    -- Check if pipeline_environment entry exists for this pipeline and environment
    SELECT environment_id INTO v_environment_id
    FROM pipeline.pipeline_environment
    WHERE pipeline_id = v_pipeline_id
    AND env_system_cd = v_env_system_cd;
    
    -- If pipeline_environment doesn't exist, create it
    IF v_environment_id IS NULL THEN
        INSERT INTO pipeline.pipeline_environment (
            pipeline_id,
            env_system_cd
        ) VALUES (
            v_pipeline_id,
            v_env_system_cd
        ) RETURNING environment_id INTO v_environment_id;
        
        RAISE NOTICE 'Created pipeline environment entry with ID: % for pipeline: % in environment: %',
                     v_environment_id, v_pipeline_id, p_environment;
    END IF;
    
    -- Create pipeline run entry
    INSERT INTO pipeline.pipeline_run (
        pipeline_id,
        environment_id,
        start_dt,
        end_dt,
        description,
        status_cd,
        status_cd_type
    ) VALUES (
        v_pipeline_id,
        v_environment_id,
        CURRENT_TIMESTAMP,
        NULL,
        'Pipeline run started for ' || p_pipeline_tag || ' in ' || p_environment || ' environment',
        'RUNNING',
        'STATUS'
    ) RETURNING pipeline_run_id INTO v_pipeline_run_id;
    
    RAISE NOTICE 'Created pipeline run with ID: % for pipeline: % in environment: %',
                 v_pipeline_run_id, v_pipeline_id, p_environment;
    
    -- Return the pipeline_run_id
    RETURN v_pipeline_run_id;
    
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in start_pipeline_run: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Example usage:
-- SELECT start_pipeline_run('dev', 'test_pipeline_123');
-- SELECT start_pipeline_run('prod', 'global_batch57');