-- Insert pipeline entry for "global batch 57"
INSERT INTO pipeline.pipeline (
    pipeline_type_cd,
    pipeline_type_cd_type,
    pipeline_status_id,
    pipeline_name,
    pipeline_description,
    pipeline_tag,
    is_active
) VALUES (
    'BATCH_PROC',
    'FEED_TYPE',
    (SELECT code_id FROM admin.system_codes WHERE common_cd = 'ACTIVE' AND code_type_cd = 'FEED_STATUS'),
    'global batch 57',
    'Global batch processing pipeline #57',
    'global_batch57',
    TRUE
);

-- Insert environment entry for the pipeline (DEV environment)
INSERT INTO pipeline.pipeline_environment (
    pipeline_id,
    env_system_cd
) VALUES (
    (SELECT pipeline_id FROM pipeline.pipeline WHERE pipeline_name = 'global batch 57' AND pipeline_tag = 'global_batch57'),
    (SELECT code_id FROM admin.system_codes WHERE common_cd = 'DEV' AND code_type_cd = 'FEED_ENVIRONMENT')
);