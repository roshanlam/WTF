-- ============================================
-- Views and Helper Functions
-- Useful queries and utilities
-- Migration: 20250101000003
-- ============================================

-- ============================================
-- Views
-- ============================================

-- View: Recent food events with details
CREATE OR REPLACE VIEW v_recent_food_events AS
SELECT
    e.id,
    e.title,
    e.description,
    e.location,
    e.event_date,
    e.end_time,
    e.food_type,
    e.confidence_score,
    e.organizer,
    ec.name as category_name,
    ec.icon as category_icon,
    es.name as source_name,
    es.type as source_type,
    e.notification_sent,
    e.view_count,
    e.click_count,
    e.is_verified,
    e.created_at
FROM events e
LEFT JOIN event_categories ec ON e.category_id = ec.id
LEFT JOIN event_sources es ON e.source_id = es.id
WHERE e.has_free_food = TRUE
  AND e.is_hidden = FALSE
  AND e.is_cancelled = FALSE
  AND e.event_date >= NOW() - INTERVAL '1 day'
ORDER BY e.event_date ASC;

COMMENT ON VIEW v_recent_food_events IS 'Recent free food events with category and source details';

-- View: User notification statistics
CREATE OR REPLACE VIEW v_user_notification_stats AS
SELECT
    up.id as user_id,
    up.email,
    COUNT(n.id) as total_notifications,
    COUNT(n.id) FILTER (WHERE n.status = 'delivered') as delivered_count,
    COUNT(n.id) FILTER (WHERE n.status = 'opened') as opened_count,
    COUNT(n.id) FILTER (WHERE n.status = 'clicked') as clicked_count,
    COUNT(n.id) FILTER (WHERE n.status = 'failed') as failed_count,
    MAX(n.sent_at) as last_notification_at
FROM user_profiles up
LEFT JOIN notifications n ON up.id = n.user_id
GROUP BY up.id, up.email;

COMMENT ON VIEW v_user_notification_stats IS 'Notification statistics per user';

-- View: Event performance metrics
CREATE OR REPLACE VIEW v_event_metrics AS
SELECT
    e.id,
    e.title,
    e.event_date,
    e.confidence_score,
    e.view_count,
    e.click_count,
    e.notification_count,
    COUNT(DISTINCT n.user_id) as users_notified,
    COUNT(DISTINCT n.id) FILTER (WHERE n.status = 'delivered') as delivery_count,
    COUNT(DISTINCT ef.id) as feedback_count,
    AVG(ef.rating) as avg_rating,
    COUNT(DISTINCT ef.id) FILTER (WHERE ef.feedback_type = 'helpful') as helpful_count,
    COUNT(DISTINCT ef.id) FILTER (WHERE ef.feedback_type = 'spam') as spam_count
FROM events e
LEFT JOIN notifications n ON e.id = n.event_id
LEFT JOIN event_feedback ef ON e.id = ef.event_id
WHERE e.has_free_food = TRUE
GROUP BY e.id, e.title, e.event_date, e.confidence_score, e.view_count, e.click_count, e.notification_count;

COMMENT ON VIEW v_event_metrics IS 'Performance metrics and analytics for events';

-- View: Daily notification summary
CREATE OR REPLACE VIEW v_daily_notification_summary AS
SELECT
    DATE(sent_at) as date,
    channel,
    status,
    COUNT(*) as count,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(EXTRACT(EPOCH FROM (delivered_at - sent_at))) as avg_delivery_time_seconds
FROM notifications
WHERE sent_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(sent_at), channel, status
ORDER BY date DESC, channel, status;

COMMENT ON VIEW v_daily_notification_summary IS 'Daily notification statistics and performance';

-- View: Popular event categories
CREATE OR REPLACE VIEW v_popular_categories AS
SELECT
    ec.id,
    ec.name,
    ec.slug,
    ec.icon,
    COUNT(e.id) as event_count,
    COUNT(e.id) FILTER (WHERE e.has_free_food = TRUE) as food_event_count,
    AVG(e.confidence_score) as avg_confidence,
    SUM(e.view_count) as total_views,
    SUM(e.notification_count) as total_notifications
