-- Enhanced database schema with authentication

-- Users table with authentication
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Enhanced file uploads with user tracking
CREATE TABLE file_uploads (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    -- Added storage_path to reload files for processing
    storage_path VARCHAR(512),
    row_count INTEGER,
    column_count INTEGER,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'uploaded',
    is_public BOOLEAN DEFAULT FALSE
);

-- Analysis results linked to users
CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    file_upload_id INTEGER REFERENCES file_uploads(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    analysis_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Column analysis details
CREATE TABLE column_analyses (
    id SERIAL PRIMARY KEY,
    analysis_result_id INTEGER REFERENCES analysis_results(id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    missing_values INTEGER NOT NULL,
    missing_percentage DECIMAL(5,2) NOT NULL,
    unique_values INTEGER NOT NULL,
    suggestions JSONB NOT NULL,
    recommended_action VARCHAR(100),
    is_problematic BOOLEAN DEFAULT FALSE,
    -- NEW AI-POWERED FIELDS
    ai_insights TEXT,
    ai_recommendation VARCHAR(100)
);

-- Processing jobs with user tracking
CREATE TABLE data_processing_jobs (
    id SERIAL PRIMARY KEY,
    file_upload_id INTEGER REFERENCES file_uploads(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    actions_applied JSONB NOT NULL,
    processing_status VARCHAR(20) DEFAULT 'pending',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    output_filename VARCHAR(255)
);

-- User sessions for authentication
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_agent TEXT,
    ip_address INET
);

-- Enhanced usage analytics with user tracking
CREATE TABLE usage_analytics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action_type VARCHAR(50) NOT NULL,
    file_upload_id INTEGER REFERENCES file_uploads(id) ON DELETE SET NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Renamed 'metadata' to 'event_details' to avoid SQL conflicts
    event_details JSONB,
    ip_address INET,
    user_agent TEXT
);

-- User preferences
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    -- Added ON DELETE CASCADE for better data integrity
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE NOT NULL,
    theme VARCHAR(20) DEFAULT 'dark',
    notifications_enabled BOOLEAN DEFAULT TRUE,
    auto_save_analyses BOOLEAN DEFAULT TRUE,
    default_actions JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Password reset tokens
CREATE TABLE password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Image dataset jobs
CREATE TABLE image_dataset_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    original_zip_filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(512) NOT NULL UNIQUE,
    image_count INTEGER,
    processing_status VARCHAR(20) DEFAULT 'pending',
    actions_applied JSONB,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    output_zip_path VARCHAR(512)
);


-- Create indexes for better performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_file_uploads_user_id ON file_uploads(user_id);
CREATE INDEX idx_file_uploads_file_hash ON file_uploads(file_hash);
CREATE INDEX idx_analysis_results_user_id ON analysis_results(user_id);
CREATE INDEX idx_analysis_results_file_id ON analysis_results(file_upload_id);
CREATE INDEX idx_column_analyses_analysis_id ON column_analyses(analysis_result_id);
CREATE INDEX idx_processing_jobs_user_id ON data_processing_jobs(user_id);
CREATE INDEX idx_processing_jobs_file_id ON data_processing_jobs(file_upload_id);
CREATE INDEX idx_processing_jobs_status ON data_processing_jobs(processing_status);
CREATE INDEX idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_usage_analytics_user_id ON usage_analytics(user_id);
CREATE INDEX idx_usage_analytics_timestamp ON usage_analytics(timestamp);
CREATE INDEX idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX idx_image_dataset_jobs_user_id ON image_dataset_jobs(user_id);