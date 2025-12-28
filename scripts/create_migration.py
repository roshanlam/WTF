#!/usr/bin/env python3
"""
Create a new Supabase migration file.

Usage:
    python scripts/create_migration.py "description of migration"

Example:
    python scripts/create_migration.py "add user avatars table"
"""

import sys
from datetime import datetime
from pathlib import Path


def create_migration(description: str):
    """Create a new migration file with timestamp."""
    # Get timestamp for migration number
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Convert description to snake_case filename
    filename = description.lower().replace(" ", "_").replace("-", "_")
    filename = "".join(c for c in filename if c.isalnum() or c == "_")

    # Create full migration name
    migration_name = f"{timestamp}_{filename}.sql"

    # Get migrations directory
    project_root = Path(__file__).parent.parent
    migrations_dir = project_root / "supabase" / "migrations"

    # Create migrations directory if it doesn't exist
    migrations_dir.mkdir(parents=True, exist_ok=True)

    # Full path to new migration file
    migration_path = migrations_dir / migration_name

    # Template for migration file
    template = f"""-- ============================================
-- {description.title()}
-- Migration: {timestamp}
-- ============================================

-- Write your migration SQL here

-- Example: Add a new table
-- CREATE TABLE IF NOT EXISTS example_table (
--     id BIGSERIAL PRIMARY KEY,
--     name VARCHAR(255) NOT NULL,
--     created_at TIMESTAMPTZ DEFAULT NOW()
-- );

-- Example: Add a new column
-- ALTER TABLE existing_table
--     ADD COLUMN IF NOT EXISTS new_column VARCHAR(100);

-- Example: Create an index
-- CREATE INDEX IF NOT EXISTS idx_example_name
--     ON example_table(name);

-- Example: Add Row Level Security
-- ALTER TABLE example_table ENABLE ROW LEVEL SECURITY;
--
-- CREATE POLICY "Users can view own data"
--     ON example_table
--     FOR SELECT
--     USING (auth.uid() = user_id);

-- Don't forget to:
-- 1. Test your migration locally first
-- 2. Add comments explaining complex logic
-- 3. Use IF NOT EXISTS to make migrations idempotent
-- 4. Consider performance impact of your changes
"""

    # Write migration file
    with open(migration_path, "w") as f:
        f.write(template)

    print(f"✓ Created migration: {migration_path}")
    print("\nNext steps:")
    print(f"1. Edit the migration file: {migration_path}")
    print("2. Test locally if possible")
    print("3. Run migrations: ./scripts/supabase_migrate.sh")

    return migration_path


def main():
    if len(sys.argv) < 2:
        print('Usage: python scripts/create_migration.py "description"')
        print("\nExample:")
        print('  python scripts/create_migration.py "add user avatars table"')
        sys.exit(1)

    description = " ".join(sys.argv[1:])

    if not description:
        print("Error: Migration description cannot be empty")
        sys.exit(1)

    create_migration(description)


if __name__ == "__main__":
    main()
