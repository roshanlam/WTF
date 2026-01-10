#!/bin/bash

# ============================================
# Supabase Migration Script
# Run migrations on Supabase database
# ============================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create a .env file with SUPABASE_DB_URL"
    exit 1
fi

# Load environment variables (safely handles special characters like @ in emails)
while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    # Skip lines without = sign
    [[ ! "$line" =~ = ]] && continue
    # Extract key (everything before first =) and value (everything after first =)
    key="${line%%=*}"
    value="${line#*=}"
    # Remove leading/trailing whitespace from key
    key=$(echo "$key" | tr -d '[:space:]')
    # Skip if key is empty
    [[ -z "$key" ]] && continue
    # Export the variable
    export "$key=$value"
done < .env

# Check if SUPABASE_DB_URL is set (also accept SUPABASE_URL as fallback)
if [ -z "$SUPABASE_DB_URL" ]; then
    if [ -n "$SUPABASE_URL" ] && [[ "$SUPABASE_URL" == postgresql://* ]]; then
        # SUPABASE_URL contains the DB connection string
        export SUPABASE_DB_URL="$SUPABASE_URL"
        echo -e "${YELLOW}Note: Using SUPABASE_URL as database connection${NC}"
    else
        echo -e "${RED}Error: SUPABASE_DB_URL not set in .env${NC}"
        echo "Get it from: Supabase Dashboard > Project Settings > Database > Connection string"
        exit 1
    fi
fi

echo -e "${GREEN}╔═══════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Supabase Migration Script      ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════╝${NC}"
echo ""

# Get migration directory
MIGRATION_DIR="supabase/migrations"

if [ ! -d "$MIGRATION_DIR" ]; then
    echo -e "${RED}Error: Migration directory not found: $MIGRATION_DIR${NC}"
    exit 1
fi

# Count migrations
MIGRATION_COUNT=$(ls -1 $MIGRATION_DIR/*.sql 2>/dev/null | wc -l)

if [ "$MIGRATION_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}No migration files found in $MIGRATION_DIR${NC}"
    exit 0
fi

echo -e "${GREEN}Found $MIGRATION_COUNT migration(s) to run${NC}"
echo ""

# Run each migration in order
for migration_file in $(ls $MIGRATION_DIR/*.sql | sort); do
    migration_name=$(basename "$migration_file")
    echo -e "${YELLOW}Running migration: $migration_name${NC}"

    # Run migration using psql
    if psql "$SUPABASE_DB_URL" -f "$migration_file" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Success: $migration_name${NC}"
    else
        echo -e "${RED}✗ Failed: $migration_name${NC}"
        echo "Check the migration file for errors"
        exit 1
    fi

    echo ""
done

echo -e "${GREEN}════════════════════════════════════${NC}"
echo -e "${GREEN}All migrations completed successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════${NC}"
echo ""

# Run seed data if requested
if [ "$1" == "--seed" ]; then
    echo -e "${YELLOW}Running seed data...${NC}"
    SEED_FILE="supabase/seed/seed_data.sql"

    if [ -f "$SEED_FILE" ]; then
        if psql "$SUPABASE_DB_URL" -f "$SEED_FILE" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Seed data loaded successfully${NC}"
        else
            echo -e "${RED}✗ Failed to load seed data${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}No seed file found: $SEED_FILE${NC}"
    fi
fi

# Show stats
echo ""
echo -e "${GREEN}Database Statistics:${NC}"
psql "$SUPABASE_DB_URL" -c "
SELECT
    (SELECT COUNT(*) FROM event_categories) as categories,
    (SELECT COUNT(*) FROM event_sources) as sources,
    (SELECT COUNT(*) FROM events) as events,
    (SELECT COUNT(*) FROM user_profiles) as users;
" 2>/dev/null || echo "Could not fetch stats"

echo ""
echo -e "${GREEN}✓ Done!${NC}"