FROM event_categories ec
LEFT JOIN events e ON ec.id = e.category_id
WHERE ec.is_active = TRUE
  AND e.created_at >= NOW() - INTERVAL '90 days'
GROUP BY ec.id, ec.name, ec.slug, ec.icon
ORDER BY food_event_count DESC;

COMMENT ON VIEW v_popular_categories IS 'Event category popularity and statistics';

-- ============================================
-- Helper Functions
-- ============================================

-- Function: Search events by text
CREATE OR REPLACE FUNCTION search_events(search_query TEXT, limit_count INTEGER DEFAULT 20)
RETURNS TABLE (
    id BIGINT,
    title VARCHAR,
    description TEXT,
    location VARCHAR,
    event_date TIMESTAMPTZ,
    confidence_score DECIMAL,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.title,
        e.description,
        e.location,
        e.event_date,
        e.confidence_score,
        ts_rank(
            to_tsvector('english', e.title || ' ' || COALESCE(e.description, '')),
            plainto_tsquery('english', search_query)
        ) as rank
    FROM events e
    WHERE to_tsvector('english', e.title || ' ' || COALESCE(e.description, ''))
        @@ plainto_tsquery('english', search_query)
      AND e.has_free_food = TRUE
      AND e.is_hidden = FALSE
      AND e.event_date >= NOW() - INTERVAL '1 day'
    ORDER BY rank DESC, e.event_date ASC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION search_events IS 'Full-text search for food events';

-- Function: Get events by location proximity
CREATE OR REPLACE FUNCTION get_nearby_events(
    location_keyword TEXT,
    days_ahead INTEGER DEFAULT 7,
    limit_count INTEGER DEFAULT 20
)
RETURNS TABLE (
    id BIGINT,
    title VARCHAR,
    description TEXT,
    location VARCHAR,
    event_date TIMESTAMPTZ,
    confidence_score DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.title,
        e.description,
        e.location,
        e.event_date,
        e.confidence_score
    FROM events e
    WHERE e.has_free_food = TRUE
      AND e.is_hidden = FALSE
      AND e.is_cancelled = FALSE
      AND e.location ILIKE '%' || location_keyword || '%'
      AND e.event_date >= NOW()
      AND e.event_date <= NOW() + (days_ahead || ' days')::INTERVAL
    ORDER BY e.event_date ASC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_nearby_events IS 'Find events near a specific location';

-- Function: Get user's personalized event feed
CREATE OR REPLACE FUNCTION get_personalized_feed(
    user_id_param UUID,
    limit_count INTEGER DEFAULT 20
)
RETURNS TABLE (
    id BIGINT,
    title VARCHAR,
    description TEXT,
    location VARCHAR,
    event_date TIMESTAMPTZ,
    confidence_score DECIMAL,
    food_type VARCHAR,
    category_name VARCHAR
) AS $$
DECLARE
    user_prefs RECORD;
BEGIN
    -- Get user preferences
    SELECT * INTO user_prefs
    FROM user_preferences
    WHERE user_id = user_id_param;

    -- Return personalized feed based on preferences
    RETURN QUERY
    SELECT
        e.id,
        e.title,
        e.description,
        e.location,
        e.event_date,
        e.confidence_score,
        e.food_type,
        ec.name as category_name
    FROM events e
    LEFT JOIN event_categories ec ON e.category_id = ec.id
    WHERE e.has_free_food = TRUE
      AND e.is_hidden = FALSE
      AND e.is_cancelled = FALSE
      AND e.event_date >= NOW()
      AND e.confidence_score >= COALESCE(user_prefs.min_confidence_score, 0.70)
      -- Filter by subscribed categories if set
      AND (
          user_prefs.subscribed_categories IS NULL
          OR array_length(user_prefs.subscribed_categories, 1) IS NULL
          OR e.category_id = ANY(user_prefs.subscribed_categories)
      )
      -- Exclude excluded categories
      AND (
          user_prefs.excluded_categories IS NULL
          OR array_length(user_prefs.excluded_categories, 1) IS NULL
          OR e.category_id != ALL(user_prefs.excluded_categories)
      )
      -- Filter by food types if set
      AND (
          user_prefs.food_types IS NULL
          OR array_length(user_prefs.food_types, 1) IS NULL
          OR e.food_type = ANY(user_prefs.food_types)
      )
      -- Exclude food types
      AND (
          user_prefs.excluded_food_types IS NULL
          OR array_length(user_prefs.excluded_food_types, 1) IS NULL
          OR e.food_type != ALL(user_prefs.excluded_food_types)
      )
    ORDER BY e.event_date ASC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

COMMENT ON FUNCTION get_personalized_feed IS 'Get personalized event feed based on user preferences';

-- Function: Mark event as viewed
CREATE OR REPLACE FUNCTION mark_event_viewed(event_id_param BIGINT)
RETURNS VOID AS $$
BEGIN
    UPDATE events
    SET view_count = view_count + 1
    WHERE id = event_id_param;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION mark_event_viewed IS 'Increment view count for an event';

-- Function: Mark notification as delivered/opened/clicked
CREATE OR REPLACE FUNCTION update_notification_status(
    notification_id_param BIGINT,
    new_status VARCHAR,
    user_agent_param TEXT DEFAULT NULL,
    ip_address_param INET DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE notifications
    SET
        status = new_status,
        delivered_at = CASE WHEN new_status = 'delivered' THEN NOW() ELSE delivered_at END,
        opened_at = CASE WHEN new_status = 'opened' THEN NOW() ELSE opened_at END,
        clicked_at = CASE WHEN new_status = 'clicked' THEN NOW() ELSE clicked_at END,
        user_agent = COALESCE(user_agent_param, user_agent),
        ip_address = COALESCE(ip_address_param, ip_address)
    WHERE id = notification_id_param;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_notification_status IS 'Update notification delivery status with tracking';

-- Function: Get notification delivery rate
CREATE OR REPLACE FUNCTION get_notification_delivery_rate(days_back INTEGER DEFAULT 7)
RETURNS TABLE (
    total_sent BIGINT,
    delivered BIGINT,
    opened BIGINT,
    clicked BIGINT,
    failed BIGINT,
    delivery_rate NUMERIC,
    open_rate NUMERIC,
    click_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) as total_sent,
        COUNT(*) FILTER (WHERE status = 'delivered') as delivered,
        COUNT(*) FILTER (WHERE status = 'opened') as opened,
        COUNT(*) FILTER (WHERE status = 'clicked') as clicked,
        COUNT(*) FILTER (WHERE status = 'failed') as failed,
        ROUND(
            COUNT(*) FILTER (WHERE status = 'delivered')::NUMERIC / NULLIF(COUNT(*), 0) * 100,
            2
        ) as delivery_rate,
        ROUND(
            COUNT(*) FILTER (WHERE status = 'opened')::NUMERIC / NULLIF(COUNT(*), 0) * 100,
            2
        ) as open_rate,
        ROUND(
            COUNT(*) FILTER (WHERE status = 'clicked')::NUMERIC / NULLIF(COUNT(*), 0) * 100,
            2
        ) as click_rate
    FROM notifications
    WHERE sent_at >= NOW() - (days_back || ' days')::INTERVAL;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_notification_delivery_rate IS 'Calculate notification delivery metrics';

-- ============================================
-- Realtime Publication (Supabase Realtime)
-- ============================================

-- Enable realtime for events table
ALTER PUBLICATION supabase_realtime ADD TABLE events;
ALTER PUBLICATION supabase_realtime ADD TABLE user_preferences;

-- ============================================
-- Grant execute permissions on functions
-- ============================================

GRANT EXECUTE ON FUNCTION search_events TO authenticated, anon;
GRANT EXECUTE ON FUNCTION get_nearby_events TO authenticated, anon;
GRANT EXECUTE ON FUNCTION get_personalized_feed TO authenticated;
GRANT EXECUTE ON FUNCTION mark_event_viewed TO authenticated, anon;
GRANT EXECUTE ON FUNCTION update_notification_status TO service_role;
GRANT EXECUTE ON FUNCTION get_notification_delivery_rate TO authenticated;
