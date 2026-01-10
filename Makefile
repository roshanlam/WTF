.PHONY: help install setup clean test test-cov test-fast test-verbose lint format run-api run-llm-agent run-decision-gateway run-mq-consumer run-notification run-subscription-api dev check pre-commit-install redis-check redis-start redis-stop redis-clean redis-cli docker-up docker-down docker-logs docker-build docker-init seed-db db-stats

help:
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:
	@echo "Installing dependencies..."
	poetry install

setup: install
	@echo "Setting up project..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file from .env.example"; \
		echo "Please review and update .env with your local configuration"; \
	else \
		echo ".env file already exists"; \
	fi
	@echo "Setup complete!"

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleanup complete!"

test: ## Run all tests
	@if [ -d "venv" ]; then \
		. venv/bin/activate && pytest; \
	else \
		poetry run pytest; \
	fi

test-cov: ## Run tests with coverage report
	@if [ -d "venv" ]; then \
		. venv/bin/activate && pytest --cov=services --cov-report=term-missing; \
	else \
		poetry run pytest --cov=services --cov-report=term-missing; \
	fi

test-fast: ## Run tests and stop on first failure
	@if [ -d "venv" ]; then \
		. venv/bin/activate && pytest -x -q; \
	else \
		poetry run pytest -x -q; \
	fi

test-verbose: ## Run tests with verbose output
	@if [ -d "venv" ]; then \
		. venv/bin/activate && pytest -vv; \
	else \
		poetry run pytest -vv; \
	fi

lint:
	poetry run ruff check .

format:
	poetry run ruff format .
	poetry run ruff check --fix .

check: lint test

pre-commit-install:
	poetry run pre-commit install
	@echo "Pre-commit hooks installed!"

run-api:
	poetry run api

run-llm-agent:
	poetry run llm-agent

run-decision-gateway:
	poetry run decision-gateway

run-mq-consumer:
	poetry run mq-consumer

run-notification:
	poetry run notification

run-scraper:
	poetry run scrape

run-subscription-api: ## Run the subscription API server
	poetry run python -m services.subscription_api

redis-check: ## Check if Redis is running and accessible
	@echo "Checking Redis connection..."
	@redis-cli ping > /dev/null 2>&1 && echo "✓ Redis is running and accessible on localhost:6379" || \
	(echo "✗ Redis is not accessible. Run 'make redis-start' or install Redis locally." && exit 1)

redis-start: ## Start Redis using Docker (use if no local Redis)
	@echo "Starting Redis in Docker..."
	@docker rm wtf-redis 2>/dev/null || true
	@docker run -d --name wtf-redis -p 6379:6379 redis:latest && \
	echo "✓ Redis started in Docker" || \
	echo "✗ Failed to start Redis. Port 6379 may be in use. Try 'make redis-check' to see if Redis is already running."

redis-stop: ## Stop Redis Docker container
	@echo "Stopping Redis container..."
	@docker stop wtf-redis 2>/dev/null && docker rm wtf-redis 2>/dev/null && echo "✓ Redis container stopped" || \
	echo "Redis container not running"

redis-clean: ## Remove Redis Docker container and data
	@echo "Cleaning up Redis container..."
	@docker stop wtf-redis 2>/dev/null || true
	@docker rm -v wtf-redis 2>/dev/null && echo "✓ Redis container removed" || echo "No Redis container to remove"

redis-cli: ## Connect to Redis CLI (works with local or Docker Redis)
	@redis-cli

docker-up: ## Start all services with Docker Compose
	@echo "Starting services with Docker Compose..."
	docker-compose up -d
	@echo "✓ Services started. Redis available at localhost:6379"

docker-down: ## Stop all Docker Compose services
	@echo "Stopping Docker Compose services..."
	docker-compose down
	@echo "✓ Services stopped"

docker-logs: ## View Docker Compose logs
	docker-compose logs -f

docker-build: ## Build all Docker images
	@echo "Building all Docker images..."
	docker-compose build
	@echo "✓ Docker images built"

docker-init: ## Initialize database in Docker
	@echo "Initializing database in Docker container..."
	docker-compose exec subscription-api python scripts/seed_database.py
	@echo "✓ Database initialized"

seed-db: ## Seed database with events (local)
	poetry run python scripts/seed_database.py

db-stats: ## Show database statistics
	@poetry run python -c "from services.database import get_stats; import json; print(json.dumps(get_stats(), indent=2))"

dev:
	@echo "Services defined in this project:"
	@echo "  - api (port 8000)"
	@echo "  - llm-agent"
	@echo "  - decision-gateway (port 8100)"
	@echo "  - mq-consumer"
	@echo "  - notification (port 8200)"
	@echo ""
	@echo "Use 'make run-<service-name>' to start a service"
	@echo "Example: make run-api"
