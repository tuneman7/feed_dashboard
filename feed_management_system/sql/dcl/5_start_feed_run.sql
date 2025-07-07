-- Create stored procedure: start_feed_run
CREATE OR REPLACE FUNCTION start_feed_run(
    p_environment VARCHAR(10),
    p_feed_tag VARCHAR(255)
) RETURNS INTEGER AS $$
DECLARE
    v_feed_id INTEGER;
    v_environment_id INTEGER;
    v_env_system_cd INTEGER;
    v_feed_status_id INTEGER;
    v_feed_run_id INTEGER;
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
    
    -- Get default feed status (ACTIVE) for new feeds
    SELECT code_id INTO v_feed_status_id
    FROM admin.system_codes
    WHERE common_cd = 'ACTIVE'
    AND code_type_cd = 'FEED_STATUS';
    
    IF v_feed_status_id IS NULL THEN
        RAISE EXCEPTION 'ACTIVE feed status code not found in system_codes';
    END IF;
    
    -- Get default status for feed runs (RUNNING)
    SELECT code_id INTO v_status_cd_id
    FROM admin.system_codes
    WHERE common_cd = 'RUNNING'
    AND code_type_cd = 'STATUS';
    
    IF v_status_cd_id IS NULL THEN
        RAISE EXCEPTION 'RUNNING status code not found in system_codes';
    END IF;
    
    -- Check if feed exists
    SELECT feed_id INTO v_feed_id
    FROM feed.feed
    WHERE feed_tag = p_feed_tag;
    
    -- If feed doesn't exist, create it
    IF v_feed_id IS NULL THEN
        INSERT INTO feed.feed (
            feed_type_cd,
            feed_type_cd_type,
            feed_status_id,
            feed_name,
            feed_description,
            feed_tag,
            is_active
        ) VALUES (
            'SFTP_FEED',
            'FEED_TYPE',
            v_feed_status_id,
            'Auto Created for: ' || p_feed_tag,
            'Auto Created for: ' || p_feed_tag,
            p_feed_tag,
            TRUE
        ) RETURNING feed_id INTO v_feed_id;
        
        RAISE NOTICE 'Created new feed with ID: % for tag: %', v_feed_id, p_feed_tag;
    END IF;
    
    -- Check if feed_environment entry exists for this feed and environment
    SELECT environment_id INTO v_environment_id
    FROM feed.feed_environment
    WHERE feed_id = v_feed_id
    AND env_system_cd = v_env_system_cd;
    
    -- If feed_environment doesn't exist, create it
    IF v_environment_id IS NULL THEN
        INSERT INTO feed.feed_environment (
            feed_id,
            env_system_cd
        ) VALUES (
            v_feed_id,
            v_env_system_cd
        ) RETURNING environment_id INTO v_environment_id;
        
        RAISE NOTICE 'Created feed environment entry with ID: % for feed: % in environment: %',
                     v_environment_id, v_feed_id, p_environment;
    END IF;
    
    -- Create feed run entry
    INSERT INTO feed.feed_run (
        feed_id,
        environment_id,
        start_dt,
        end_dt,
        description,
        status_cd,
        status_cd_type
    ) VALUES (
        v_feed_id,
        v_environment_id,
        CURRENT_TIMESTAMP,
        NULL,
        'Feed run started for ' || p_feed_tag || ' in ' || p_environment || ' environment',
        'RUNNING',
        'STATUS'
    ) RETURNING feed_run_id INTO v_feed_run_id;
    
    RAISE NOTICE 'Created feed run with ID: % for feed: % in environment: %',
                 v_feed_run_id, v_feed_id, p_environment;
    
    -- Return the feed_run_id
    RETURN v_feed_run_id;
    
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in start_feed_run: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Example usage:
-- SELECT start_feed_run('dev', 'test_feed_123');
-- SELECT start_feed_run('prod', 'global_batch57');