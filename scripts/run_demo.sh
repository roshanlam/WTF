#!/bin/bash
# WTF System Demo Runner
# This script helps you run the complete system end-to-end

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  WTF (Where's The Food) - System Demo${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

# Check if Redis is running
echo -e "\n${YELLOW}[1/5]${NC} Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis is running${NC}"
else
    echo -e "❌ Redis is not running. Please start Redis first:"
    echo -e "   ${YELLOW}redis-server${NC}"
    echo -e "   or: ${YELLOW}brew services start redis${NC}"
    exit 1
fi

# Check virtual environment
echo -e "\n${YELLOW}[2/5]${NC} Checking virtual environment..."
if [ -d "venv" ]; then
    echo -e "${GREEN}✅ Virtual environment found${NC}"
    source venv/bin/activate
else
    echo -e "❌ Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt 2>/dev/null || poetry install
fi

# Run integration tests
echo -e "\n${YELLOW}[3/5]${NC} Running integration tests..."
if python tests/test_integration.py; then
    echo -e "${GREEN}✅ All integration tests passed${NC}"
else
    echo -e "❌ Integration tests failed. Please check the errors above."
    exit 1
fi

# Clear old events from Redis (optional)
echo -e "\n${YELLOW}[4/5]${NC} Cleaning Redis stream..."
read -p "Do you want to clear old events from Redis? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    redis-cli DEL events.free-food > /dev/null
    echo -e "${GREEN}✅ Redis stream cleared${NC}"
else
    echo -e "${BLUE}ℹ  Keeping existing events${NC}"
fi

# Display instructions
echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ All checks passed! Ready to run the system.${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

echo -e "\n${YELLOW}[5/5]${NC} To run the complete system:"
echo -e ""
echo -e "1️⃣  ${YELLOW}Terminal 1${NC} - Start Notification Service:"
echo -e "   ${BLUE}source venv/bin/activate && python -m services.notification${NC}"
echo -e ""
echo -e "2️⃣  ${YELLOW}Terminal 2${NC} - Run LLM Agent:"
echo -e "   ${BLUE}source venv/bin/activate && python -m services.llm_agent --csv sample_events.csv${NC}"
echo -e ""
echo -e "📊 ${YELLOW}Optional${NC} - Monitor Redis:"
echo -e "   ${BLUE}redis-cli MONITOR${NC}"
echo -e ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "📚 For more details, see:"
echo -e "   - ${YELLOW}QUICKSTART.md${NC} - Quick start guide"
echo -e "   - ${YELLOW}TESTING_INSTRUCTIONS.md${NC} - Detailed testing instructions"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
