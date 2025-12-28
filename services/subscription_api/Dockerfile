FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

ENV DATABASE_PATH=/app/data/wtf.db
ENV PYTHONUNBUFFERED=1
ENV API_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "services.subscription_api"]
