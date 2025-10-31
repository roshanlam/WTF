#!/usr/bin/env bash
# Reset Redis data for local development

set -euo pipefail

echo "Resetting Redis data..."

# Check if Redis is accessible
if ! redis-cli ping > /dev/null 2>&1; then
    echo "Error: Cannot connect to Redis"
    echo "Make sure Redis is running with 'make redis-check'"
    exit 1
fi

# Flush all Redis data
read -p "This will delete all Redis data. Continue? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    redis-cli FLUSHALL
    echo "✓ Redis data cleared"
else
    echo "Cancelled"
    exit 0
fi
