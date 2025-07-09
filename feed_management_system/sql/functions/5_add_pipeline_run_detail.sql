CREATE OR REPLACE FUNCTION add_pipeline_run_detail(
    p_pipeline_run_id INTEGER,
    p_common_cd VARCHAR(50),
    p_detail_desc TEXT DEFAULT NULL,
    p_detail_data TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_system_code_id INTEGER;
    v_system_code_desc VARCHAR(255);
    v_final_desc TEXT;
    v_detail_id INTEGER;
BEGIN
    -- Resolve the system code based on common_cd and code_type_cd
    SELECT code_id, code_description
    INTO v_system_code_id, v_system_code_desc
    FROM admin.system_codes
    WHERE common_cd = p_common_cd
      AND code_type_cd = 'PIPELINE_RUN_DETAIL_TYPE'
      AND is_active = TRUE;
    
    -- Check if the common_cd exists
    IF v_system_code_id IS NULL THEN
        RAISE EXCEPTION 'Common code "%" does not exist for code type "PIPELINE_RUN_DETAIL_TYPE" or is not active', p_common_cd;
    END IF;
    
    -- Use provided description or fall back to system code description
    IF p_detail_desc IS NULL OR p_detail_desc = '' THEN
        v_final_desc := v_system_code_desc;
    ELSE
        v_final_desc := p_detail_desc;
    END IF;
    
    -- Insert into pipeline_run_details table
    INSERT INTO pipeline.pipeline_run_details (
        pipeline_run_id,
        run_detail_type_cd,
        detail_desc,
        detail_data
    )
    VALUES (
        p_pipeline_run_id,
        v_system_code_id,
        v_final_desc,
        p_detail_data
    )
    RETURNING detail_id INTO v_detail_id;
    
    -- Return the generated detail_id
    RETURN v_detail_id;
    
EXCEPTION
    WHEN foreign_key_violation THEN
        RAISE EXCEPTION 'Invalid pipeline_run_id: %', p_pipeline_run_id;
    WHEN OTHERS THEN
        RAISE;
END;
$$;