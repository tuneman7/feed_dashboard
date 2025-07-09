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
