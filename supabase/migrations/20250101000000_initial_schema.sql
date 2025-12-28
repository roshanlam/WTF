-- ============================================
-- WTF Initial Schema Migration
-- Supabase PostgreSQL Database
-- Migration: 20250101000000
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Set timezone
SET timezone = 'America/New_York';

-- ============================================
-- Helper Functions
-- ============================================

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Reference Tables
-- ============================================

-- Event Categories
CREATE TABLE IF NOT EXISTS event_categories (
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

CREATE INDEX IF NOT EXISTS idx_event_categories_active ON event_categories(is_active, display_order);

CREATE TRIGGER update_event_categories_updated_at
    BEFORE UPDATE ON event_categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE event_categories IS 'Categories for organizing and filtering events';

-- Event Sources
CREATE TABLE IF NOT EXISTS event_sources (
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

CREATE INDEX IF NOT EXISTS idx_event_sources_active ON event_sources(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_event_sources_type ON event_sources(type);

CREATE TRIGGER update_event_sources_updated_at
    BEFORE UPDATE ON event_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE event_sources IS 'Tracks different sources of events (social media, feeds, etc.)';

-- ============================================
-- User Profile Extension (extends auth.users)
-- ============================================

-- User profiles (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone_number VARCHAR(20),

    -- Notification settings
    notification_enabled BOOLEAN DEFAULT TRUE,
    email_frequency VARCHAR(20) DEFAULT 'instant',

    -- Status
    is_admin BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_email_frequency CHECK (email_frequency IN ('instant', 'daily', 'weekly', 'none'))
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_notification_enabled ON user_profiles(notification_enabled)
    WHERE notification_enabled = TRUE;

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE user_profiles IS 'User profile data extending Supabase auth.users';

-- ============================================
-- User Preferences
-- ============================================

CREATE TABLE IF NOT EXISTS user_preferences (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Notification channels
    notify_email BOOLEAN DEFAULT TRUE,
    notify_sms BOOLEAN DEFAULT FALSE,
    notify_push BOOLEAN DEFAULT FALSE,

    -- Category preferences
    subscribed_categories BIGINT[] DEFAULT '{}',
    excluded_categories BIGINT[] DEFAULT '{}',

    -- Location preferences
    preferred_locations TEXT[],
    excluded_locations TEXT[],
    max_distance_miles DECIMAL(5,2),

    -- Time preferences
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    weekend_notifications BOOLEAN DEFAULT TRUE,

    -- Content filters
    min_confidence_score DECIMAL(3,2) DEFAULT 0.70,
    food_types TEXT[],
    excluded_food_types TEXT[],

    -- Digest settings
    digest_enabled BOOLEAN DEFAULT FALSE,
    digest_frequency VARCHAR(20) DEFAULT 'daily',
    digest_time TIME DEFAULT '08:00',
    digest_day_of_week INTEGER,

    -- Rate limiting
    max_notifications_per_day INTEGER DEFAULT 10,
    notifications_today INTEGER DEFAULT 0,
    notifications_reset_date DATE DEFAULT CURRENT_DATE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_digest_frequency CHECK (digest_frequency IN ('daily', 'weekly')),
    CONSTRAINT valid_day_of_week CHECK (digest_day_of_week IS NULL OR (digest_day_of_week >= 0 AND digest_day_of_week <= 6))
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_digest ON user_preferences(digest_enabled, digest_frequency)
    WHERE digest_enabled = TRUE;

CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE user_preferences IS 'Detailed notification and content preferences per user';

-- ============================================
-- Events Table (Partitioned)
-- ============================================

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    location VARCHAR(500),
    event_date TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,

    -- Source information
    source_id BIGINT NOT NULL REFERENCES event_sources(id) ON DELETE RESTRICT,
    external_source_id VARCHAR(255),
    source_url TEXT,

    -- Classification (from LLM)
    has_free_food BOOLEAN DEFAULT FALSE,
    food_type VARCHAR(100),
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    classification_reason TEXT,
    classification_timestamp TIMESTAMPTZ,
    llm_model_version VARCHAR(50),

    -- Organization
    organizer VARCHAR(255),
    organizer_verified BOOLEAN DEFAULT FALSE,
    category_id BIGINT REFERENCES event_categories(id) ON DELETE SET NULL,
    tags TEXT[],

    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMPTZ,
    notification_count INTEGER DEFAULT 0,

    -- User engagement
    view_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    report_count INTEGER DEFAULT 0,

    -- Status
    is_verified BOOLEAN DEFAULT FALSE,
    is_cancelled BOOLEAN DEFAULT FALSE,
    is_hidden BOOLEAN DEFAULT FALSE,

    -- Metadata
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (id, event_date),
    CONSTRAINT valid_times CHECK (end_time IS NULL OR end_time > event_date)
) PARTITION BY RANGE (event_date);

-- Create partitions for 2025
CREATE TABLE IF NOT EXISTS events_2025_01 PARTITION OF events
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE IF NOT EXISTS events_2025_02 PARTITION OF events
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE IF NOT EXISTS events_2025_03 PARTITION OF events
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS events_2025_04 PARTITION OF events
    FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE IF NOT EXISTS events_2025_05 PARTITION OF events
    FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE IF NOT EXISTS events_2025_06 PARTITION OF events
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS events_2025_07 PARTITION OF events
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE IF NOT EXISTS events_2025_08 PARTITION OF events
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE IF NOT EXISTS events_2025_09 PARTITION OF events
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS events_2025_10 PARTITION OF events
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE IF NOT EXISTS events_2025_11 PARTITION OF events
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE IF NOT EXISTS events_2025_12 PARTITION OF events
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
CREATE TABLE IF NOT EXISTS events_default PARTITION OF events DEFAULT;

-- Indexes for events
CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date DESC);
CREATE INDEX IF NOT EXISTS idx_events_has_free_food ON events(has_free_food) WHERE has_free_food = TRUE;
CREATE INDEX IF NOT EXISTS idx_events_source_id ON events(source_id);
CREATE INDEX IF NOT EXISTS idx_events_category_id ON events(category_id);
CREATE INDEX IF NOT EXISTS idx_events_notification_pending ON events(notification_sent, has_free_food)
    WHERE notification_sent = FALSE AND has_free_food = TRUE;
CREATE INDEX IF NOT EXISTS idx_events_tags ON events USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_events_raw_data ON events USING GIN(raw_data);
CREATE INDEX IF NOT EXISTS idx_events_title_description ON events USING GIN(
    to_tsvector('english', title || ' ' || COALESCE(description, ''))
);

CREATE TRIGGER update_events_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE events IS 'All detected events, partitioned by event_date for performance';

-- ============================================
-- Notifications Table (Partitioned)
-- ============================================

CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL,

    -- Notification details
    channel VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',

    -- Delivery tracking
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    clicked_at TIMESTAMPTZ,

    -- Error tracking
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    next_retry_at TIMESTAMPTZ,

    -- Email specifics
    email_subject VARCHAR(500),
    email_message_id VARCHAR(255),

    -- Analytics
    user_agent TEXT,
    ip_address INET,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (id, sent_at),
    CONSTRAINT valid_channel CHECK (channel IN ('email', 'sms', 'push')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'sent', 'failed', 'bounced', 'delivered', 'opened', 'clicked'))
) PARTITION BY RANGE (sent_at);

-- Create partitions for 2025
CREATE TABLE IF NOT EXISTS notifications_2025_01 PARTITION OF notifications
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE IF NOT EXISTS notifications_2025_02 PARTITION OF notifications
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE IF NOT EXISTS notifications_2025_03 PARTITION OF notifications
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS notifications_2025_04 PARTITION OF notifications
    FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE IF NOT EXISTS notifications_2025_05 PARTITION OF notifications
    FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE IF NOT EXISTS notifications_2025_06 PARTITION OF notifications
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS notifications_2025_07 PARTITION OF notifications
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE IF NOT EXISTS notifications_2025_08 PARTITION OF notifications
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE IF NOT EXISTS notifications_2025_09 PARTITION OF notifications
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS notifications_2025_10 PARTITION OF notifications
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE IF NOT EXISTS notifications_2025_11 PARTITION OF notifications
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE IF NOT EXISTS notifications_2025_12 PARTITION OF notifications
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
CREATE TABLE IF NOT EXISTS notifications_default PARTITION OF notifications DEFAULT;

-- Indexes for notifications
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_event_id ON notifications(event_id);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status, next_retry_at)
    WHERE status IN ('pending', 'failed');

COMMENT ON TABLE notifications IS 'Tracks all notifications sent to users, partitioned by sent_at';

-- ============================================
-- Event Feedback
-- ============================================

CREATE TABLE IF NOT EXISTS event_feedback (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL,

    feedback_type VARCHAR(20) NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,

    -- Specific feedback
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

CREATE INDEX IF NOT EXISTS idx_event_feedback_event_id ON event_feedback(event_id);
CREATE INDEX IF NOT EXISTS idx_event_feedback_user_id ON event_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_event_feedback_type ON event_feedback(feedback_type);

COMMENT ON TABLE event_feedback IS 'User feedback on event accuracy and quality';

-- ============================================
-- API Keys
-- ============================================

CREATE TABLE IF NOT EXISTS api_keys (
    id BIGSERIAL PRIMARY KEY,
    key_hash VARCHAR(64) UNIQUE NOT NULL,
    key_prefix VARCHAR(10) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);

CREATE TRIGGER update_api_keys_updated_at
    BEFORE UPDATE ON api_keys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE api_keys IS 'API keys for external service integrations';
