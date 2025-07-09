-- Create stored procedure: complete_pipeline_run
CREATE OR REPLACE FUNCTION complete_pipeline_run(
    p_pipeline_run_id INTEGER,
    p_status VARCHAR(10)
) RETURNS BOOLEAN AS $$
DECLARE
    v_status_code VARCHAR(50);
    v_pipeline_run_exists BOOLEAN := FALSE;
BEGIN
    -- Validate status parameter
    IF LOWER(p_status) NOT IN ('success', 'failure') THEN
        RAISE EXCEPTION 'Invalid status. Must be success or failure';
    END IF;
    
    -- Check if pipeline_run_id exists
    SELECT EXISTS(
        SELECT 1 FROM pipeline.pipeline_run 
        WHERE pipeline_run_id = p_pipeline_run_id
    ) INTO v_pipeline_run_exists;
    
    IF NOT v_pipeline_run_exists THEN
        RAISE EXCEPTION 'Pipeline run ID % not found', p_pipeline_run_id;
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
    
    -- Update the pipeline_run record
    UPDATE pipeline.pipeline_run 
    SET 
        end_dt = CURRENT_TIMESTAMP,
        status_cd = v_status_code,
        updated_at = CURRENT_TIMESTAMP
    WHERE pipeline_run_id = p_pipeline_run_id;
    
    RAISE NOTICE 'Pipeline run ID % completed with status: %', p_pipeline_run_id, v_status_code;
    
    -- Return success
    RETURN TRUE;
    
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in complete_pipeline_run: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Example usage:
-- SELECT complete_pipeline_run(123, 'success');
-- SELECT complete_pipeline_run(124, 'failure');