# Supabase Setup Guide for WTF

## Overview

This guide will help you set up **Supabase** as the database backend for the WTF (Where's The Food) application. Supabase provides:

- ✅ **PostgreSQL Database** (scalable to 50K+ users)
- ✅ **Built-in Authentication** (email, OAuth, magic links)
- ✅ **Row Level Security** (automatic security policies)
- ✅ **Real-time Subscriptions** (live event updates)
- ✅ **Auto-generated REST API** (no backend code needed)
- ✅ **Storage** (for user avatars, event images)
- ✅ **Edge Functions** (serverless functions)

**Estimated Setup Time**: 15-30 minutes

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create Supabase Project](#create-supabase-project)
3. [Run Database Migrations](#run-database-migrations)
4. [Configure Environment Variables](#configure-environment-variables)
5. [Update Application Code](#update-application-code)
6. [Verify Setup](#verify-setup)
7. [Next Steps](#next-steps)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### 1. Create a Supabase Account

1. Go to [https://app.supabase.com](https://app.supabase.com)
2. Sign up with GitHub, Google, or email
3. Verify your email address

### 2. Install Required Tools

```bash
# Install PostgreSQL client (for running migrations)
# macOS
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql-client

# Windows
# Download from: https://www.postgresql.org/download/windows/

# Install Python dependencies
pip install supabase-py python-dotenv
```

### 3. Install Supabase CLI (Optional but Recommended)

```bash
# macOS/Linux
brew install supabase/tap/supabase

# Windows
scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
scoop install supabase

# Verify installation
supabase --version
```

---

## Create Supabase Project

### Step 1: Create New Project

1. Go to [https://app.supabase.com](https://app.supabase.com)
2. Click **"New Project"**
3. Select your organization (or create one)
4. Fill in project details:
   - **Name**: `wtf-production` (or `wtf-dev` for development)
   - **Database Password**: Generate a strong password (save this!)
   - **Region**: Choose closest to your users (e.g., `us-east-1` for East Coast)
   - **Pricing Plan**: Free tier (upgrade later as needed)
5. Click **"Create new project"**
6. Wait 2-3 minutes for project setup to complete

### Step 2: Get API Keys

Once your project is ready:

1. Go to **Project Settings** (gear icon) → **API**
2. Copy these values (you'll need them later):
   - **Project URL**: `https://xxxxx.supabase.co`
   - **anon public** key: `eyJhbGci...` (safe for client-side)
   - **service_role** key: `eyJhbGci...` (**SECRET!** Use only server-side)

3. Go to **Project Settings** → **Database**
4. Scroll to **Connection string** → **URI**
5. Copy the connection string and replace `[YOUR-PASSWORD]` with your database password
6. Save as `SUPABASE_DB_URL`

---

## Run Database Migrations

### Option A: Using Our Migration Script (Recommended)

1. **Copy environment template**:
```bash
cp .env.example .env
```

2. **Edit `.env` file**:
```bash
# Add your Supabase credentials
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGci...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
SUPABASE_DB_URL=postgresql://postgres:your-password@db.xxxxx.supabase.co:5432/postgres
```

3. **Run migrations**:
```bash
# Make script executable
chmod +x scripts/supabase_migrate.sh

# Run all migrations
./scripts/supabase_migrate.sh

# Run migrations AND seed data
./scripts/supabase_migrate.sh --seed
```

4. **Verify**:
```bash
# Check tables were created
psql "$SUPABASE_DB_URL" -c "\dt"
```

### Option B: Using Supabase CLI

```bash
# Link to your project
supabase link --project-ref your-project-ref

# Run migrations
supabase db push

# Run seed data
supabase db seed
```

### Option C: Manual via Supabase Dashboard

1. Go to **SQL Editor** in Supabase Dashboard
2. Run each migration file in order:
   - `supabase/migrations/20250101000000_initial_schema.sql`
   - `supabase/migrations/20250101000001_auth_integration.sql`
   - `supabase/migrations/20250101000002_rls_policies.sql`
   - `supabase/migrations/20250101000003_views_functions.sql`
3. Run seed data: `supabase/seed/seed_data.sql`

---

## Configure Environment Variables

### Update Your `.env` File

```bash
# ============================================
# Supabase Configuration
# ============================================
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_DB_URL=postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres

# ============================================
# Redis (still needed for caching)
# ============================================
REDIS_URL=redis://redis:6379/0
REDIS_POOL_SIZE=50
REDIS_POOL_TIMEOUT=30
CACHE_ACTIVE_USERS_TTL=300

# ============================================
# Email Configuration
# ============================================
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
USE_SSL=true
DRY_RUN=false

# ============================================
# LLM Configuration
# ============================================
CLOUDFLARE_API_TOKEN=your-token
CLOUDFLARE_ACCOUNT_ID=your-account-id

# ============================================
# Application
# ============================================
API_PORT=8000
ENVIRONMENT=production
DEBUG=false
```

---

## Update Application Code

### Step 1: Update `requirements.txt` or `pyproject.toml`

Add Supabase client:

```toml
# pyproject.toml
[tool.poetry.dependencies]
supabase = "^2.0.0"
python-dotenv = "^1.0.0"
```

Or for pip:
```bash
pip install supabase-py python-dotenv
```

### Step 2: Update `services/database.py`

You have two options:

**Option A: Use Supabase client (recommended)**

Replace imports in your code:
```python
# Old SQLite imports
# from services.database import add_user, get_active_users

# New Supabase imports
from services.supabase_client import (
    add_user_subscription as add_user,
    get_active_users,
    get_event,
    add_event,
    # ... other functions
)
```

**Option B: Keep existing interface**

Update `services/database.py` to use `supabase_client.py` internally:
```python
# services/database.py
from services.supabase_client import (
    add_user_subscription,
    get_active_users as _get_active_users,
    # ... other imports
)

def add_user(email: str) -> bool:
    """Add user subscription (wrapper for Supabase)."""
    result = add_user_subscription(email)
    return result is not None

def get_active_users() -> list[str]:
    """Get active users (wrapper for Supabase)."""
    return _get_active_users()

# ... other wrapper functions
```

### Step 3: Update Docker Compose (Optional)

If using Docker, you can remove the local PostgreSQL container since you're using Supabase:

```yaml
# docker-compose.yml
services:
  # Remove local postgres service (using Supabase instead)

  notification:
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      # ... other env vars

  # Keep Redis for caching
  redis:
    image: redis:latest
    # ... redis config
```

---

## Verify Setup

### 1. Check Database Tables

```bash
# Via psql
psql "$SUPABASE_DB_URL" -c "\dt"

# Should show:
# - user_profiles
# - user_preferences
# - events (partitioned)
# - notifications (partitioned)
# - event_categories
# - event_sources
# - event_feedback
# - api_keys
```

### 2. Test Supabase Client

Create a test script:

```python
# test_supabase.py
from services.supabase_client import (
    get_supabase_client,
    get_event_categories,
    get_stats
)

def test_connection():
    print("Testing Supabase connection...")

    # Test 1: Get categories
    categories = get_event_categories()
    print(f"✓ Categories: {len(categories)} found")

    # Test 2: Get stats
    stats = get_stats()
    print(f"✓ Stats: {stats}")

    print("\n✓ All tests passed!")

if __name__ == "__main__":
    test_connection()
```

Run it:
```bash
python test_supabase.py
```

### 3. Test User Signup

```python
# test_signup.py
from services.supabase_client import add_user_subscription

# Test signup
user = add_user_subscription("test@umass.edu")
if user:
    print(f"✓ User created: {user}")
else:
    print("✗ User creation failed")
```

### 4. Check Supabase Dashboard

1. Go to **Table Editor** in Supabase Dashboard
2. Verify tables exist with correct columns
3. Check **Authentication** → Users (should see test user)
4. Check **Logs** → Postgres Logs for any errors

---

## Next Steps

### 1. Enable Email Authentication

1. Go to **Authentication** → **Providers**
2. Enable **Email** provider
3. Configure email templates
4. Set up email confirmation (optional)

### 2. Set Up Row Level Security

RLS is already configured in migrations, but you can customize:

1. Go to **Authentication** → **Policies**
2. Review policies for each table
3. Add custom policies as needed

### 3. Configure Realtime (Optional)

Enable real-time updates for events:

1. Go to **Database** → **Replication**
2. Enable replication for `events` table
3. In your app, subscribe to changes:

```python
# Example: Real-time event subscription
supabase = get_supabase_client()

def handle_event_change(payload):
    print(f"New event: {payload}")

# Subscribe to new food events
supabase.table('events') \
    .on('INSERT', handle_event_change) \
    .filter('has_free_food', 'eq', True) \
    .subscribe()
```

### 4. Set Up Storage (for Event Images)

1. Go to **Storage**
2. Create bucket: `event-images`
3. Set policies for upload/download
4. Use in your app:

```python
# Upload event image
supabase.storage.from_('event-images').upload(
    f'events/{event_id}.jpg',
    file_data
)
```

### 5. Monitor Usage

1. Go to **Settings** → **Usage**
2. Monitor:
   - Database size
   - API requests
   - Bandwidth
   - Authentication users
3. Set up alerts for approaching limits

### 6. Backups

Supabase automatically backs up your database, but for critical data:

1. Go to **Database** → **Backups**
2. Enable Point-in-Time Recovery (PITR)
3. Schedule manual backups
4. Download backups for local storage

---

## Troubleshooting

### Problem: "Connection refused" when running migrations

**Solution**: Check your `SUPABASE_DB_URL`:
- Ensure you replaced `[YOUR-PASSWORD]` with actual password
- Check if IP is allowed (Supabase allows all by default)
- Verify project is not paused (free tier pauses after 1 week of inactivity)

### Problem: "Role 'postgres' does not exist"

**Solution**: Use the connection pooler URL instead:
```bash
SUPABASE_DB_URL=postgresql://postgres.xxxxx:password@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

### Problem: RLS policies blocking operations

**Solution**: Use service role key for backend operations:
```python
# Use service role key (bypasses RLS)
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

### Problem: Migration fails with "already exists"

**Solution**: Migrations use `IF NOT EXISTS` and should be idempotent. If you need to reset:
```bash
# WARNING: This deletes all data!
psql "$SUPABASE_DB_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Then re-run migrations
./scripts/supabase_migrate.sh --seed
```

### Problem: Can't connect from Python

**Solution**: Check dependencies:
```bash
pip install --upgrade supabase-py

# Test connection
python -c "from supabase import create_client; print('OK')"
```

### Problem: "Project is paused"

**Solution**: Free tier projects pause after 1 week of inactivity:
1. Go to Supabase Dashboard
2. Click "Restore project"
3. Wait 1-2 minutes
4. Upgrade to Pro plan to prevent pausing

---

## Migration Strategy

### For Existing SQLite Users

If you have existing data in SQLite:

#### 1. Export SQLite Data

```bash
# Export users
sqlite3 wtf.db "SELECT * FROM users;" > users.csv

# Export events
sqlite3 wtf.db "SELECT * FROM events;" > events.csv
```

#### 2. Import to Supabase

```bash
# Import users
psql "$SUPABASE_DB_URL" -c "\COPY user_profiles(email, created_at) FROM 'users.csv' CSV"

# Import events (adjust columns as needed)
psql "$SUPABASE_DB_URL" -c "\COPY events(...) FROM 'events.csv' CSV"
```

#### 3. Verify Data

```python
from services.supabase_client import get_stats

stats = get_stats()
print(f"Migrated {stats['active_users']} users")
print(f"Migrated {stats['food_events']} events")
```

---

## Performance Optimization

### 1. Connection Pooling

Supabase uses PgBouncer automatically. For even better performance:

```python
# Use connection pooler URL
SUPABASE_DB_URL=postgresql://postgres.xxxxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres?pgbouncer=true
```

### 2. Caching

Still use Redis for caching:

```python
# Cache active users for 5 minutes
from services.database import get_active_users  # Uses Redis cache

users = get_active_users()  # Cached!
```

### 3. Indexes

Our migrations already create indexes, but monitor usage:

```sql
-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```

### 4. Query Optimization

Use `.select()` to fetch only needed columns:

```python
# Bad: Fetch all columns
events = supabase.table('events').select('*').execute()

# Good: Fetch only needed columns
events = supabase.table('events').select('id, title, location, event_date').execute()
```

---

## Security Best Practices

### 1. Environment Variables

- ✅ **DO**: Use different keys for dev/staging/prod
- ✅ **DO**: Rotate service role key if compromised
- ❌ **DON'T**: Commit `.env` to git
- ❌ **DON'T**: Use service role key in client-side code

### 2. Row Level Security

- ✅ **DO**: Always enable RLS on tables with user data
- ✅ **DO**: Test policies before deploying
- ❌ **DON'T**: Disable RLS in production

### 3. API Keys

- ✅ **DO**: Use anon key for public API calls
- ✅ **DO**: Use service role key for backend only
- ❌ **DON'T**: Expose service role key to clients

### 4. Rate Limiting

Enable in Supabase dashboard:
1. Go to **Settings** → **API**
2. Configure rate limits per IP
3. Set up abuse prevention

---

## Cost Estimation

### Free Tier Limits

- Database: 500MB
- Bandwidth: 2GB
- Storage: 1GB
- API Requests: Unlimited
- Authentication Users: Unlimited

**Estimate for 50K users**:
- Database size: ~4GB (exceeds free tier)
- Monthly cost on Pro tier: ~$25/month
- Add-ons for scale: ~$50-100/month total

### Recommended Plan

For 50,000 users:
- **Pro Plan**: $25/month
- **Compute Add-on**: Small (included in Pro)
- **Total**: ~$25-50/month

Much cheaper than managing your own PostgreSQL server!

---

## Support Resources

- 📚 **Supabase Docs**: https://supabase.com/docs
- 💬 **Discord Community**: https://discord.supabase.com
- 🐛 **GitHub Issues**: https://github.com/supabase/supabase
- 📧 **Email Support**: Pro tier includes email support

---

## Summary Checklist

- [ ] Create Supabase account and project
- [ ] Copy API keys to `.env`
- [ ] Run database migrations
- [ ] Load seed data
- [ ] Install `supabase-py` dependency
- [ ] Update application code to use Supabase client
- [ ] Test user signup and login
- [ ] Verify events can be created
- [ ] Test notifications
- [ ] Enable Row Level Security
- [ ] Set up monitoring
- [ ] Configure backups

**Once complete, your app is ready for 50K+ users!** 🎉

---

**Version**: 1.0
**Last Updated**: 2025-12-28
**Author**: Claude Code
