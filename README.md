# WTF - Where's The Food

A microservices-based event-driven system for tracking and notifying users about free food events.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Development](#development)
- [Services](#services)
- [Useful Resources](#useful-resources)

## Architecture Overview

This project uses a microservices architecture with the following components:

- **API Service**: Main REST API for handling user requests
- **Decision Gateway**: Routes and processes decision logic
- **LLM Agent**: Handles AI/LLM interactions
- **MQ Consumer**: Consumes messages from the event stream
- **Notification Service**: Sends notifications to users

All services communicate via Redis Streams for event-driven messaging.

## Quick Start

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/) (Python dependency management)
- Docker (redis)

### Setup

1. **Clone the repository**
   ```bash
   git clone git@github.com:roshanlam/WTF.git
   cd wtf
   ```

2. **Run setup** (installs dependencies and creates .env)
   ```bash
   make setup
   ```

3. **Configure environment**
   - Review and update `.env` with your local settings
   - See `.env.example` for available configuration options

4. **Start Redis**

   **Option A: Docker Compose (Recommended)**
   ```bash
   make docker-up
   ```

   **Option B: Check existing or start manually**
   ```bash
   # Check if Redis is already running
   make redis-check

   # If not running, start Redis in Docker
   make redis-start
   ```

5. **Run a service**
   ```bash
   make run-api
   # or
   make run-llm-agent
   ```

### Available Make Commands

Run `make help` to see all available commands:

```bash
make help          # Show all commands
make setup         # Initial setup (install + .env)
make install       # Install dependencies
make test          # Run tests
make lint          # Run linting
make format        # Format code
make check         # Run lint + tests
make clean         # Remove caches and generated files
make redis-start   # Start Redis in Docker
make redis-stop    # Stop Redis container
```

## Project Structure

```
wtf/
├── services/              # All microservices
│   ├── __init__.py
│   ├── config.py         # Shared configuration loader
│   ├── mq.py             # Message queue utilities
│   ├── api/              # REST API service
│   │   ├── __init__.py
│   │   └── __main__.py
│   ├── decision_gateway/ # Decision routing service
│   │   ├── __init__.py
│   │   └── __main__.py
│   ├── llm_agent/        # LLM interaction service
│   │   ├── __init__.py
│   │   └── __main__.py
│   ├── mq_consumer/      # Message queue consumer
│   │   ├── __init__.py
│   │   └── __main__.py
│   └── notification/     # Notification service
│       ├── __init__.py
│       └── __main__.py
├── docs/                 # Documentation (architecture, API specs)
├── infra/                # Infrastructure configs (Docker, CI/CD)
├── scripts/              # Utility scripts (check_deps.sh, reset_redis.sh)
├── .env.example          # Environment variables template
├── .env                  # Local environment config (gitignored)
├── pyproject.toml        # Poetry dependencies and project config
├── poetry.lock           # Locked dependency versions
└── Makefile              # Development commands
```

## Development

### Adding Dependencies

```bash
# Add a runtime dependency
poetry add <package-name>

# Add a dev dependency
poetry add --group dev <package-name>
```

### Running Services

Each service can be run individually using Poetry or Make:

```bash
# Using Make (recommended)
make run-api
make run-llm-agent
make run-decision-gateway
make run-mq-consumer
make run-notification

# Using Poetry directly
poetry run api
poetry run llm-agent
```

### Code Quality

This project uses:
- **Ruff**: Fast Python linter and formatter
- **MyPy**: Static type checking
- **Pytest**: Testing framework
- **Pre-commit**: Git hooks for automated checks

```bash
# Format code
make format

# Run linting
make lint

# Run tests
make test

# Run all checks
make check

# Install pre-commit hooks (recommended)
make pre-commit-install
```

### Redis Setup

You have three options for running Redis:

**Option 1: Docker Compose (Recommended for teams)**
```bash
make docker-up      # Start Redis with Docker Compose
make docker-down    # Stop all services
make docker-logs    # View logs
```

**Option 2: Local Redis (if already installed)**
```bash
make redis-check    # Verify it's running
# .env should use: REDIS_URL=redis://localhost:6379/0
```

**Option 3: Standalone Docker**
```bash
make redis-start    # Start Redis container
make redis-stop     # Stop container
make redis-clean    # Remove container and data
```

**Redis Commands:**
- `make redis-check` - Verify Redis is accessible
- `make redis-cli` - Open Redis CLI (works with any option)

### Environment Variables

Key configuration variables (see `.env.example`):

- `REDIS_URL`: Redis connection string (default: `redis://redis:6379/0`)
- `MQ_STREAM`: Message queue stream name (default: `events.free-food`)
- `API_PORT`: API service port (default: `8000`)
- `DECISION_GATEWAY_PORT`: Decision Gateway port (default: `8100`)
- `NOTIFICATION_PORT`: Notification service port (default: `8200`)

## Services

### API Service
- **Port**: 8000
- **Purpose**: Main REST API endpoint for external requests
- **Run**: `make run-api`

### Decision Gateway
- **Port**: 8100
- **Purpose**: Routes requests and applies decision logic
- **Run**: `make run-decision-gateway`

### LLM Agent
- **Purpose**: Handles AI/LLM interactions and processing
- **Run**: `make run-llm-agent`

### MQ Consumer
- **Purpose**: Consumes events from Redis Stream
- **Run**: `make run-mq-consumer`

### Notification Service
- **Port**: 8200
- **Purpose**: Sends notifications to users
- **Run**: `make run-notification`

## Additional Documentation

- [Architecture](docs/architecture.md) - System design and component interactions
- [Infrastructure](infra/README.md) - Deployment and infrastructure setup
- [Scripts](scripts/README.md) - Utility scripts for development

## Useful Resources

### Poetry
- [Poetry Documentation](https://python-poetry.org/docs/)
- [Poetry Basic Usage](https://python-poetry.org/docs/basic-usage/)
- [Managing Dependencies](https://python-poetry.org/docs/dependency-specification/)
- [Poetry Commands](https://python-poetry.org/docs/cli/)

### Tools & Frameworks
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Redis Documentation](https://redis.io/docs/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Pytest Documentation](https://docs.pytest.org/)

### Python
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Python Async/Await](https://docs.python.org/3/library/asyncio.html)

## Troubleshooting

### Poetry installation fails
- Ensure you're using Python 3.11+: `python --version`
- Clear Poetry cache: `poetry cache clear --all pypi`
- Delete `poetry.lock` and run `poetry install` again

### Redis connection issues
- Check if Redis is accessible: `make redis-check`
- If port 6379 is in use: You likely have local Redis running. Update `.env` to use `redis://localhost:6379/0`
- Test connection: `make redis-cli` then run `PING`
- Check what's using port 6379: `lsof -i :6379`

### Import errors
- Ensure dependencies are installed: `make install`
- Activate Poetry shell: `poetry shell`

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting: `make check`
4. Format code: `make format`
5. Commit and push
6. Create a pull request
