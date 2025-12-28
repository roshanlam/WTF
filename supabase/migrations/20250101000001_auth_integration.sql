-- ============================================
-- Auth Integration Migration
-- Supabase Auth Triggers and Functions
-- Migration: 20250101000001
-- ============================================

-- ============================================
-- Auto-create user profile on signup
-- ============================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- Create user profile
    INSERT INTO public.user_profiles (id, email, created_at)
    VALUES (
        NEW.id,
        NEW.email,
        NOW()
    );

    -- Create default user preferences
    INSERT INTO public.user_preferences (user_id, created_at)
    VALUES (
        NEW.id,
        NOW()
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger on auth.users creation
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

COMMENT ON FUNCTION public.handle_new_user IS 'Automatically creates user_profile and user_preferences when a new user signs up';

-- ============================================
-- Sync email updates from auth.users
-- ============================================

CREATE OR REPLACE FUNCTION public.sync_user_email()
RETURNS TRIGGER AS $$
BEGIN
    -- Update email in user_profiles when changed in auth.users
    IF NEW.email IS DISTINCT FROM OLD.email THEN
        UPDATE public.user_profiles
        SET email = NEW.email, updated_at = NOW()
        WHERE id = NEW.id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger on auth.users email update
DROP TRIGGER IF EXISTS on_auth_user_email_updated ON auth.users;
CREATE TRIGGER on_auth_user_email_updated
    AFTER UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.sync_user_email();

COMMENT ON FUNCTION public.sync_user_email IS 'Syncs email changes from auth.users to user_profiles';

-- ============================================
-- Update last login timestamp
-- ============================================

CREATE OR REPLACE FUNCTION public.update_last_login()
RETURNS TRIGGER AS $$
BEGIN
    -- Update last_login_at when last_sign_in_at changes
    IF NEW.last_sign_in_at IS DISTINCT FROM OLD.last_sign_in_at THEN
        UPDATE public.user_profiles
        SET last_login_at = NEW.last_sign_in_at, updated_at = NOW()
        WHERE id = NEW.id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger on auth.users sign in
DROP TRIGGER IF EXISTS on_auth_user_login ON auth.users;
CREATE TRIGGER on_auth_user_login
    AFTER UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.update_last_login();

COMMENT ON FUNCTION public.update_last_login IS 'Updates last_login_at timestamp when user signs in';

-- ============================================
-- Soft delete user data
-- ============================================

CREATE OR REPLACE FUNCTION public.handle_user_delete()
RETURNS TRIGGER AS $$
BEGIN
    -- Mark user as inactive but don't delete data (for analytics)
    UPDATE public.user_profiles
    SET
        notification_enabled = FALSE,
        updated_at = NOW()
    WHERE id = OLD.id;

    -- Note: Child tables (preferences, notifications, feedback) will cascade delete
    -- due to ON DELETE CASCADE in foreign keys

    RETURN OLD;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger on auth.users deletion
DROP TRIGGER IF EXISTS on_auth_user_deleted ON auth.users;
CREATE TRIGGER on_auth_user_deleted
    BEFORE DELETE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_user_delete();

COMMENT ON FUNCTION public.handle_user_delete IS 'Handles cleanup when user account is deleted';

-- ============================================
-- Helper Functions for User Management
-- ============================================

-- Function to get user profile by email
CREATE OR REPLACE FUNCTION public.get_user_by_email(user_email TEXT)
RETURNS TABLE (
    id UUID,
    email TEXT,
    first_name TEXT,
    last_name TEXT,
    notification_enabled BOOLEAN,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        up.id,
        up.email,
        up.first_name,
        up.last_name,
        up.notification_enabled,
        up.created_at
    FROM public.user_profiles up
    WHERE up.email = user_email
    LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION public.get_user_by_email IS 'Retrieves user profile by email address';

-- Function to check if user is admin
CREATE OR REPLACE FUNCTION public.is_admin(user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM public.user_profiles
        WHERE id = user_id AND is_admin = TRUE
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION public.is_admin IS 'Checks if a user has admin privileges';

-- ============================================
-- Reset daily notification count (scheduled)
-- ============================================

CREATE OR REPLACE FUNCTION public.reset_daily_notification_counts()
RETURNS VOID AS $$
BEGIN
    UPDATE public.user_preferences
    SET
        notifications_today = 0,
        notifications_reset_date = CURRENT_DATE
    WHERE notifications_reset_date < CURRENT_DATE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION public.reset_daily_notification_counts IS 'Resets daily notification counter for all users (run via cron)';

-- ============================================
-- Increment event view count
-- ============================================

CREATE OR REPLACE FUNCTION public.increment_event_views(event_id_param BIGINT)
RETURNS VOID AS $$
BEGIN
    UPDATE public.events
    SET view_count = view_count + 1
    WHERE id = event_id_param;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.increment_event_views IS 'Increments view count for an event';

-- ============================================
-- Get active subscribers for notifications
-- ============================================

CREATE OR REPLACE FUNCTION public.get_active_subscribers()
RETURNS TABLE (
    user_id UUID,
    email TEXT,
    min_confidence_score DECIMAL,
    subscribed_categories BIGINT[],
    excluded_categories BIGINT[],
    max_notifications_per_day INTEGER,
    notifications_today INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        up.id as user_id,
        up.email,
        upr.min_confidence_score,
        upr.subscribed_categories,
        upr.excluded_categories,
        upr.max_notifications_per_day,
        upr.notifications_today
    FROM public.user_profiles up
    INNER JOIN public.user_preferences upr ON up.id = upr.user_id
    WHERE up.notification_enabled = TRUE
      AND upr.notify_email = TRUE
      AND (upr.notifications_today < upr.max_notifications_per_day);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION public.get_active_subscribers IS 'Returns all active subscribers eligible for notifications';
