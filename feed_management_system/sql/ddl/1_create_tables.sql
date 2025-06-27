-- Create schemas if they don't exist
CREATE SCHEMA IF NOT EXISTS admin;
CREATE SCHEMA IF NOT EXISTS feed;

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

-- Create feed table in feed schema
CREATE TABLE IF NOT EXISTS feed.feed (
    feed_id SERIAL PRIMARY KEY,
    feed_type_cd VARCHAR(50) NOT NULL,
    feed_type_cd_type VARCHAR(50) NOT NULL DEFAULT 'FEED_TYPE',
    feed_status_id INTEGER REFERENCES admin.system_codes(code_id),
    feed_name VARCHAR(255) NOT NULL,
    feed_description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feed_type_cd, feed_type_cd_type)
        REFERENCES admin.system_codes(common_cd, code_type_cd)
);

-- Drop old table if needed (optional safety)
-- DROP TABLE IF EXISTS feed.feed_environment;
CREATE TABLE IF NOT EXISTS feed.feed_environment (
    environment_id SERIAL PRIMARY KEY,
    feed_id INTEGER NOT NULL,
    env_system_cd INTEGER NOT NULL,  -- references admin.system_codes(code_id)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feed_id) REFERENCES feed.feed(feed_id),
    FOREIGN KEY (env_system_cd) REFERENCES admin.system_codes(code_id)
);


-- Create feed_run table in feed schema
CREATE TABLE IF NOT EXISTS feed.feed_run (
    feed_run_id SERIAL PRIMARY KEY,
    feed_id INTEGER NOT NULL,
    environment_id INTEGER NOT NULL,
    start_dt TIMESTAMP NOT NULL,
    end_dt TIMESTAMP,
    description TEXT,
    status_cd VARCHAR(50) NOT NULL,
    status_cd_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feed_id) REFERENCES feed.feed(feed_id),
    FOREIGN KEY (environment_id) REFERENCES feed.feed_environment(environment_id),
    FOREIGN KEY (status_cd, status_cd_type)
        REFERENCES admin.system_codes(common_cd, code_type_cd)
);

-- Create feed_run_details table in feed schema
CREATE TABLE IF NOT EXISTS feed.feed_run_details (
    detail_id SERIAL PRIMARY KEY,
    parent_detail_id INTEGER,
    feed_run_id INTEGER NOT NULL,
    detail_desc TEXT NOT NULL,
    detail_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_detail_id) REFERENCES feed.feed_run_details(detail_id),
    FOREIGN KEY (feed_run_id) REFERENCES feed.feed_run(feed_run_id)
);

-- Create feed_details table in feed schema
CREATE TABLE IF NOT EXISTS feed.feed_details (
    detail_id SERIAL PRIMARY KEY,
    parent_detail_id INTEGER,
    feed_id INTEGER NOT NULL,
    environment_id INTEGER NOT NULL,
    detail_type_cd VARCHAR(50) NOT NULL,
    detail_type_cd_type VARCHAR(50) NOT NULL,
    detail_desc VARCHAR(500) NOT NULL,
    detail_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_detail_id) REFERENCES feed.feed_details(detail_id),
    FOREIGN KEY (feed_id) REFERENCES feed.feed(feed_id),
    FOREIGN KEY (environment_id) REFERENCES feed.feed_environment(environment_id),
    FOREIGN KEY (detail_type_cd, detail_type_cd_type)
        REFERENCES admin.system_codes(common_cd, code_type_cd)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_feed_run_feed_id ON feed.feed_run(feed_id);
CREATE INDEX IF NOT EXISTS idx_feed_run_status ON feed.feed_run(status_cd);
CREATE INDEX IF NOT EXISTS idx_feed_run_start_dt ON feed.feed_run(start_dt);
CREATE INDEX IF NOT EXISTS idx_feed_run_details_feed_run_id ON feed.feed_run_details(feed_run_id);
CREATE INDEX IF NOT EXISTS idx_feed_run_details_parent ON feed.feed_run_details(parent_detail_id);
CREATE INDEX IF NOT EXISTS idx_system_codes_type ON admin.system_codes(code_type_cd);
