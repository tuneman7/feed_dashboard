-- Create stored procedure: complete_feed_run
CREATE OR REPLACE FUNCTION complete_feed_run(
    p_feed_run_id INTEGER,
    p_status VARCHAR(10)
) RETURNS BOOLEAN AS $$
DECLARE
    v_status_code VARCHAR(50);
    v_feed_run_exists BOOLEAN := FALSE;
BEGIN
    -- Validate status parameter
    IF LOWER(p_status) NOT IN ('success', 'failure') THEN
        RAISE EXCEPTION 'Invalid status. Must be success or failure';
    END IF;
    
    -- Check if feed_run_id exists
    SELECT EXISTS(
        SELECT 1 FROM feed.feed_run 
        WHERE feed_run_id = p_feed_run_id
    ) INTO v_feed_run_exists;
    
    IF NOT v_feed_run_exists THEN
        RAISE EXCEPTION 'Feed run ID % not found', p_feed_run_id;
    END IF;
    
    -- Map status to system code
    IF LOWER(p_status) = 'success' THEN
        v_status_code := 'COMPLETED';
    ELSE
        v_status_code := 'FAILED';
    END IF;
    
    -- Verify the status code exists in system_codes
    IF NOT EXISTS(
        SELECT 1 FROM admin.system_codes 
        WHERE common_cd = v_status_code 
        AND code_type_cd = 'STATUS'
    ) THEN
        RAISE EXCEPTION 'Status code % not found in system_codes', v_status_code;
    END IF;
    
    -- Update the feed_run record
    UPDATE feed.feed_run 
    SET 
        end_dt = CURRENT_TIMESTAMP,
        status_cd = v_status_code,
        updated_at = CURRENT_TIMESTAMP
    WHERE feed_run_id = p_feed_run_id;
    
    RAISE NOTICE 'Feed run ID % completed with status: %', p_feed_run_id, v_status_code;
    
    -- Return success
    RETURN TRUE;
    
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in complete_feed_run: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Example usage:
-- SELECT complete_feed_run(123, 'success');
-- SELECT complete_feed_run(124, 'failure');