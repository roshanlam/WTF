# WTF (Where's The Food) - System Integration Testing Guide

## System Architecture Overview

```
┌─────────────────┐
│  CSV File       │
│  (Events)       │
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│  LLM Agent Service                                       │
│  - Reads events from CSV                                 │
│  - Analyzes with Cloudflare AI (food detection)         │
│  - Publishes FreeFoodEvent to Redis                      │
└────────┬────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│  Redis Message Queue                                     │
│  - Stream: events.free-food                              │
│  - Stores FreeFoodEvent messages                         │
└────┬────────────────────────────────────────────────────┘
     │
     ├────────────────┐
     ↓                ↓
┌──────────────┐  ┌──────────────────────────────────────┐
│ MQ Consumer  │  │ Notification Service                  │
│ (Generic)    │  │ - Consumes FreeFoodEvents             │
│              │  │ - Sends email notifications via SMTP  │
└──────────────┘  └───────────────────────────────────────┘
```

## Prerequisites

### 1. Environment Variables
Ensure `.env` file has these required variables:
```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
MQ_STREAM=events.free-food

# Cloudflare AI API (for LLM Agent)
CLOUDFLARE_API_TOKEN="your_cloudflare_token"
CLOUDFLARE_ACCOUNT_ID="your_cloudflare_account_id"

# Email Notification (optional for dry-run testing)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
DRY_RUN=true  # Set to 'false' to actually send emails
NOTIFICATION_RECIPIENTS=recipient1@example.com,recipient2@example.com
```

### 2. Redis Server
Redis must be running locally on port 6379.

### 3. Python Environment
Virtual environment must be activated with all dependencies installed.

---

## Testing Steps

### Step 1: Start Redis Server

**Terminal 1:**
```bash
# Start Redis
redis-server

# Or if using Homebrew (macOS):
brew services start redis
```

**Verify Redis is running:**
```bash
redis-cli ping
# Should respond: PONG
```

---

### Step 2: Start Notification Service

**Terminal 2:**
```bash
# Activate virtual environment
source venv/bin/activate

# Start notification service
python -m services.notification

# You should see:
# - "Starting Notification Service"
# - "Notification service ready — waiting for events..."
```

**What to expect:**
- Service will connect to Redis
- Create consumer group "notification_service_group"
- Wait for FreeFoodEvent messages
- In DRY_RUN mode, it will log emails instead of sending them

---

### Step 3: Run LLM Agent Service

**Terminal 3:**
```bash
# Activate virtual environment
source venv/bin/activate

# Run LLM agent with sample events
python -m services.llm_agent --csv sample_events.csv

# You should see:
# - Events being processed
# - LLM analysis results
# - Events published to Redis queue
```

**What to expect:**
The LLM Agent will:
1. Read each event from `sample_events.csv`
2. Send to Cloudflare AI for food detection
3. For events with food detected:
   - Create `FreeFoodEvent` object
   - Publish to Redis stream
   - Trigger notification service
4. For events without food:
   - Log "No food detected"
   - Skip publishing

---

### Step 4: Monitor Notification Service (Terminal 2)

Watch Terminal 2 for notification activity:

**Expected output for food events:**
```
Processing event <event_id> — Free Pizza Workshop @ CS Building Room 150
[DRY-RUN] Would send email to recipient@example.com with subject 'Free Food: ...'
Send result for recipient@example.com: {'SMTPNotifier': True}
```

**What to verify:**
- [ ] Events are consumed from Redis
- [ ] Email subject includes event title and location
- [ ] Email body contains event details
- [ ] Notification sent to all configured recipients

---

### Step 5: Verify Redis Messages

**Terminal 4 (optional):**
```bash
# Connect to Redis CLI
redis-cli

# Check stream length
XLEN events.free-food

# Read messages from stream
XREAD COUNT 10 STREAMS events.free-food 0

# View consumer groups
XINFO GROUPS events.free-food

# Exit Redis CLI
quit
```

---

## Expected Results

### Sample Events Processing

From `sample_events.csv`, these events should trigger notifications:

1. **CS Club** - Free pizza and drinks
   - Title: "Coding Workshop" or similar
   - Location: "CS Building Room 150"

2. **Student Government** - Free bagels and coffee
   - Title: "Town Hall Meeting"
   - Location: "Student Union"

3. **Cultural Society** - Dinner and refreshments
   - Title: "Cultural Showcase"
   - Location: "Goodell Lawn"

4. **Gaming Club** - Snacks and energy drinks
   - Title: "Smash Bros Tournament"
   - Location: "Student Center"

These events should NOT trigger notifications (no food mentioned):

- Robotics Team meeting ❌
- Math Club study session ❌
- Photography Club photo walk ❌
- Book Club discussion ❌

---

## Decision Gateway Testing (Standalone)

The Decision Gateway can be tested independently:

```bash
source venv/bin/activate

python -c "
from services.decision_gateway.__main__ import DecisionGateway

gateway = DecisionGateway()

# Test with food event
result = gateway.process_tweet({
    'club_name': 'Test Club',
    'tweet': 'Free pizza today at 2pm in Student Union!',
    'food_label': 1
})

print('Decision:', result['decision'])
print('Payload:', result.get('payload', {}))
"
```

---

## Troubleshooting

### Issue: Redis Connection Error
```
Error: Connection refused (Redis)
```
**Solution:** Start Redis server (see Step 1)

### Issue: No Events Consumed
```
Notification service shows no activity
```
**Solution:**
1. Check Redis stream has messages: `redis-cli XLEN events.free-food`
2. Restart notification service
3. Verify consumer group exists

### Issue: Email Not Sent (Non-DRY-RUN)
```
Error: SMTP authentication failed
```
**Solution:**
1. Verify SMTP credentials in `.env`
2. For Gmail, use App Password, not regular password
3. Enable "Less secure app access" or use OAuth2

### Issue: Module Import Errors
```
ModuleNotFoundError: No module named 'services'
```
**Solution:**
1. Ensure virtual environment is activated
2. Run from project root directory
3. Install dependencies: `poetry install` or `pip install -r requirements.txt`

---

## Clean Up

### Stop All Services
1. Press `Ctrl+C` in each terminal
2. Stop Redis: `redis-cli shutdown` or `brew services stop redis`

### Clear Redis Stream (Optional)
```bash
redis-cli
DEL events.free-food
quit
```

---

## Advanced Testing

### Test with Custom Events

Create `test_events.csv`:
```csv
club_name,tweet,food_label
"Test Club","Custom event with free cookies!",1
```

Run:
```bash
python -m services.llm_agent --csv test_events.csv
```
