-- Insert feed entry for "global batch 57"
INSERT INTO feed.feed (
    feed_type_cd,
    feed_type_cd_type,
    feed_status_id,
    feed_name,
    feed_description,
    feed_tag,
    is_active
) VALUES (
    'BATCH_PROC',
    'FEED_TYPE',
    (SELECT code_id FROM admin.system_codes WHERE common_cd = 'ACTIVE' AND code_type_cd = 'FEED_STATUS'),
    'global batch 57',
    'Global batch processing feed #57',
    'global_batch57',
    TRUE
);

-- Insert environment entry for the feed (DEV environment)
INSERT INTO feed.feed_environment (
    feed_id,
    env_system_cd
) VALUES (
    (SELECT feed_id FROM feed.feed WHERE feed_name = 'global batch 57' AND feed_tag = 'global_batch57'),
    (SELECT code_id FROM admin.system_codes WHERE common_cd = 'DEV' AND code_type_cd = 'FEED_ENVIRONMENT')
);