# Supabase Migrations

This directory contains database migrations for the WTF application using Supabase (PostgreSQL).

## Directory Structure

```
supabase/
├── migrations/          # Database migration files
│   ├── 20250101000000_initial_schema.sql
│   ├── 20250101000001_auth_integration.sql
│   ├── 20250101000002_rls_policies.sql
│   └── 20250101000003_views_functions.sql
├── seed/               # Seed data for development
│   └── seed_data.sql
└── README.md          # This file
```

## Running Migrations

### Quick Start

```bash
# 1. Set up your .env file with Supabase credentials
cp .env.example .env

# 2. Run all migrations
./scripts/supabase_migrate.sh

# 3. Load seed data
./scripts/supabase_migrate.sh --seed
```

### Manual Migration

```bash
# Run individual migration
psql "$SUPABASE_DB_URL" -f supabase/migrations/20250101000000_initial_schema.sql
```

## Creating New Migrations

```bash
# Use the helper script
python scripts/create_migration.py "add user avatars table"

# This creates: supabase/migrations/YYYYMMDDHHMMSS_add_user_avatars_table.sql
```

## Migration Naming Convention

- Migrations are numbered by timestamp: `YYYYMMDDHHMMSS_description.sql`
- Use descriptive names: `add_user_avatars`, `update_events_schema`
- Always use snake_case

## Migration Best Practices

1. **Idempotent**: Use `IF NOT EXISTS` to make migrations rerunnable
2. **Reversible**: Include comments on how to reverse if needed
3. **Small**: Keep each migration focused on one change
4. **Tested**: Test migrations locally before deploying
5. **Sequential**: Run migrations in order (enforced by timestamp)

## Example Migration

```sql
-- Migration: 20250101000004_add_user_avatars
-- Description: Add avatar URL column to user_profiles

-- Add column
ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS avatar_url TEXT;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_avatar
    ON user_profiles(avatar_url)
    WHERE avatar_url IS NOT NULL;

-- Add RLS policy
CREATE POLICY "Users can update own avatar"
    ON user_profiles
    FOR UPDATE
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Comments
COMMENT ON COLUMN user_profiles.avatar_url IS 'URL to user avatar image in storage';
```

## Troubleshooting

### Migration fails with "already exists"

Migrations use `IF NOT EXISTS` and should be idempotent. If you see this error:
1. Check if the migration was already run
2. Verify your migration uses `IF NOT EXISTS` clauses

### Can't connect to database

Check your `.env` file:
- `SUPABASE_DB_URL` should be the PostgreSQL connection string
- Format: `postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres`

### Permission denied

Use the service role key in your `.env`:
- `SUPABASE_SERVICE_ROLE_KEY=your-service-role-key`

## Documentation

For more details, see [SUPABASE_SETUP.md](../SUPABASE_SETUP.md)
