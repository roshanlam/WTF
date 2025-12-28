FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.7.1

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

COPY . .

RUN mkdir -p /app/data

ENV DATABASE_PATH=/app/data/wtf.db
ENV PYTHONUNBUFFERED=1

CMD ["poetry", "run", "llm-agent"]
