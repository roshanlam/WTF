-- ============================================
-- WTF Database Schema v2.0
-- PostgreSQL 15+
-- Quick Setup Script
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Set timezone (adjust for your campus)
SET timezone = 'America/New_York';

-- ============================================
-- Helper function for auto-updating timestamps
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 1. Event Categories (Reference Table)
-- ============================================

CREATE TABLE event_categories (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    color VARCHAR(7),
    parent_category_id BIGINT REFERENCES event_categories(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_event_categories_active ON event_categories(is_active, display_order);
CREATE TRIGGER update_event_categories_updated_at BEFORE UPDATE ON event_categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Seed categories
INSERT INTO event_categories (name, slug, description, icon) VALUES
    ('Club Events', 'club-events', 'Student organization events', '🎉'),
    ('Department Events', 'department-events', 'Academic department events', '📚'),
    ('Campus Events', 'campus-events', 'University-wide events', '🏫'),
    ('Sports', 'sports', 'Athletic events', '⚽'),
    ('Career', 'career', 'Career fairs and networking', '💼'),
    ('Social', 'social', 'Social gatherings', '🎊'),
    ('Academic', 'academic', 'Lectures and seminars', '🎓'),
    ('Cultural', 'cultural', 'Cultural celebrations', '🌍');

-- ============================================
-- 2. Event Sources
-- ============================================

CREATE TABLE event_sources (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL,
    source_identifier VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    trust_score INTEGER DEFAULT 50 CHECK (trust_score >= 0 AND trust_score <= 100),
    priority INTEGER DEFAULT 0,
    last_checked_at TIMESTAMPTZ,
    last_event_at TIMESTAMPTZ,
    total_events_scraped INTEGER DEFAULT 0,
    total_food_events_found INTEGER DEFAULT 0,
    check_frequency_minutes INTEGER DEFAULT 60,
    api_rate_limit INTEGER,
    description TEXT,
    config JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_source_type CHECK (type IN (
        'twitter', 'instagram', 'facebook', 'rss', 'manual', 'api', 'webhook'
    ))
);

CREATE INDEX idx_event_sources_active ON event_sources(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_event_sources_type ON event_sources(type);
CREATE TRIGGER update_event_sources_updated_at BEFORE UPDATE ON event_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Seed event sources (customize for your campus)
INSERT INTO event_sources (name, type, source_identifier, trust_score, is_verified) VALUES
    ('UMass Student Union', 'twitter', '@UMassStudentUnion', 90, TRUE),
    ('UMass Dining', 'twitter', '@UMassDining', 95, TRUE),
    ('Campus Calendar', 'rss', 'https://calendar.umass.edu/feed', 100, TRUE),
    ('Manual Entry', 'manual', NULL, 100, TRUE);

-- ============================================
-- 3. Users
-- ============================================

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(64) UNIQUE,
    verification_token_expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone_number VARCHAR(20),
    notification_enabled BOOLEAN DEFAULT TRUE,
    email_frequency VARCHAR(20) DEFAULT 'instant',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'),
    CONSTRAINT valid_email_frequency CHECK (email_frequency IN ('instant', 'daily', 'weekly', 'none'))
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_users_verification_token ON users(verification_token) WHERE verification_token IS NOT NULL;
CREATE INDEX idx_users_deleted_at ON users(deleted_at) WHERE deleted_at IS NULL;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 4. User Preferences
-- ============================================

CREATE TABLE user_preferences (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notify_email BOOLEAN DEFAULT TRUE,
    notify_sms BOOLEAN DEFAULT FALSE,
    notify_push BOOLEAN DEFAULT FALSE,
    subscribed_categories BIGINT[] DEFAULT '{}',
    excluded_categories BIGINT[] DEFAULT '{}',
    preferred_locations TEXT[],
    excluded_locations TEXT[],
    max_distance_miles DECIMAL(5,2),
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    weekend_notifications BOOLEAN DEFAULT TRUE,
    min_confidence_score DECIMAL(3,2) DEFAULT 0.70,
    food_types TEXT[],
    excluded_food_types TEXT[],
    digest_enabled BOOLEAN DEFAULT FALSE,
    digest_frequency VARCHAR(20) DEFAULT 'daily',
    digest_time TIME DEFAULT '08:00',
    digest_day_of_week INTEGER,
    max_notifications_per_day INTEGER DEFAULT 10,
    notifications_today INTEGER DEFAULT 0,
    notifications_reset_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_digest_frequency CHECK (digest_frequency IN ('daily', 'weekly')),
    CONSTRAINT valid_day_of_week CHECK (digest_day_of_week IS NULL OR (digest_day_of_week >= 0 AND digest_day_of_week <= 6))
);

CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id);
CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 5. Events (Partitioned)
-- ============================================

CREATE TABLE events (
    id BIGSERIAL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    location VARCHAR(500),
    event_date TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    source_id BIGINT NOT NULL REFERENCES event_sources(id) ON DELETE RESTRICT,
    external_source_id VARCHAR(255),
    source_url TEXT,
    has_free_food BOOLEAN DEFAULT FALSE,
    food_type VARCHAR(100),
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    classification_reason TEXT,
    classification_timestamp TIMESTAMPTZ,
    llm_model_version VARCHAR(50),
    organizer VARCHAR(255),
    organizer_verified BOOLEAN DEFAULT FALSE,
    category_id BIGINT REFERENCES event_categories(id) ON DELETE SET NULL,
    tags TEXT[],
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMPTZ,
    notification_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    report_count INTEGER DEFAULT 0,
    is_verified BOOLEAN DEFAULT FALSE,
    is_cancelled BOOLEAN DEFAULT FALSE,
    is_hidden BOOLEAN DEFAULT FALSE,
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, event_date),
    CONSTRAINT valid_times CHECK (end_time IS NULL OR end_time > event_date)
) PARTITION BY RANGE (event_date);

-- Create partitions for 2025
CREATE TABLE events_2025_01 PARTITION OF events FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE events_2025_02 PARTITION OF events FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE events_2025_03 PARTITION OF events FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE events_2025_04 PARTITION OF events FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE events_2025_05 PARTITION OF events FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE events_2025_06 PARTITION OF events FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE events_2025_07 PARTITION OF events FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE events_2025_08 PARTITION OF events FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE events_2025_09 PARTITION OF events FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE events_2025_10 PARTITION OF events FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE events_2025_11 PARTITION OF events FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE events_2025_12 PARTITION OF events FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
CREATE TABLE events_default PARTITION OF events DEFAULT;

-- Indexes for events
CREATE INDEX idx_events_event_date ON events(event_date DESC);
CREATE INDEX idx_events_has_free_food ON events(has_free_food) WHERE has_free_food = TRUE;
CREATE INDEX idx_events_source_id ON events(source_id);
CREATE INDEX idx_events_notification_pending ON events(notification_sent, has_free_food)
    WHERE notification_sent = FALSE AND has_free_food = TRUE;
CREATE INDEX idx_events_tags ON events USING GIN(tags);
CREATE INDEX idx_events_title_description ON events USING GIN(
    to_tsvector('english', title || ' ' || COALESCE(description, ''))
);
CREATE TRIGGER update_events_updated_at BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 6. Notifications (Partitioned)
-- ============================================

CREATE TABLE notifications (
    id BIGSERIAL,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL,
    channel VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    clicked_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    next_retry_at TIMESTAMPTZ,
    email_subject VARCHAR(500),
    email_message_id VARCHAR(255),
    user_agent TEXT,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, sent_at),
    CONSTRAINT valid_channel CHECK (channel IN ('email', 'sms', 'push')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'sent', 'failed', 'bounced', 'delivered', 'opened', 'clicked'))
) PARTITION BY RANGE (sent_at);

