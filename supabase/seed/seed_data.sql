-- ============================================
-- Seed Data for WTF Application
-- Initial data for development and testing
-- ============================================

-- ============================================
-- Event Categories
-- ============================================

INSERT INTO public.event_categories (name, slug, description, icon, color, display_order) VALUES
    ('Club Events', 'club-events', 'Student organization events', '🎉', '#FF6B6B', 1),
    ('Department Events', 'department-events', 'Academic department events', '📚', '#4ECDC4', 2),
    ('Campus Events', 'campus-events', 'University-wide events', '🏫', '#45B7D1', 3),
    ('Sports', 'sports', 'Athletic events', '⚽', '#96CEB4', 4),
    ('Career', 'career', 'Career fairs and networking', '💼', '#FFEAA7', 5),
    ('Social', 'social', 'Social gatherings', '🎊', '#DFE6E9', 6),
    ('Academic', 'academic', 'Lectures and seminars', '🎓', '#74B9FF', 7),
    ('Cultural', 'cultural', 'Cultural celebrations', '🌍', '#A29BFE', 8),
    ('Greek Life', 'greek-life', 'Fraternity and sorority events', '🏛️', '#FD79A8', 9),
    ('Residence Hall', 'residence-hall', 'Dormitory events', '🏠', '#FDCB6E', 10)
ON CONFLICT (slug) DO NOTHING;

-- ============================================
-- Event Sources (Customize for your campus!)
-- ============================================

INSERT INTO public.event_sources (name, type, source_identifier, trust_score, is_verified, priority, description) VALUES
    -- Twitter sources
    ('UMass Student Union', 'twitter', '@UMassStudentUnion', 90, TRUE, 10, 'Official UMass Student Union Twitter account'),
    ('UMass Dining', 'twitter', '@UMassDining', 95, TRUE, 10, 'Official UMass Dining Services'),
    ('UMass Events', 'twitter', '@UMassEvents', 85, TRUE, 9, 'UMass campus events'),

    -- Instagram sources
    ('UMass Instagram', 'instagram', '@umass', 80, TRUE, 8, 'Official UMass Instagram'),
    ('Student Activities', 'instagram', '@umass_activities', 75, FALSE, 7, 'Student activities board'),

    -- RSS/Calendar feeds
    ('Campus Calendar', 'rss', 'https://calendar.umass.edu/feed', 100, TRUE, 10, 'Official campus calendar feed'),
    ('Events RSS', 'rss', 'https://umass.edu/events/rss', 95, TRUE, 9, 'Campus events RSS feed'),

    -- Manual entry
    ('Manual Entry', 'manual', NULL, 100, TRUE, 10, 'Manually entered events by admins'),

    -- API sources
    ('Events API', 'api', 'https://api.umass.edu/events', 90, TRUE, 8, 'Official events API'),

    -- Additional club accounts (add your own!)
    ('CS Club', 'twitter', '@UMassCS', 70, FALSE, 6, 'Computer Science club'),
    ('Engineering Society', 'twitter', '@UMassEngineering', 70, FALSE, 6, 'Engineering student society')
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- Sample Events (for testing)
-- ============================================

-- Get the source ID for manual entry
DO $$
DECLARE
    manual_source_id BIGINT;
    club_category_id BIGINT;
    social_category_id BIGINT;
BEGIN
    SELECT id INTO manual_source_id FROM event_sources WHERE name = 'Manual Entry';
    SELECT id INTO club_category_id FROM event_categories WHERE slug = 'club-events';
    SELECT id INTO social_category_id FROM event_categories WHERE slug = 'social';

    -- Sample event 1: Club meeting with pizza
    INSERT INTO events (
        title, description, location, event_date, end_time,
        source_id, has_free_food, food_type, confidence_score,
        classification_reason, llm_model_version, organizer,
        category_id, tags, is_verified
    ) VALUES (
        'CS Club Meeting - Free Pizza!',
        'Join us for our weekly CS Club meeting! We''ll be discussing upcoming hackathons and will have FREE PIZZA for all attendees. Come network with fellow computer science students!',
        'Computer Science Building, Room 140',
        NOW() + INTERVAL '2 days' + INTERVAL '18 hours',
        NOW() + INTERVAL '2 days' + INTERVAL '20 hours',
        manual_source_id,
        TRUE,
        'pizza',
        0.95,
        'Explicitly mentions "FREE PIZZA"',
        'llama-3.1-8b',
        'CS Club',
        club_category_id,
        ARRAY['pizza', 'computer science', 'club meeting', 'networking'],
        TRUE
    );

    -- Sample event 2: Career fair with lunch
    INSERT INTO events (
        title, description, location, event_date, end_time,
        source_id, has_free_food, food_type, confidence_score,
        classification_reason, llm_model_version, organizer,
        category_id, tags, is_verified
    ) VALUES (
        'Spring Career Fair - Free Lunch Provided',
        'Explore career opportunities with top employers! Free lunch will be provided to all attendees. Bring your resume!',
        'Campus Center Auditorium',
        NOW() + INTERVAL '5 days' + INTERVAL '12 hours',
        NOW() + INTERVAL '5 days' + INTERVAL '16 hours',
        manual_source_id,
        TRUE,
        'lunch',
        0.92,
        'Mentions "Free lunch will be provided"',
        'llama-3.1-8b',
        'Career Services',
        (SELECT id FROM event_categories WHERE slug = 'career'),
        ARRAY['career', 'networking', 'lunch', 'employers'],
        TRUE
    );

    -- Sample event 3: Study session with snacks
    INSERT INTO events (
        title, description, location, event_date, end_time,
        source_id, has_free_food, food_type, confidence_score,
        classification_reason, llm_model_version, organizer,
        category_id, tags
    ) VALUES (
        'Finals Study Session',
        'Group study session for calculus finals. Snacks and coffee will be available!',
        'Library, 3rd Floor Study Room',
        NOW() + INTERVAL '1 day' + INTERVAL '19 hours',
        NOW() + INTERVAL '1 day' + INTERVAL '23 hours',
        manual_source_id,
        TRUE,
        'snacks',
        0.85,
        'Mentions "Snacks and coffee will be available"',
        'llama-3.1-8b',
        'Math Department',
        (SELECT id FROM event_categories WHERE slug = 'academic'),
        ARRAY['study', 'finals', 'snacks', 'coffee', 'math']
    );
END $$;

-- ============================================
-- Sample Admin User (for testing)
-- Note: You'll need to create this user via Supabase Auth first
-- ============================================

-- To create an admin user:
-- 1. Sign up via Supabase Auth UI
-- 2. Get the user UUID
-- 3. Run this update to make them admin:
-- UPDATE user_profiles SET is_admin = TRUE WHERE email = 'admin@example.com';

-- ============================================
-- Success Message
-- ============================================

SELECT
    (SELECT COUNT(*) FROM event_categories) as categories_count,
    (SELECT COUNT(*) FROM event_sources) as sources_count,
    (SELECT COUNT(*) FROM events WHERE has_free_food = TRUE) as sample_events_count;
