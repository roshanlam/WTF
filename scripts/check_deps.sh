#!/usr/bin/env bash
# Check if all required dependencies are installed

set -euo pipefail

echo "Checking dependencies..."
echo ""

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✓ $PYTHON_VERSION"
else
    echo "✗ Python 3 not found"
    exit 1
fi

# Check Poetry
if command -v poetry &> /dev/null; then
    POETRY_VERSION=$(poetry --version)
    echo "✓ $POETRY_VERSION"
else
    echo "✗ Poetry not found - Install from https://python-poetry.org/"
    exit 1
fi

# Check Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo "✓ $DOCKER_VERSION"
else
    echo "⚠ Docker not found - Optional but recommended"
fi

# Check Redis CLI
if command -v redis-cli &> /dev/null; then
    echo "✓ redis-cli available"
else
    echo "⚠ redis-cli not found - Optional for debugging"
fi

# Check Make
if command -v make &> /dev/null; then
    MAKE_VERSION=$(make --version | head -n1)
    echo "✓ $MAKE_VERSION"
else
    echo "✗ Make not found"
    exit 1
fi

echo ""
echo "All required dependencies are installed!"
echo "Run 'make setup' to get started."