-- Create partitions for 2025
CREATE TABLE notifications_2025_01 PARTITION OF notifications FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE notifications_2025_02 PARTITION OF notifications FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE notifications_2025_03 PARTITION OF notifications FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE notifications_2025_04 PARTITION OF notifications FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE notifications_2025_05 PARTITION OF notifications FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE notifications_2025_06 PARTITION OF notifications FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE notifications_2025_07 PARTITION OF notifications FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE notifications_2025_08 PARTITION OF notifications FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE notifications_2025_09 PARTITION OF notifications FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE notifications_2025_10 PARTITION OF notifications FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE notifications_2025_11 PARTITION OF notifications FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE notifications_2025_12 PARTITION OF notifications FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
CREATE TABLE notifications_default PARTITION OF notifications DEFAULT;

-- Indexes for notifications
CREATE INDEX idx_notifications_user_id ON notifications(user_id, sent_at DESC);
CREATE INDEX idx_notifications_event_id ON notifications(event_id);
CREATE INDEX idx_notifications_status ON notifications(status, next_retry_at)
    WHERE status IN ('pending', 'failed');

-- ============================================
-- 7. Event Feedback
-- ============================================

CREATE TABLE event_feedback (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL,
    feedback_type VARCHAR(20) NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    food_was_available BOOLEAN,
    food_type_correct BOOLEAN,
    location_correct BOOLEAN,
    time_correct BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, event_id),
    CONSTRAINT valid_feedback_type CHECK (feedback_type IN (
        'helpful', 'not_helpful', 'spam', 'incorrect', 'cancelled', 'duplicate'
    ))
);

