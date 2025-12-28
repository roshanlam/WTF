-- ============================================
-- Row Level Security (RLS) Policies
-- Supabase Security Layer
-- Migration: 20250101000002
-- ============================================

-- ============================================
-- Enable RLS on all tables
-- ============================================

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.event_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

-- Reference tables (categories, sources) - allow public read access
ALTER TABLE public.event_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.event_sources ENABLE ROW LEVEL SECURITY;

-- ============================================
-- User Profiles Policies
-- ============================================

-- Users can view their own profile
CREATE POLICY "Users can view own profile"
    ON public.user_profiles
    FOR SELECT
    USING (auth.uid() = id);

-- Users can update their own profile
CREATE POLICY "Users can update own profile"
    ON public.user_profiles
    FOR UPDATE
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Admins can view all profiles
CREATE POLICY "Admins can view all profiles"
    ON public.user_profiles
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Service role bypass (for backend operations)
CREATE POLICY "Service role has full access to user_profiles"
    ON public.user_profiles
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role')
    WITH CHECK (auth.jwt()->>'role' = 'service_role');

-- ============================================
-- User Preferences Policies
-- ============================================

-- Users can view their own preferences
CREATE POLICY "Users can view own preferences"
    ON public.user_preferences
    FOR SELECT
    USING (auth.uid() = user_id);

-- Users can update their own preferences
CREATE POLICY "Users can update own preferences"
    ON public.user_preferences
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Service role bypass
CREATE POLICY "Service role has full access to user_preferences"
    ON public.user_preferences
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role')
    WITH CHECK (auth.jwt()->>'role' = 'service_role');

-- ============================================
-- Events Policies
-- ============================================

-- Anyone can view active events
CREATE POLICY "Anyone can view active events"
    ON public.events
    FOR SELECT
    USING (
        is_hidden = FALSE
        AND is_cancelled = FALSE
    );

-- Admins can insert events
CREATE POLICY "Admins can insert events"
    ON public.events
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Admins can update events
CREATE POLICY "Admins can update events"
    ON public.events
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Service role bypass
CREATE POLICY "Service role has full access to events"
    ON public.events
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role')
    WITH CHECK (auth.jwt()->>'role' = 'service_role');

-- ============================================
-- Notifications Policies
-- ============================================

-- Users can view their own notifications
CREATE POLICY "Users can view own notifications"
    ON public.notifications
    FOR SELECT
    USING (auth.uid() = user_id);

-- Service role can manage all notifications
CREATE POLICY "Service role has full access to notifications"
    ON public.notifications
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role')
    WITH CHECK (auth.jwt()->>'role' = 'service_role');

-- ============================================
-- Event Feedback Policies
-- ============================================

-- Users can view their own feedback
CREATE POLICY "Users can view own feedback"
    ON public.event_feedback
    FOR SELECT
    USING (auth.uid() = user_id);

-- Users can insert their own feedback
CREATE POLICY "Users can insert own feedback"
    ON public.event_feedback
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own feedback
CREATE POLICY "Users can update own feedback"
    ON public.event_feedback
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Users can delete their own feedback
CREATE POLICY "Users can delete own feedback"
    ON public.event_feedback
    FOR DELETE
    USING (auth.uid() = user_id);

-- Admins can view all feedback
CREATE POLICY "Admins can view all feedback"
    ON public.event_feedback
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Service role bypass
CREATE POLICY "Service role has full access to event_feedback"
    ON public.event_feedback
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role')
    WITH CHECK (auth.jwt()->>'role' = 'service_role');

-- ============================================
-- API Keys Policies
-- ============================================

-- Users can view their own API keys
CREATE POLICY "Users can view own API keys"
    ON public.api_keys
    FOR SELECT
    USING (auth.uid() = user_id);

-- Users can insert their own API keys
CREATE POLICY "Users can insert own API keys"
    ON public.api_keys
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own API keys (deactivate)
CREATE POLICY "Users can update own API keys"
    ON public.api_keys
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Users can delete their own API keys
CREATE POLICY "Users can delete own API keys"
    ON public.api_keys
    FOR DELETE
    USING (auth.uid() = user_id);

-- Admins can view all API keys
CREATE POLICY "Admins can view all API keys"
    ON public.api_keys
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Service role bypass
CREATE POLICY "Service role has full access to api_keys"
    ON public.api_keys
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role')
    WITH CHECK (auth.jwt()->>'role' = 'service_role');

-- ============================================
-- Reference Tables Policies (Public Read)
-- ============================================

-- Anyone can read event categories
CREATE POLICY "Anyone can read event categories"
    ON public.event_categories
    FOR SELECT
    USING (is_active = TRUE);

-- Admins can manage categories
CREATE POLICY "Admins can manage event categories"
    ON public.event_categories
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Service role bypass
CREATE POLICY "Service role has full access to event_categories"
    ON public.event_categories
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role')
    WITH CHECK (auth.jwt()->>'role' = 'service_role');

-- Anyone can read event sources
CREATE POLICY "Anyone can read event sources"
    ON public.event_sources
    FOR SELECT
    USING (is_active = TRUE);

-- Admins can manage sources
CREATE POLICY "Admins can manage event sources"
    ON public.event_sources
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Service role bypass
CREATE POLICY "Service role has full access to event_sources"
    ON public.event_sources
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role')
    WITH CHECK (auth.jwt()->>'role' = 'service_role');

-- ============================================
-- Grant permissions to authenticated users
-- ============================================

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO anon;

-- Grant table access
GRANT SELECT ON public.event_categories TO authenticated, anon;
GRANT SELECT ON public.event_sources TO authenticated, anon;
GRANT SELECT ON public.events TO authenticated, anon;

-- Grant sequence usage for inserts
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- ============================================
-- Comments
-- ============================================

COMMENT ON POLICY "Users can view own profile" ON public.user_profiles IS 'Users can only see their own profile data';
COMMENT ON POLICY "Service role has full access to events" ON public.events IS 'Backend services can manage all events';
COMMENT ON POLICY "Anyone can view active events" ON public.events IS 'Public can view non-hidden, non-cancelled events';
