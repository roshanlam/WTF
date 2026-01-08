-- ============================================
-- WTF 2026 Partitions Migration
-- Adds table partitions for year 2026
-- Migration: 20250101000004
-- ============================================

-- ============================================
-- Events Partitions for 2026
-- ============================================

CREATE TABLE IF NOT EXISTS events_2026_01 PARTITION OF events
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE IF NOT EXISTS events_2026_02 PARTITION OF events
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE IF NOT EXISTS events_2026_03 PARTITION OF events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE IF NOT EXISTS events_2026_04 PARTITION OF events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS events_2026_05 PARTITION OF events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS events_2026_06 PARTITION OF events
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS events_2026_07 PARTITION OF events
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE IF NOT EXISTS events_2026_08 PARTITION OF events
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE IF NOT EXISTS events_2026_09 PARTITION OF events
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE IF NOT EXISTS events_2026_10 PARTITION OF events
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE IF NOT EXISTS events_2026_11 PARTITION OF events
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE IF NOT EXISTS events_2026_12 PARTITION OF events
    FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');

-- ============================================
-- Notifications Partitions for 2026
-- ============================================

CREATE TABLE IF NOT EXISTS notifications_2026_01 PARTITION OF notifications
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE IF NOT EXISTS notifications_2026_02 PARTITION OF notifications
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE IF NOT EXISTS notifications_2026_03 PARTITION OF notifications
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE IF NOT EXISTS notifications_2026_04 PARTITION OF notifications
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS notifications_2026_05 PARTITION OF notifications
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS notifications_2026_06 PARTITION OF notifications
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS notifications_2026_07 PARTITION OF notifications
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE IF NOT EXISTS notifications_2026_08 PARTITION OF notifications
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE IF NOT EXISTS notifications_2026_09 PARTITION OF notifications
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE IF NOT EXISTS notifications_2026_10 PARTITION OF notifications
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE IF NOT EXISTS notifications_2026_11 PARTITION OF notifications
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE IF NOT EXISTS notifications_2026_12 PARTITION OF notifications
    FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');

-- ============================================
-- Add unique constraint for spider deduplication
-- ============================================

-- This allows the spider to upsert events without duplicates
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'events_external_source_unique'
    ) THEN
        ALTER TABLE events
        ADD CONSTRAINT events_external_source_unique
        UNIQUE (external_source_id, source_id, event_date);
    END IF;
EXCEPTION
    WHEN duplicate_object THEN
        NULL;
END $$;

-- ============================================
-- Insert WTF Spider as event source
-- ============================================

INSERT INTO event_sources (name, type, source_identifier, is_active, is_verified, trust_score, priority, description, config)
VALUES (
    'WTF Spider',
    'api',
    'wtf-spider-v2',
    TRUE,
    TRUE,
    80,
    10,
    'Automated web crawler for detecting free food events from campus websites',
    '{"version": "2.0", "platforms": ["localist", "eventbrite", "facebook", "meetup", "schema.org"]}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
    is_active = TRUE,
    config = EXCLUDED.config,
    description = EXCLUDED.description;

-- ============================================
-- Add indexes for spider queries
-- ============================================

CREATE INDEX IF NOT EXISTS idx_events_external_source_id
ON events(external_source_id)
WHERE external_source_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_events_source_url
ON events(source_url)
WHERE source_url IS NOT NULL;

COMMENT ON INDEX idx_events_external_source_id IS 'Index for spider deduplication lookups';