CREATE INDEX idx_event_feedback_event_id ON event_feedback(event_id);
CREATE INDEX idx_event_feedback_user_id ON event_feedback(user_id);

-- ============================================
-- 8. API Keys
-- ============================================

CREATE TABLE api_keys (
    id BIGSERIAL PRIMARY KEY,
    key_hash VARCHAR(64) UNIQUE NOT NULL,
    key_prefix VARCHAR(10) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    organization VARCHAR(255),
    scopes TEXT[] DEFAULT '{"read"}',
    allowed_ips INET[],
    rate_limit_per_hour INTEGER DEFAULT 1000,
    rate_limit_per_day INTEGER DEFAULT 10000,
    last_used_at TIMESTAMPTZ,
    total_requests BIGINT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = TRUE;
CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON api_keys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 9. Audit Log (Partitioned)
-- ============================================

CREATE TABLE audit_log (
    id BIGSERIAL,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    admin_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    api_key_id BIGINT REFERENCES api_keys(id) ON DELETE SET NULL,
    table_name VARCHAR(100) NOT NULL,
    record_id BIGINT,
    action VARCHAR(20) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_fields TEXT[],
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, created_at),
    CONSTRAINT valid_action CHECK (action IN ('insert', 'update', 'delete'))
) PARTITION BY RANGE (created_at);

-- Create quarterly partitions for audit log
CREATE TABLE audit_log_2025_q1 PARTITION OF audit_log FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE audit_log_2025_q2 PARTITION OF audit_log FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE audit_log_2025_q3 PARTITION OF audit_log FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE audit_log_2025_q4 PARTITION OF audit_log FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE audit_log_default PARTITION OF audit_log DEFAULT;

CREATE INDEX idx_audit_log_user_id ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_log_table_record ON audit_log(table_name, record_id);

-- ============================================
-- 10. Useful Views
-- ============================================

-- Active subscribers
CREATE OR REPLACE VIEW v_active_subscribers AS
SELECT
    u.id,
    u.email,
    u.first_name,
    u.last_name,
    u.notification_enabled,
    u.email_frequency,
    up.notify_email,
    up.min_confidence_score,
    up.subscribed_categories
FROM users u
LEFT JOIN user_preferences up ON u.id = up.user_id
WHERE u.is_active = TRUE
  AND u.email_verified = TRUE
  AND u.notification_enabled = TRUE
  AND u.deleted_at IS NULL;

-- Recent food events
CREATE OR REPLACE VIEW v_recent_food_events AS
SELECT
    e.id,
    e.title,
    e.description,
    e.location,
    e.event_date,
    e.confidence_score,
    e.food_type,
    ec.name as category_name,
    es.name as source_name,
    e.notification_sent
FROM events e
LEFT JOIN event_categories ec ON e.category_id = ec.id
LEFT JOIN event_sources es ON e.source_id = es.id
WHERE e.has_free_food = TRUE
  AND e.is_hidden = FALSE
  AND e.event_date >= NOW() - INTERVAL '1 day'
ORDER BY e.event_date ASC;

-- ============================================
-- Success!
-- ============================================

SELECT
    'Database schema created successfully!' as status,
    COUNT(*) FILTER (WHERE tablename LIKE 'events_%') as event_partitions,
    COUNT(*) FILTER (WHERE tablename LIKE 'notifications_%') as notification_partitions
FROM pg_tables
WHERE schemaname = 'public';
